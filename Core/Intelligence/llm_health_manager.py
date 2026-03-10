# llm_health_manager.py: Adaptive LLM provider health-check and routing.
# Part of LeoBook Core — Intelligence (AI Engine)
#
# Classes: LLMHealthManager
# Called by: api_manager.py, build_search_dict.py
"""
Multi-key, multi-model LLM health manager.
- Grok: single key (GROK_API_KEY)
- Gemini: comma-separated keys (GEMINI_API_KEY=key1,key2,...,key14)
  Round-robins through active keys AND models to maximize free-tier quota.
Model Chains (Mar 2026 free-tier rate limits per key):
  gemini-2.5-pro 5 RPM / 100 RPD (best reasoning)
  gemini-3-flash-preview 5 RPM / 20 RPD (frontier preview)
  gemini-2.5-flash 10 RPM / 250 RPD (balanced)
  gemini-2.0-flash 15 RPM / 1500 RPD (high throughput)
  gemini-2.5-flash-lite 15 RPM / 1000 RPD (cheap)
  gemini-3.1-flash-lite 15 RPM / 1000 RPD (cheapest, ultra-fast, 1M tokens)
DESCENDING = pro-first (AIGO predictions, match analysis)
ASCENDING = lite-first (search-dict metadata enrichment)
"""
import os
import time
import asyncio
import requests
import threading
from dotenv import load_dotenv
load_dotenv()
PING_INTERVAL = 900 # 15 minutes
class LLMHealthManager:
    """Singleton manager with multi-key, multi-model Gemini rotation."""
    _instance = None
    _lock = asyncio.Lock()
    # ── Model Chains ──────────────────────────────────────────
    # DESCENDING: max intelligence first (AIGO / predictions)
    # gemini-2.5-flash-lite excluded — reserved for SearchDict
    MODELS_DESCENDING = [
        "gemini-2.5-pro",
        "gemini-3-flash-preview",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ]
    # ASCENDING: max throughput first (search-dict / bulk enrichment)
    # gemini-2.5-pro excluded — reserved for AIGO
    MODELS_ASCENDING = [
        "gemini-3.1-flash-lite-preview",
        "gemini-2.5-flash-lite",
        "gemini-2.0-flash",
        "gemini-2.5-flash",
        "gemini-3-flash-preview",
    ]
    # Default model for health-check pings (cheapest)
    PING_MODEL = "gemini-3.1-flash-lite-preview"
    GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions"
    GROK_API_URL = "https://api.x.ai/v1/chat/completions"
    GROK_MODEL = "grok-beta"
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._grok_active = False
            cls._instance._gemini_keys = [] # All parsed keys
            cls._instance._gemini_active = [] # Keys that passed ping
            cls._instance._gemini_index = 0 # Round-robin pointer
            cls._instance._last_ping = 0.0
            cls._instance._initialized = False
            # Per-model cooldown keys (model_name -> {key: expiry_timestamp})
            cls._instance._model_cooldowns = {}
            # Permanently dead keys (403) — persists across ping cycles
            cls._instance._dead_keys = set()
            # Default cooldown duration in seconds (Gemini free-tier resets ~60s)
            cls._instance.COOLDOWN_SECONDS = 65
            # Thread-safe lock for state mutations (get_next / on_429 / etc) — fixes race conditions in async usage
            cls._instance._state_lock = threading.Lock()
        return cls._instance
    # ── Public API ──────────────────────────────────────────────
    async def ensure_initialized(self):
        """Ping providers if we haven't yet or if the interval has elapsed."""
        now = time.time()
        if not self._initialized or (now - self._last_ping) >= PING_INTERVAL:
            async with self._lock:
                if not self._initialized or (time.time() - self._last_ping) >= PING_INTERVAL:
                    await self._ping_all()
    def get_ordered_providers(self) -> list:
        """Returns provider names ordered: active first, inactive last."""
        grok_configured = bool(os.getenv("GROK_API_KEY", "").strip())
        if not self._initialized:
            providers = ["Gemini"]
            if grok_configured:
                providers.insert(0, "Grok")
            return providers
        active = []
        inactive = []
        if grok_configured:
            if self._grok_active:
                active.append("Grok")
            else:
                inactive.append("Grok")
        if self._gemini_active:
            active.append("Gemini")
        else:
            inactive.append("Gemini")
        return active + inactive
    def is_provider_active(self, name: str) -> bool:
        """Check if a specific provider has at least one active key."""
        if name == "Grok":
            return self._grok_active
        if name == "Gemini":
            return len(self._gemini_active) > 0
        return False
    def get_model_chain(self, context: str = "aigo") -> list:
        """
        Returns the model priority chain for the given context.
      
        Args:
            context: "aigo" for DESCENDING (predictions/analysis),
                     "search_dict" for ASCENDING (bulk enrichment).
        """
        if context == "search_dict":
            return list(self.MODELS_ASCENDING)
        return list(self.MODELS_DESCENDING)
    def get_next_gemini_key(self, model: str = None) -> str:
        """
        Round-robin through active Gemini keys, skipping keys on cooldown for
        the given model. Cooldowns expire automatically after COOLDOWN_SECONDS.
        """
        with self._state_lock:
            pool = self._gemini_active if self._gemini_active else self._gemini_keys
            if not pool:
                return ""
            now = time.time()
            cooldowns = self._model_cooldowns.get(model, {}) if model else {}
            # Prune expired cooldowns
            if cooldowns:
                expired = [k for k, exp in cooldowns.items() if exp <= now]
                for k in expired:
                    del cooldowns[k]
            available = [k for k in pool if k not in cooldowns]
            if not available:
                return ""
            key = available[self._gemini_index % len(available)]
            self._gemini_index += 1
            return key
    def get_cooldown_remaining(self, model: str) -> float:
        """Returns seconds until the earliest cooldown for this model expires. 0 if none."""
        with self._state_lock:
            cooldowns = self._model_cooldowns.get(model, {})
            if not cooldowns:
                return 0.0
            now = time.time()
            # Filter to still-active cooldowns
            active = [exp for exp in cooldowns.values() if exp > now]
            if not active:
                return 0.0
            return min(active) - now
    def on_gemini_429(self, failed_key: str, model: str = None):
        """
        Called when a Gemini key hits 429 for a specific model.
        Sets a time-based cooldown (COOLDOWN_SECONDS) — key auto-recovers.
        """
        with self._state_lock:
            if model:
                if model not in self._model_cooldowns:
                    self._model_cooldowns[model] = {}
                expiry = time.time() + self.COOLDOWN_SECONDS
                self._model_cooldowns[model][failed_key] = expiry
                pool = self._gemini_active or self._gemini_keys
                remaining = len([k for k in pool if k not in self._model_cooldowns[model]
                                 or self._model_cooldowns[model][k] <= time.time()])
                print(f" [LLM Health] Key ...{failed_key[-4:]} cooling down for {self.COOLDOWN_SECONDS}s on {model}. "
                      f"{remaining} keys available for this model.")
                if remaining == 0:
                    print(f" [LLM Health] [!] All keys on cooldown for {model} -- waiting or downgrading.")
            else:
                # Legacy: remove from active pool entirely
                if failed_key in self._gemini_active:
                    self._gemini_active.remove(failed_key)
                    remaining = len(self._gemini_active)
                    print(f" [LLM Health] Gemini key rotated out (429). {remaining} keys remaining.")
                    if remaining == 0:
                        print(f" [LLM Health] [!] All {len(self._gemini_keys)} Gemini keys exhausted!")
    def on_gemini_fatal_error(self, failed_key: str, reason: str = "403/400/401"):
        """Called when a Gemini key hits a fatal error (400 Invalid, 401 Unauth, 403 Forbidden). 
        Permanently remove from ALL pools.
        """
        with self._state_lock:
            if failed_key in self._dead_keys:
                return
            self._dead_keys.add(failed_key)
            if failed_key in self._gemini_active:
                self._gemini_active.remove(failed_key)
            if failed_key in self._gemini_keys:
                self._gemini_keys.remove(failed_key)
            print(f" [LLM Health] Gemini key permanently removed ({reason}). "
                  f"{len(self._gemini_active)} active, {len(self._gemini_keys)} total.")
    def reset_model_exhaustion(self):
        """Reset per-model cooldown tracking (call at start of each cycle)."""
        with self._state_lock:
            self._model_cooldowns.clear()
    # ── Internals ───────────────────────────────────────────────
    async def _ping_all(self):
        """Ping Grok + sample Gemini keys."""
        print(" [LLM Health] Pinging providers...")
        # Parse Gemini keys — exclude permanently dead keys (403)
        raw = os.getenv("GEMINI_API_KEY", "")
        self._gemini_keys = [k.strip() for k in raw.split(",") if k.strip() and k.strip() not in self._dead_keys]
        # Reset per-model exhaustion on re-ping (rate limits reset)
        self.reset_model_exhaustion()
        # Ping Grok (only if key is configured)
        grok_key = os.getenv("GROK_API_KEY", "").strip()
        if grok_key:
            self._grok_active = await self._ping_key("Grok", self.GROK_API_URL, self.GROK_MODEL, grok_key)
            tag = "[OK] Active" if self._grok_active else "[X] Inactive"
            print(f" [LLM Health] Grok: {tag}")
        else:
            self._grok_active = False
        # Ping Gemini keys (sample 3 to avoid wasting quota)
        if self._gemini_keys:
            n = len(self._gemini_keys)
            sample_indices = [0]
            if n > 1:
                sample_indices.append(n // 2)
            if n > 2:
                sample_indices.append(n - 1)
            sample_indices = list(dict.fromkeys(sample_indices)) # deterministic + unique
            sample_results = []
            for idx in sample_indices:
                key = self._gemini_keys[idx]
                status = await self._ping_key("Gemini", self.GEMINI_API_URL, self.PING_MODEL, key)
                if status == "FATAL":
                    self.on_gemini_fatal_error(key, "Dead Key detected in ping")
                    sample_results.append(False)
                else:
                    sample_results.append(status == "OK")
            if any(sample_results):
                self._gemini_active = list(self._gemini_keys)
                print(f" [LLM Health] Gemini: [OK] Active ({len(self._gemini_keys)} keys, "
                      f"{len(self.MODELS_DESCENDING)} models available)")
            else:
                self._gemini_active = []
                print(f" [LLM Health] Gemini: [X] Inactive (all {len(self._gemini_keys)} keys failed)")
        else:
            self._gemini_active = []
            print(" [LLM Health] Gemini: [X] No keys configured")
        self._last_ping = time.time()
        self._initialized = True
        with self._state_lock:
            self._gemini_index = 0 # reset round-robin pointer after fresh ping cycle
        if not self._grok_active and not self._gemini_active:
            print(" [LLM Health] [!] CRITICAL -- All LLM providers are offline! User action required.")
    async def _ping_key(self, name: str, api_url: str, model: str, api_key: str) -> str:
        """Ping a single API key. OK (200/429), FATAL (401/403/400-Invalid), or FAIL (other)."""
        if not api_key:
            return "FAIL"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 5,
            "temperature": 0,
        }
        def _do_ping():
            try:
                resp = requests.post(api_url, headers=headers, json=payload, timeout=10)
                # 400 Bad Request with INVALID_ARGUMENT is a dead key (usually bad API key)
                if resp.status_code in (401, 403) or (resp.status_code == 400 and "INVALID_ARGUMENT" in resp.text):
                    return "FATAL"
                return "OK" if resp.status_code in (200, 429) else "FAIL"
            except Exception:
                return "FAIL"
        return await asyncio.to_thread(_do_ping)
# Module-level singleton
health_manager = LLMHealthManager()
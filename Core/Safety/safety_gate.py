# safety_gate.py: Project Stairway safety validation gate.
# Part of LeoBook Core — Safety
#
# Functions: is_stairway_safe(), validate_accumulator(), get_stairway_stake()
#
# All bet candidates MUST pass these checks before placement.
# Reference: Project_Stairway_v2.docx

"""
Project Stairway Safety Gate
Hard-coded validation rules that CANNOT be overridden by model output.

Rules:
  Single bets:    1.20 ≤ odds < 4.00
  Accumulators:   total odds 3.50–5.00, max 4 legs
  Confidence:     ≥ 70% per leg AND overall
  Stake:          ₦1,000 fixed (scaled down only if balance < 10,000)
  Priority:       high-probability first (confidence DESC), NOT EV
"""

from typing import Tuple, List, Dict

# ── Hard Constants (from Project Stairway v2) ────────────────────────────────

SINGLE_ODDS_MIN = 1.20
SINGLE_ODDS_MAX = 4.00
ACCA_TOTAL_ODDS_MIN = 3.50
ACCA_TOTAL_ODDS_MAX = 5.00
ACCA_MAX_LEGS = 4
MIN_CONFIDENCE_PCT = 70.0
FIXED_STAKE = 1000
LOW_BALANCE_THRESHOLD = 10000

# Map string confidence labels → numeric percent
CONFIDENCE_MAP = {
    "Very High": 90.0,
    "High":      75.0,
    "Medium":    50.0,
    "Low":       30.0,
}


def _conf_to_pct(confidence) -> float:
    """Convert confidence (string label, float, or int) to a percentage."""
    if isinstance(confidence, (int, float)):
        return float(confidence) if confidence <= 1.0 else float(confidence)
    if isinstance(confidence, str):
        # Handle "85%" style strings
        cleaned = confidence.strip().rstrip("%")
        try:
            return float(cleaned)
        except ValueError:
            return CONFIDENCE_MAP.get(confidence, 0.0)
    return 0.0


def is_stairway_safe(bet: Dict) -> Tuple[bool, str]:
    """
    Validate a SINGLE bet/leg against Stairway rules.

    Required keys in `bet`:
      - odds: float        (the decimal odds for this leg)
      - confidence: str|float  (model confidence)

    Returns:
      (True,  "pass")             if safe
      (False, "<reason string>")  if rejected
    """
    odds = float(bet.get("odds") or bet.get("booking_odds") or 0)
    confidence = bet.get("confidence", 0)
    conf_pct = _conf_to_pct(confidence)

    # ── Check 1: Odds range ──────────────────────────────────────────────
    if odds < SINGLE_ODDS_MIN:
        return False, f"odds {odds:.2f} below minimum {SINGLE_ODDS_MIN}"
    if odds >= SINGLE_ODDS_MAX:
        return False, f"odds {odds:.2f} at or above maximum {SINGLE_ODDS_MAX}"

    # ── Check 2: Minimum confidence ──────────────────────────────────────
    if conf_pct < MIN_CONFIDENCE_PCT:
        return False, f"confidence {conf_pct:.0f}% below minimum {MIN_CONFIDENCE_PCT:.0f}%"

    return True, "pass"


def validate_accumulator(legs: List[Dict]) -> Tuple[bool, str, List[Dict]]:
    """
    Validate a full accumulator against Stairway rules.
    Filters and returns only safe legs, sorted by confidence DESC.

    Returns:
      (True,  "pass",   safe_legs)   if accumulator is valid
      (False, "<reason>", safe_legs) if accumulator fails rules
    """
    # ── Per-leg safety filter ────────────────────────────────────────────
    safe_legs = []
    for leg in legs:
        ok, reason = is_stairway_safe(leg)
        fixture = leg.get("fixture_id", leg.get("home_team", "?"))
        if ok:
            print(f"    [STAIRWAY ACCEPT] fixture={fixture} "
                  f"odds={float(leg.get('odds', leg.get('booking_odds', 0))):.2f} "
                  f"conf={_conf_to_pct(leg.get('confidence', 0)):.0f}% "
                  f"stake={FIXED_STAKE}")
            safe_legs.append(leg)
        else:
            print(f"    [SAFETY REJECT] fixture={fixture} reason={reason}")

    # ── Sort by confidence DESC (probability-first) ──────────────────────
    safe_legs.sort(
        key=lambda x: _conf_to_pct(x.get("confidence", 0)),
        reverse=True,
    )

    # ── Max legs cap ────────────────────────────────────────────────────
    if len(safe_legs) > ACCA_MAX_LEGS:
        safe_legs = safe_legs[:ACCA_MAX_LEGS]

    if not safe_legs:
        return False, "no legs passed safety gate", []

    # ── Total odds check ────────────────────────────────────────────────
    total_odds = 1.0
    for leg in safe_legs:
        total_odds *= float(leg.get("odds") or leg.get("booking_odds") or 1)

    if total_odds < ACCA_TOTAL_ODDS_MIN:
        return False, f"total odds {total_odds:.2f} below minimum {ACCA_TOTAL_ODDS_MIN}", safe_legs
    if total_odds > ACCA_TOTAL_ODDS_MAX:
        return False, f"total odds {total_odds:.2f} above maximum {ACCA_TOTAL_ODDS_MAX}", safe_legs

    return True, "pass", safe_legs


def get_stairway_stake(current_balance: float) -> int:
    """
    Return the fixed Stairway stake.
    Hard-locked at ₦1,000 unless balance < ₦10,000 (then scale down).
    """
    if current_balance < LOW_BALANCE_THRESHOLD:
        scaled = max(100, int(current_balance * 0.10))
        print(f"    [SAFETY] Low balance ₦{current_balance:,.0f} — "
              f"stake scaled down to ₦{scaled:,}")
        return scaled
    return FIXED_STAKE


def filter_and_rank_candidates(candidates: List[Dict]) -> List[Dict]:
    """
    Filter candidates through safety gate and rank by confidence DESC.
    This is the entry point for rule engine / RL output filtering.

    Takes top candidates that pass the safety gate, sorted by probability.
    """
    safe = []
    for c in candidates:
        ok, reason = is_stairway_safe(c)
        if ok:
            safe.append(c)
        else:
            fixture = c.get("fixture_id", c.get("home_team", "?"))
            print(f"    [SAFETY REJECT] fixture={fixture} reason={reason}")

    # Sort by confidence DESC (probability-first, not EV)
    safe.sort(
        key=lambda x: _conf_to_pct(x.get("confidence", 0)),
        reverse=True,
    )
    return safe

"""
Popup Handler Module
Handles universal popup dismissal, modal detection, and UI recovery mechanisms.
Responsible for automatically dismissing blocking overlays and popups during web automation.
"""

import asyncio
import base64
import json
from typing import Optional

from google.generativeai.types import GenerationConfig, HarmBlockThreshold, HarmCategory

from Helpers.Neo_Helpers.Managers.api_key_manager import gemini_api_call_with_rotation
from Helpers.Neo_Helpers.Managers.db_manager import knowledge_db, save_knowledge


class PopupHandler:
    """Handles automatic popup dismissal and UI recovery"""

    @staticmethod
    async def fb_universal_popup_dismissal(
        page,
        context: str = "fb_generic",
        html: Optional[str] = None,
        monitor_interval: int = 0,
    ) -> bool:
        """
        Universal pop-up dismissal with HTML analysis, pattern detection,
        overlay visibility check, multi-click handling, and Gemini fallback.

        Args:
            page: Playwright Page object
            context: Page context for selector lookup (e.g., "fb_login_page")
            html: Optional HTML content (auto-fetched if None)
            monitor_interval: Seconds between checks (0 = single run)

        Returns:
            bool: True if pop-up was dismissed, False otherwise
        """

        async def single_dismiss_attempt() -> bool:
            try:
                # Step 1: Fetch HTML if not provided
                if html is None:
                    html_content = await page.content()
                else:
                    html_content = html

                # Step 2: Detect known pop-up patterns in HTML
                patterns = PopupHandler.get_popup_patterns()

                has_overlay = any(p in html_content.lower() for p in patterns["overlay_classes"])
                has_popup = any(p in html_content.lower() for p in patterns["popup_wrappers"])
                potential_multi = any(ind in html_content for ind in patterns["multi_step_indicators"])

                if not (has_overlay or has_popup):
                    print("    [AI Pop-up] No pop-up patterns detected (skipped)")
                    return False

                print(
                    f"    [AI Pop-up] Detected: Overlay={has_overlay}, Popup={has_popup}, Multi={potential_multi}"
                )

                # Step 3: Try AI selector first
                close_sel = await PopupHandler.get_smart_close_selector(page, context)
                if close_sel:
                    close_btn = page.locator(close_sel).first
                    if await close_btn.count() > 0 and await close_btn.is_visible(timeout=1500):
                        await close_btn.click(timeout=2000)
                        print("    [AI Pop-up] ✓ Closed via AI selector")
                        await asyncio.sleep(0.8)
                        if potential_multi:
                            print("    [AI Pop-up] Checking multi-step...")
                            return await single_dismiss_attempt()
                        return True

                # Step 4: Fallback selectors (visible-only)
                fallback_selectors = patterns["close_selectors"] + [
                    'button:has-text("Next")',
                    'button:has-text("Got it")',
                    'button:has-text("Dismiss")',
                    'button:has-text("Close")',
                    'svg[aria-label="Close"]',
                    'button[aria-label="Close"]',
                ]

                for sel in fallback_selectors:
                    btn = page.locator(sel).first
                    if await btn.count() > 0 and await btn.is_visible(timeout=1000):
                        await btn.click(timeout=2000)
                        print(f"    [AI Pop-up] ✓ Closed via fallback: {sel}")
                        await asyncio.sleep(0.8)
                        if any(step in sel for step in ["Next", "Got it"]) and potential_multi:
                            print("    [AI Pop-up] Multi-step; continuing...")
                            return await single_dismiss_attempt()
                        return True

                # Step 5: Gemini Vision Fallback
                print("    [AI Pop-up] Using Gemini vision fallback...")

                return await PopupHandler.gemini_popup_analysis(page, html_content)

            except Exception as e:
                print(f"    [AI Pop-up] Attempt failed: {e}")
                return False

        if monitor_interval > 0:
            print(f"    [AI Pop-up] Continuous monitoring every {monitor_interval}s...")
            while True:
                await single_dismiss_attempt()
                await asyncio.sleep(monitor_interval)
        else:
            attempts = 0
            max_attempts = 3
            while attempts < max_attempts:
                if await single_dismiss_attempt():
                    return True
                attempts += 1
                await asyncio.sleep(0.5)
            return False

    @staticmethod
    def get_popup_patterns() -> dict:
        """Get comprehensive popup detection patterns"""
        return {
            "overlay_classes": [
                "dialog-mask",
                "modal-backdrop",
                "overlay",
                "mask",
                "un-op-70%",
                "un-h-100vh",
                "backdrop",
                "popup-overlay",
            ],
            "popup_wrappers": [
                "m-popOver-wrapper",
                "popup-hint",
                "modal-dialog",
                "tooltip",
                "popover",
                "dialog-container",
            ],
            "close_selectors": [
                "svg.close-circle-icon",
                "button.close",
                '[data-dismiss="modal"]',
                'button:has-text("Close")',
            ],
            "multi_step_indicators": [
                "Next",
                "Got it",
                "Step",
                "of",
                "intro",
                "guide",
                "tour",
                "Continue",
            ],
        }

    @staticmethod
    async def get_smart_close_selector(page, context: str) -> Optional[str]:
        """Get smart close selector for popup dismissal"""
        # Import here to avoid circular imports
        from .selector_manager import SelectorManager

        # Try context-specific close selectors
        close_selectors = [
            "top_icon_close",
            "notification_popup_close_icon",
            "dialog_container_close",
            "modal_close_button"
        ]

        for selector_key in close_selectors:
            selector = await SelectorManager.get_selector_auto(page, context, selector_key)
            if selector:
                return selector

        return None

    @staticmethod
    async def gemini_popup_analysis(page, html_content: str) -> bool:
        """Use Gemini vision API for popup analysis and dismissal"""

        # Capture screenshot
        screenshot_bytes = await page.screenshot(full_page=True, type="png")
        img_data = base64.b64encode(screenshot_bytes).decode("utf-8")

        prompt = f"""
        Analyze this webpage screenshot + HTML for pop-up/modal dismissal.
        IDENTIFY:
        1. Close buttons (X icons, Close buttons)
        2. Next/Continue/Got it buttons (multi-step)
        3. Overlay dismissal areas

        Output STRICT JSON only:

        {{
        "selectors": ["primary_close_selector", "backup_selector"],
        "multi_click": true/false,
        "steps": 1,
        "type": "modal|tooltip|guide|popover|none",
        "reason": "brief explanation"
        }}

        If no pop-up: {{"selectors": [], "multi_click": false, "steps": 0, "type": "none", "reason": "No pop-up"}}

        HTML: {html_content[:4000]}...
        """

        try:
            response = await gemini_api_call_with_rotation(
                [prompt, {"inline_data": {"mime_type": "image/png", "data": img_data}}],
                generation_config=GenerationConfig(temperature=0.0, response_mime_type="application/json"),  # type: ignore
                safety_settings={  # type: ignore
                    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
                    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
                },
            )

            if response and response.text:
                from .intelligence import clean_json_response
                cleaned_text = clean_json_response(response.text)
                gemini_output = json.loads(cleaned_text)
                print(f"    [Gemini] Analysis: {gemini_output}")

                selectors = gemini_output.get("selectors", [])
                multi_click = gemini_output.get("multi_click", False)
                steps = gemini_output.get("steps", 1)

                if selectors and steps > 0:
                    success = await PopupHandler.execute_gemini_selectors(page, selectors, steps, multi_click)

                    # Update knowledge base if successful
                    if success:
                        context = "fb_generic"  # Default context
                        if context not in knowledge_db:
                            knowledge_db[context] = {}
                        if selectors:
                            knowledge_db[context]["gemini_popup_close"] = selectors[0]
                            save_knowledge()

                    return success

        except Exception as e:
            print(f"    [Gemini] Parse error: {e}")

        print("    [AI Pop-up] No dismissible elements found")
        return False

    @staticmethod
    async def execute_gemini_selectors(page, selectors: list, steps: int, multi_click: bool) -> bool:
        """Execute selectors provided by Gemini analysis"""
        for i, sel in enumerate(selectors[:steps]):
            btn = page.locator(sel).first
            if await btn.count() > 0 and await btn.is_visible(timeout=2000):
                await btn.click(timeout=3000)
                print(f"    [AI Pop-up] ✓ Gemini selector {i+1}/{steps}: {sel}")
                await asyncio.sleep(1.0)
                if multi_click and i < steps - 1:
                    print("    [AI Pop-up] Multi-step continuing...")
            else:
                print(f"    [AI Pop-up] Selector {i+1} not found or not visible: {sel}")
                return False

        return True

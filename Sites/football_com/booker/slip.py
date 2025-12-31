"""
Betslip Management
Handles counting and clearing of the betslip.
"""

import re
import asyncio
from playwright.async_api import Page
from .ui import robust_click
from Neo.selector_manager import SelectorManager
from Neo.intelligence import get_selector, get_selector_auto

async def get_bet_slip_count(page: Page) -> int:
    """Extract current number of bets in the slip using dynamic selector."""
    count_sel = await get_selector_auto(page, "fb_match_page", "betslip_count_badge")
    
    if count_sel:
        try:
            if await page.locator(count_sel).count() > 0:
                text = await page.locator(count_sel).first.inner_text(timeout=2000)
                count = int(re.sub(r'\D', '', text) or 0)
                if count > 0:
                    return count
        except Exception as e:
            print(f"    [Slip] Count selector failed: {count_sel} - {e}")

    return 0

async def clear_bet_slip(page: Page):
    """Ensure the bet slip is empty before starting a new session using dynamic selectors."""
    print("    [Slip] Checking if bet slip needs clearing...")
    try:
        if await get_bet_slip_count(page) > 0:
            print("    [Slip] Bets detected. Opening slip to clear...")

            # Open bet slip
            open_sel = await get_selector_auto(page, "fb_match_page", "slip_trigger_button")
            slip_opened = False
            
            if open_sel:
                try:
                    if await page.locator(open_sel).count() > 0:
                        await robust_click(page.locator(open_sel).first, page)
                        print(f"    [Slip] Opened bet slip with selector: {open_sel}")
                        slip_opened = True
                        await asyncio.sleep(2)
                except Exception as e:
                    print(f"    [Slip] Open selector failed: {open_sel} - {e}")
            else:
                 print("    [Slip] Slip trigger selector missing")

            if not slip_opened:
                print("    [Slip] Could not open bet slip")
                return

            # Clear all bets
            clear_sel = await get_selector_auto(page, "fb_match_page", "betslip_clear_all")
            bets_cleared = False
            
            if clear_sel:
                try:
                    if await page.locator(clear_sel).count() > 0:
                        await page.locator(clear_sel).first.click()
                        print(f"    [Slip] Clicked clear with selector: {clear_sel}")
                        bets_cleared = True
                        await asyncio.sleep(1)

                        # Confirm clear action if confirmation appears
                        confirm_sel = await get_selector_auto(page, "fb_match_page", "confirm_bet_button")
                        if confirm_sel:
                            try:
                                if await page.locator(confirm_sel).count() > 0:
                                    await page.locator(confirm_sel).first.click()
                                    print(f"    [Slip] Confirmed clear with selector: {confirm_sel}")
                            except:
                                pass
                except Exception as e:
                    print(f"    [Slip] Clear selector failed: {clear_sel} - {e}")

            if bets_cleared:
                print("    [Slip] Successfully cleared all bets")
            else:
                print("    [Slip] Could not clear bets")

            # Close bet slip
            try:
                await page.keyboard.press("Escape")
                await asyncio.sleep(1)
            except:
                pass

        else:
            print("    [Slip] Bet slip is already empty.")
    except Exception as e:
        print(f"    [Slip Warning] Failed to clear slip: {e}")

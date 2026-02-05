# booking_code.py: Bet code generation and betslip preparation.
# Refactored for Clean Architecture (v2.7)
# This script searches for outcomes and retrieves the shareable booking codes.

"""
Booking Code Extractor
Handles the specific logic for Phase 2a: Harvest.
Visits a match, books a single bet, extracts the code, and saves it.
"""

import asyncio
import re
from typing import Dict, Optional, Tuple
from playwright.async_api import Page
from Core.Intelligence.selector_manager import SelectorManager
from .ui import robust_click
from .slip import force_clear_slip
from Data.Access.db_helpers import update_site_match_status, update_prediction_status


async def get_outcome_odds(loc):
    try:
        odds_text = await loc.evaluate('el => el.nextElementSibling?.innerText || ""')
        return float(odds_text.replace(",", ".").strip()) if odds_text else 0.0
    except:
        return 0.0


async def harvest_single_match_code(page: Page, match: Dict, prediction: Dict) -> bool:
    """
    Robust Phase 2a Harvest with extended timeouts, animation delays, fallbacks, and retries.
    """
    fixture_id = prediction.get('fixture_id')
    url = match.get('url')
    outcome = prediction.get('prediction')

    print(f"\n   [Harvest] Starting for fixture {fixture_id} - {url}")

    for attempt in range(1, 4):  # Full retry loop
        try:
            # Pre-clear
            await force_clear_slip(page)
            await asyncio.sleep(3)

            # Navigate & stabilize
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await page.wait_for_selector(
                SelectorManager.get_selector_strict("fb_match_page", "match_header"),
                timeout=30000
            )
            await page.screenshot(path=f"Logs/Debug/harvest_pre_{fixture_id}_attempt{attempt}.png")

            # Click search icon - Try multiple candidates and find visible one
            search_icon_sel = SelectorManager.get_selector_strict("fb_match_page", "search_icon")
            icons = page.locator(search_icon_sel)
            clicked = False
            for i in range(await icons.count()):
                icon = icons.nth(i)
                if await icon.is_visible():
                    await robust_click(icon, page)
                    clicked = True
                    break
            
            if not clicked:
                # Fallback to general search icons if strict selector fails visible check
                await robust_click(page.locator(".m-search-icon, .icon-search, [class*='search-icon']").first, page)
            
            await asyncio.sleep(2)  # Critical animation delay

            # Wait for input with more exhaustive fallbacks
            input_selectors = [
                SelectorManager.get_selector_strict("fb_match_page", "search_input"),
                'input[type="search"]',
                '.m-search-input input',
                'input[placeholder*="search" i]',
                'input[aria-label*="search" i]',
                '.search-box input'
            ]
            search_input = None
            for sel in input_selectors:
                loc = page.locator(sel).first
                try:
                    # Check visibility without waiting 15s every time
                    if await loc.is_visible():
                        search_input = loc
                        break
                    # If not immediately visible, wait a short bit
                    await loc.wait_for(state="visible", timeout=3000)
                    search_input = loc
                    break
                except:
                    continue

            if not search_input:
                # Final attempt: just try to find ANY visible input in a search-like container
                try:
                    alt_input = page.locator("div[class*='search'] input, section[class*='search'] input").first
                    if await alt_input.is_visible(timeout=2000):
                        search_input = alt_input
                except: pass

            if not search_input:
                raise TimeoutError("Search input not visible after multiple fallback attempts")

            from .mapping import find_market_and_outcome
            market_name, _ = await find_market_and_outcome(prediction)
            if not market_name: market_name = outcome

            await search_input.fill(market_name)
            await search_input.press("Enter")
            await asyncio.sleep(2)

            # Wait for market results
            # Wait for market results - Flexible Wait
            market_container_sel = ".markets-container, .market-list, .betting-markets, .m-market-list"
            market_found = False
            for _ in range(10): # 10 * 1s = 10s flexible wait
                try:
                    if await page.locator(market_container_sel).first.is_visible():
                        market_found = True
                        break
                except: pass
                await asyncio.sleep(1)
            
            if not market_found:
                 # It's possible the search result IS the market list (e.g. filtered view)
                 # so we proceed but log a warning if strictly needed
                 print("    [Harvest Warning] Market container not strictly visible, but proceeding to outcome search...")

            await asyncio.sleep(1)

            # Expand market if collapsed (Handled robustly in select_outcome now)
            # Pre-expansion removed to avoid strict mode violations on generic selectors.

            # Select outcome with logic for Tabular markets (Over/Under)
            success = await select_outcome(page, prediction)
            if not success:
                 print(f"    [Harvest Failed] Could not select outcome for '{outcome}'")
                 return False
                 
            # Note: select_outcome now handles locating the button. 
            # We need to re-verify odds logic from the returned element if needed, 
            # but select_outcome encapsulates that.  
            
            # Post-selection: The button is clicked inside select_outcome.
            # We just need to proceed to booking.
            await asyncio.sleep(2)
            await page.wait_for_selector("fb_match_page.bet_slip_container", timeout=15000)

            # Book Bet & Extract
            book_btn_sel = SelectorManager.get_selector_strict("fb_match_page", "book_bet_button")
            await robust_click(page.locator(book_btn_sel).first, page)
            await page.wait_for_selector("fb_match_page.booking_modal", timeout=20000)
            code = await page.inner_text("fb_booking_share_page.booking_code_text", timeout=10000)
            booking_url = await page.get_attribute("fb_booking_share_page.booking_share_link", "href") or f"https://www.football.com/ng/m?shareCode={code}"

            # Save
            from Data.Access.db_helpers import append_or_update
            append_or_update("football_com_matches.csv", fixture_id, {
                "booking_code": code,
                "booking_url": booking_url,
                "status": "harvested"
            })

            # Dismiss & post-clear
            dismiss_sel = SelectorManager.get_selector("fb_match_page", "modal_dismiss") or "fb_match_page.modal_dismiss"
            await robust_click(page.locator(dismiss_sel).first, page)
            await force_clear_slip(page)

            print(f"    [Harvest Success] Code: {code}")
            await page.screenshot(path=f"Logs/Debug/harvest_success_{fixture_id}.png")
            print(f"    [Harvest Success] {fixture_id} -> Code: {code}")
            return True

        except Exception as e:
            print(f"    [Harvest Retry] Attempt {attempt} failed: {str(e)}")
            await page.screenshot(path=f"Logs/Debug/harvest_fail_attempt{attempt}_{fixture_id}.png")
            await asyncio.sleep(10)

    print(f"    [Harvest Failed] {fixture_id} after 3 attempts")
    update_prediction_status(fixture_id, prediction.get('date'), "failed_harvest")
    print(f"    [Harvest Error] {fixture_id}: All attempts failed")
    return False

    
from .mapping import find_market_and_outcome

async def expand_collapsed_market(page: Page, market_name: str):
    """If a market is found but collapsed, expand it."""
    try:
        header_sel = SelectorManager.get_selector("fb_match_page", "market_header")
        if header_sel:
             target_header = page.locator(header_sel).filter(has_text=market_name).first
             if await target_header.count() > 0:
                 # print(f"    [Market] Clicking market header for '{market_name}' to ensure expansion...")
                 await robust_click(target_header, page)
                 await asyncio.sleep(1)
    except Exception as e:
        print(f"    [Market] Expansion failed: {e}")

async def select_outcome(page: Page, prediction: Dict) -> bool:
    """
    Safe outcome selection with odds check (v2.7).
    Handles standard buttons and Tabular markets (Over/Under).
    """
    from .mapping import find_market_and_outcome
    import re
    
    # 1. Map Prediction
    m_name, o_name = await find_market_and_outcome(prediction)
    if not m_name:
        print(f"    [Selection Error] No mapping for pred: {prediction.get('prediction')}")
        return False

    try:
        # 2. Expand Market if needed
        # Use first() to avoid strict mode violations if multiple matches found
        header_sel = SelectorManager.get_selector_strict("fb_match_page", "market_group_header")
        market_container = page.locator(header_sel).filter(has_text=m_name).first
        
        if await market_container.count() > 0:
            # Scroll it into view
            await market_container.scroll_into_view_if_needed()
            await asyncio.sleep(0.5)

            # Check if collapsed (often has a specific class or child icon)
            is_collapsed = await market_container.locator(".collapsed").count() > 0 or \
                           await market_container.locator(".icon-arrow-down").count() > 0
            
            if is_collapsed:
                # print(f"    [Selection] Market '{m_name}' is collapsed. Expanding...")
                await robust_click(market_container, page)
                await asyncio.sleep(1.5)
        else:
            # Proactive Search: Use the Site's Search Functionality (User Request)
            print(f"    [Selection] Market '{m_name}' not found. Attempting search-based discovery...")
            
            search_btn_sel = SelectorManager.get_selector_strict("fb_match_page", "match_market_search_icon_button") or \
                             SelectorManager.get_selector_strict("fb_match_page", "search_icon")
            search_input_sel = SelectorManager.get_selector_strict("fb_match_page", "match_market_search_input") or \
                               SelectorManager.get_selector_strict("fb_match_page", "search_input")
            
            if search_btn_sel and await page.locator(search_btn_sel).count() > 0:
                await robust_click(page.locator(search_btn_sel).first, page)
                
            if search_input_sel:
                 # CRITICAL: Max 1.5s delay allowed here per user request
                 await asyncio.sleep(1.5)
                 await page.fill(search_input_sel, m_name)
                 await page.press(search_input_sel, "Enter")
                 await asyncio.sleep(2)
                 
                 # After search, check again
                 market_container = page.locator(header_sel).filter(has_text=m_name).first
                 if await market_container.count() > 0:
                      if await market_container.locator(".collapsed").count() > 0:
                          await robust_click(market_container, page)
            
        # 3. Locate Outcome Button
        outcome_btn = None
        
        # A) Special Handling for Over/Under (Tabular)
        # e.g. "Goals Over/Under", "Over 2.5"
        if "Over/Under" in m_name:
            ou_match = re.search(r"(Over|Under) (\d+\.5)", o_name, re.IGNORECASE)
            if ou_match:
                ou_type = ou_match.group(1).title() # "Over" or "Under"
                line = ou_match.group(2) # "0.5", "1.5"
                
                # Find row with this line
                # Look for 'em' tag with exact text inside a table row
                row_loc = page.locator(f".m-table-row").filter(has=page.locator(f"em", has_text=line))
                
                if await row_loc.count() > 0:
                    # Found row. Get buttons container (second cell usually)
                    # The buttons are usually divs with 'un-rounded' class inside the flex container
                    # We assume 1st = Over, 2nd = Under based on standard layout
                    btn_index = 0 if ou_type == "Over" else 1
                    outcome_btn = row_loc.locator(".un-rounded-rem-\[10px\]").nth(btn_index)
                    print(f"    [Selection] Found tabular button for {ou_type} {line}")

        # B) Standard Text Search (Fallback)
        if not outcome_btn or await outcome_btn.count() == 0:
            outcome_btn = page.locator(f"//div[contains(@class, 'm-outcome-item')]//*[normalize-space()='{o_name}']").first
        
        # C) Fallback 2: button or div with role button
        if not outcome_btn or await outcome_btn.count() == 0:
            btn_sel = f"button:has-text('{o_name}'), div[role='button']:has-text('{o_name}'), .m-outcome-item:has-text('{o_name}')"
            outcome_btn = page.locator(btn_sel).filter(has_text=re.compile(f"^{o_name}$|^{o_name}\\s|\\s{o_name}$")).first

        if not outcome_btn or await outcome_btn.count() == 0:
            print(f"    [Selection Error] Outcome button '{o_name}' not found.")
            return False

        # Extract Odds & Verify
        odds_text = await outcome_btn.inner_text()
        # regex for float numbers
        odds_match = re.search(r'(\d+\.\d+)', odds_text)
        if odds_match:
            odds_val = float(odds_match.group(1))
            if odds_val < 1.20:
                print(f"    [Selection Skip] Odds {odds_val} for '{o_name}' are < 1.20 limit.")
                return False
            # print(f"    [Selection] Found odds: {odds_val} for '{o_name}'.")

        # 4. Click
        await robust_click(outcome_btn, page)
        return True

    except Exception as e:
        print(f"    [Selection Error] Logic failed: {e}")
        return False


async def extract_booking_info(page: Page) -> Tuple[str, str]:
    """
    Pulls code & URL from the Book Bet modal (v2.7).
    Returns (code, url) or ("", "") if failed.
    """
    modal_sel = SelectorManager.get_selector_strict("fb_match_page", "booking_code_modal")
    code_sel = SelectorManager.get_selector_strict("fb_match_page", "booking_code_text")
    
    try:
        # Wait for modal
        await page.wait_for_selector(modal_sel, state="visible", timeout=15000)
        
        # Extract code with retries
        code_text = ""
        for _ in range(5):
             code_text = (await page.locator(code_sel).first.inner_text(timeout=2000)).strip()
             if code_text and len(code_text) >= 5:
                 break
             await asyncio.sleep(1)
        
        if not code_text:
            return "", ""
            
        booking_url = f"https://www.football.com/ng/m?shareCode={code_text}"
        return code_text, booking_url

    except Exception as e:
        print(f"    [Extraction Error] Modal extraction failed: {e}")
        return "", ""

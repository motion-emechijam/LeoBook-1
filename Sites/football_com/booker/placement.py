"""
Bet Placement Orchestration
Handles adding selections to the slip and finalizing accumulators.
"""

import asyncio
from typing import List, Dict
from pathlib import Path
from datetime import datetime as dt
from playwright.async_api import Page
from Helpers.Site_Helpers.site_helpers import get_main_frame
from Helpers.DB_Helpers.db_helpers import update_prediction_status
from Helpers.utils import log_error_state, capture_debug_snapshot
from Neo.selector_manager import SelectorManager
from Neo.intelligence import get_selector, get_selector_auto, fb_universal_popup_dismissal as neo_popup_dismissal

from .ui import robust_click, handle_page_overlays, dismiss_overlays
from .mapping import find_market_and_outcome
from .slip import get_bet_slip_count
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

async def ensure_bet_insights_collapsed(page: Page):
    """Ensure the bet insights widget is collapsed to prevent obstruction."""
    try:
        header = page.locator('div.srct-widget-header_custom').first
        if await header.count() > 0:
            arrow = header.locator('div.srct-widget-header_custom-arrow')
            if await arrow.count() > 0:
                is_expanded = await arrow.evaluate('el => el.classList.contains("rotate-arrow")')
                if is_expanded:
                    print("    [UI] Collapsing Bet Insights widget...")
                    await header.click()
                    # Wait for collapse animation or arrow status change
                    try:
                       await arrow.wait_for(state='visible', timeout=2000)
                    except:
                       pass
    except Exception as e:
        print(f"    [UI] Bet Insights collapse check failed (non-critical): {e}")

async def place_bets_for_matches(page: Page, matched_urls: Dict[str, str], day_predictions: List[Dict], target_date: str):
    """Visit matched URLs and place bets using prediction mappings."""
    selected_bets = 0
    processed_urls = set()
    MAX_BETS = 50

    for match_id, match_url in matched_urls.items():
        if await get_bet_slip_count(page) >= MAX_BETS:
            print(f"[Info] Slip full ({MAX_BETS}). Finalizing accumulator.")
            await finalize_accumulator(page, target_date)

        if not match_url or match_url in processed_urls: continue
        
        pred = next((p for p in day_predictions if str(p.get('fixture_id', '')) == str(match_id)), None)
        if not pred or pred.get('prediction') == 'SKIP': continue

        print(f"[Match Found] {pred['home_team']} vs {pred['away_team']}")
        processed_urls.add(match_url)

        try:
            if page.is_closed():
                print("  [Fatal] Page was closed before navigation. Aborting.")
                from playwright.async_api import Error as PlaywrightError
                raise PlaywrightError("Page closed before navigation")

            print(f"    [Nav] Navigating to match: {match_url}")
            await page.goto(match_url, wait_until='domcontentloaded', timeout=30000)

            if page.is_closed():
                print("  [Fatal] Page was closed immediately after navigation. Aborting.")
                from playwright.async_api import Error as PlaywrightError
                raise PlaywrightError("Page closed after navigation")

            await asyncio.sleep(5)
            await neo_popup_dismissal(page, match_url)
            await ensure_bet_insights_collapsed(page)

            # After successful navigation, get the main frame and place bets
            frame = await get_main_frame(page)
            if not frame:
                print(f"    [Error] Could not get main frame for {match_url}")
                update_prediction_status(match_id, target_date, 'dropped')
                continue

            m_name, o_name = await find_market_and_outcome(pred)
            if not m_name:
                print(f"    [Info] No market found for prediction: {pred.get('prediction', 'N/A')}")
                update_prediction_status(match_id, target_date, 'dropped')
                continue
            
            # Special handling for Draw No Bet abbreviation
            search_market_name = m_name
            if m_name.endswith("(DNB)"):
                search_market_name = "Draw No Bet"
                print(f"    [Betting] Adjusted search for {m_name} -> {search_market_name}")

            print(f"    [Betting] Looking for market '{search_market_name}' with outcome '{o_name}'")

            # Find and click search icon using dynamic selector
            search_sel = await get_selector_auto(page, "fb_match_page", "search_icon")
            search_clicked = False
            
            if search_sel:
                try:
                    if await frame.locator(search_sel).count() > 0:
                        await frame.locator(search_sel).first.click()
                        print(f"    [Betting] Clicked search with selector: {search_sel}")
                        search_clicked = True
                        await asyncio.sleep(1)
                except Exception as e:
                    print(f"    [Betting] Search selector failed: {search_sel} - {e}")
            else:
                 print("    [Betting] Search selector missing in knowledge.json")

            if not search_clicked:
                print("    [Betting] Could not find search icon")
                await capture_debug_snapshot(page, f"fail_search_icon_{match_id}", "Search icon selector not found or not clickable.")
                continue

            # Find and fill search input using dynamic selector
            input_sel = await get_selector_auto(page, "fb_match_page", "search_input")
            input_found = False
            
            if input_sel:
                try:
                    if await frame.locator(input_sel).count() > 0:
                        search_input = frame.locator(input_sel).first
                        await search_input.fill(search_market_name)
                        await asyncio.sleep(0.5)
                        await page.keyboard.press("Enter")
                        print(f"    [Betting] Filled '{search_market_name}' and pressed Enter.")
                        input_found = True
                        await asyncio.sleep(3) # Wait for filter to apply
                except Exception as e:
                    print(f"    [Betting] Input selector failed: {input_sel} - {e}")
            else:
                print("    [Betting] Input selector missing in knowledge.json")

            if not input_found:
                print("    [Betting] Could not find search input")
                await capture_debug_snapshot(page, f"fail_search_input_{match_id}", "Search input not found after clicking search icon.")
                continue

            # Select Outcome using dynamic selector
            row_container = await get_selector_auto(page, "fb_match_page", "outcome_row_container")
            bet_selected = False
            
            if row_container:
                # Check if we actually have any rows visible after search
                try:
                    visible_rows = await frame.locator(row_container).count()
                    if visible_rows == 0:
                        print(f"    [Betting] No outcome rows visible after searching for '{search_market_name}'")
                        await capture_debug_snapshot(page, f"vis_rows_zero_{match_id}", f"Search: {search_market_name}. No rows in container.")
                except:
                    pass

                # Construct specific selector
                # Construct specific selector
                outcome_sel = f"{row_container} > div:has-text('{o_name}')"
                try:
                    if await frame.locator(outcome_sel).count() > 0:
                        count_before = await get_bet_slip_count(page)
                        if await robust_click(frame.locator(outcome_sel).first, page):
                            await asyncio.sleep(2)
                            if await get_bet_slip_count(page) > count_before:
                                selected_bets += 1
                                update_prediction_status(match_id, target_date, 'booked')
                                print(f"    [Success] Added bet for {pred['home_team']} vs {pred['away_team']}")
                                bet_selected = True
                except Exception as e:
                    print(f"    [Betting] Outcome selector failed: {outcome_sel} - {e}")
            else:
                 print("    [Betting] Outcome row container missing in knowledge.json")

            if bet_selected:
                continue

            print(f"    [Info] Could not place bet for {pred['home_team']} vs {pred['away_team']}")
            await capture_debug_snapshot(page, f"fail_outcome_{match_id}", f"Market: {search_market_name}, Outcome: {o_name} not found.")
            update_prediction_status(match_id, target_date, 'dropped')

        except Exception as e:
            print(f"    [Error] Match failed: {e}")
            # Check for Playwright-specific errors indicating page/browser closure
            from playwright.async_api import Error as PlaywrightError
            error_msg = str(e).lower()
            is_closure_error = (
                "target closed" in error_msg or 
                "browser has been closed" in error_msg or 
                "context was closed" in error_msg or
                "page has been closed" in error_msg
            )
            if is_closure_error or isinstance(e, PlaywrightError):
                print("    [Fatal] Browser or Page closed during betting loop. Aborting.")
                raise e

    print(f"  [Summary] Selected {selected_bets} bets for {target_date}.")
    if await get_bet_slip_count(page) > 0:
        await finalize_accumulator(page, target_date)

async def finalize_accumulator(page: Page, target_date: str) -> bool:
    """Navigate to slip, enter stake, and confirm placement."""
    print(f"[Betting] Finalizing accumulator for {target_date}...")
    try:
        await dismiss_overlays(page)
        await handle_page_overlays(page)
        # Refresh state after dismissals
        await asyncio.sleep(1)
        await page.keyboard.press("End")
        
        # Check if slip is open
        drawer_sel = await get_selector_auto(page, "fb_match_page", "slip_drawer_container")
        is_open = False
        if drawer_sel:
             is_open = await page.locator(drawer_sel).first.is_visible(timeout=500)

        if not is_open:
            trigger_sel = await get_selector_auto(page, "fb_match_page", "slip_trigger_button")
            if trigger_sel:
                if await robust_click(page.locator(trigger_sel).first, page):
                    await asyncio.sleep(3)
            else:
                print("    [Betting] Slip trigger selector missing")

        # Ensure 'Multiple' tab is selected for accumulators
        multi_sel = await get_selector_auto(page, "fb_match_page", "slip_tab_multiple")
        
        if multi_sel and await page.locator(multi_sel).count() > 0:
            if await page.locator(multi_sel).is_visible(timeout=2000):
                await page.locator(multi_sel).click()
                await asyncio.sleep(1)

        # Enter Stake
        stake_sel = await get_selector_auto(page, "fb_match_page", "stake_input")
        stake_entered = False
        
        if stake_sel:
            try:
                if await page.locator(stake_sel).count() > 0:
                    input_field = page.locator(stake_sel).first
                    await input_field.click()
                    await input_field.fill("1")
                    await page.keyboard.press("Enter")
                    print(f"    [Betting] Entered stake with selector: {stake_sel}")
                    stake_entered = True
                    await asyncio.sleep(1)
            except Exception as e:
                print(f"    [Betting] Stake selector failed: {stake_sel} - {e}")

        if not stake_entered:
            print("    [Warning] Could not enter stake. Attempting to place anyway.")

        # Place bet
        place_sel = await get_selector_auto(page, "fb_match_page", "place_bet_button")
        bet_placed = False
        
        if place_sel:
            try:
                if await robust_click(page.locator(place_sel).first, page):
                    print(f"    [Betting] Clicked place bet with selector: {place_sel}")
                    bet_placed = True
                    await asyncio.sleep(2)
            except Exception as e:
                print(f"    [Betting] Place bet selector failed: {place_sel} - {e}")

        if not bet_placed:
            print("    [Betting] Could not place bet")
            return False

        # Confirm bet
        confirm_sel = await get_selector_auto(page, "fb_match_page", "confirm_bet_button")
        
        if confirm_sel:
            try:
                if await page.locator(confirm_sel).count() > 0:
                    await robust_click(page.locator(confirm_sel).first, page)
                    print(f"    [Betting] Confirmed bet with selector: {confirm_sel}")
                    await asyncio.sleep(3)
                    
                    # Extract and save booking code
                    booking_code = await extract_booking_details(page)
                    if booking_code and booking_code != "N/A":
                        await save_booking_code(target_date, booking_code, page)
                    
                    print(f"    [Success] Placed for {target_date}")
                    return True
            except Exception as e:
                 print(f"    [Betting] Confirm selector failed: {confirm_sel} - {e}")

        print("    [Betting] Could not confirm bet")
        return False
    except Exception as e:
        await log_error_state(page, "finalize_fatal", e)
    return False

async def extract_booking_details(page: Page) -> str:
    """Extract booking code using dynamic selector."""
    code_sel = await get_selector_auto(page, "fb_match_page", "booking_code_text")
    
    if code_sel:
        try:
            if await page.locator(code_sel).count() > 0:
                code = await page.locator(code_sel).first.inner_text()
                if code and code.strip():
                    print(f"    [Booking] Code: {code.strip()}")
                    return code.strip()
        except Exception as e:
            print(f"    [Booking] Code selector failed: {code_sel} - {e}")
            
    print("    [Booking] Could not extract booking code")
    return "N/A"


async def save_booking_code(target_date: str, booking_code: str, page: Page):
    """
    Save booking code to file and capture betslip screenshot.
    Stores in DB/bookings.txt with timestamp and date association.
    """
    from pathlib import Path
    
    try:
        # Save to bookings file
        db_dir = Path("DB")
        db_dir.mkdir(exist_ok=True)
        bookings_file = db_dir / "bookings.txt"
        
        timestamp = dt.now().strftime("%Y-%m-%d %H:%M:%S")
        booking_entry = f"{timestamp} | Date: {target_date} | Code: {booking_code}\n"
        
        with open(bookings_file, "a", encoding="utf-8") as f:
            f.write(booking_entry)
        
        print(f"    [Booking] Saved code {booking_code} to bookings.txt")
        
        # Capture betslip screenshot for records
        try:
            screenshot_path = db_dir / f"betslip_{booking_code}.png"
            await page.screenshot(path=str(screenshot_path), full_page=True)
            print(f"    [Booking] Saved screenshot to {screenshot_path.name}")
        except Exception as screenshot_error:
            print(f"    [Booking] Screenshot failed: {screenshot_error}")
            
    except Exception as e:
        print(f"    [Booking] Failed to save booking code: {e}")

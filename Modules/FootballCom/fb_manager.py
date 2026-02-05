# fb_manager.py: Orchestration layer for Football.com booking process.
# Refactored for Clean Architecture (v2.7)
# This script coordinates session loading, navigation, harvesting, and placement.

"""
Football.com Main Orchestrator
Coordinates all sub-modules to execute the complete booking workflow.
"""

import asyncio
from pathlib import Path
from playwright.async_api import Playwright

# Modular Imports
from .fb_setup import get_pending_predictions_by_date
from .fb_session import launch_browser_with_retry
from .fb_url_resolver import resolve_urls
from .navigator import load_or_create_session, extract_balance
from Core.Utils.utils import log_error_state
from Core.Utils.monitor import PageMonitor
from Core.System.lifecycle import log_state

async def run_football_com_booking(playwright: Playwright):
    """
    Main Phase 2 Orchestrator.
    Manages the session retry loop and calls modular components.
    """
    print("\n--- Running Football.com Booking (Phase 2) ---")
    
    predictions_by_date = await get_pending_predictions_by_date()
    if not predictions_by_date:
        return
    
    user_data_dir = Path("Data/Auth/ChromeData_v3").absolute()
    user_data_dir.mkdir(parents=True, exist_ok=True)

    max_restarts = 3
    restarts = 0
    
    while restarts <= max_restarts:
        context = None
        page = None
        try:
            print(f"  [System] Launching Session (Restart {restarts}/{max_restarts})...")
            context = await launch_browser_with_retry(playwright, user_data_dir)
            
            _, page = await load_or_create_session(context)
            PageMonitor.attach_listeners(page)
            
            current_balance = await extract_balance(page)
            print(f"  [Balance] Current: ₦{current_balance:.2f}")
            log_state("Phase 2", "Session Validated", f"Balance: ₦{current_balance:.2f}")

            for target_date, day_preds in sorted(predictions_by_date.items()):
                print(f"\n--- Date: {target_date} ({len(day_preds)} matches) ---")
                
                # 1. URL Resolution
                matched_urls = await resolve_urls(page, target_date, day_preds)
                if not matched_urls:
                    continue

                # 2. Betting Phase (Unified)
                from Modules.FootballCom.booker.booking_code import place_bets_for_matches
                await place_bets_for_matches(page, matched_urls, day_preds, target_date)
                
                log_state("Phase 2", "Cycle Complete", f"Processed {target_date}")

            break  # Success exit

        except Exception as e:
            is_fatal = "FatalSessionError" in str(type(e)) or "dirty" in str(e).lower()
            
            if is_fatal and restarts < max_restarts:
                print(f"\n[!!!] FATAL SESSION ERROR: {e}")
                print(f"[!!!] Resetting session and restarting browser (Attempt {restarts+1}/{max_restarts})...")
                restarts += 1
                if context: 
                    await context.close()
                await asyncio.sleep(5)
                continue
            else:
                await log_error_state(page, "phase2_fatal", e)
                print(f"  [CRITICAL] Phase 2 failed: {e}")
                break
        
        finally:
            if context:
                try:
                    await context.close()
                except:
                    pass
"""
Football.com Main Orchestrator
Coordinates all sub-modules to execute the complete booking workflow.
"""

import asyncio
import os
from datetime import datetime as dt, timedelta
from pathlib import Path
from typing import List, Dict, Optional

from playwright.async_api import Browser, Playwright

from Helpers.constants import WAIT_FOR_LOAD_STATE_TIMEOUT

from .navigator import load_or_create_session, navigate_to_schedule, select_target_date, extract_balance, log_page_title
from .extractor import extract_league_matches
from .matcher import match_predictions_with_site, filter_pending_predictions
from .booker import place_bets_for_matches, finalize_accumulator, clear_bet_slip
from Helpers.DB_Helpers.db_helpers import PREDICTIONS_CSV
from Helpers.utils import log_error_state
from Helpers.monitor import PageMonitor


async def run_football_com_booking(playwright: Playwright):
    """
    Main function to handle Football.com login, match mapping, and bet placement.
    Orchestrates the entire booking workflow using modular components.
    """
    print("\n--- Running Football.com Booking ---")

    # 1. Filter pending predictions
    pending_predictions = await filter_pending_predictions()
    if not pending_predictions:
        print("  [Info] No pending predictions to book.")
        return

    # Group predictions by date (only future dates)
    predictions_by_date = {}
    today = dt.now().date()
    for pred in pending_predictions:
        date_str = pred.get('date')
        if date_str:
            try:
                pred_date = dt.strptime(date_str, "%d.%m.%Y").date()
                if pred_date >= today:
                    if date_str not in predictions_by_date:
                        predictions_by_date[date_str] = []
                    predictions_by_date[date_str].append(pred)
            except ValueError:
                continue  # Skip invalid dates

    if not predictions_by_date:
        print("  [Info] No predictions found.")
        return

    print(f"  [Info] Dates with predictions: {sorted(predictions_by_date.keys())}")

    user_data_dir = Path("DB/ChromeData").absolute()
    user_data_dir.mkdir(parents=True, exist_ok=True)
    
    print("  [System] Launching Persistent Context for Football.com...")
    context = None
    page = None
    
    try:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=str(user_data_dir),
            headless=False,
            args=[
                "--disable-dev-shm-usage", 
                "--no-sandbox", 
                "--disable-gpu",
                "--disable-extensions",
                "--disable-blink-features=AutomationControlled" 
            ],
            viewport={'width': 375, 'height': 812}, # Taller viewport for modern mobile
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
            timeout=60000 # Increased timeout
        )
    except Exception as launch_e:
        print(f"  [CRITICAL ERROR] Failed to launch browser: {launch_e}")
        
        # Automatic Lock Cleanup
        lock_file = user_data_dir / "SingletonLock"
        if lock_file.exists():
            print("  [Auto-Fix] detected Chrome SingletonLock. removing...")
            try:
                lock_file.unlink()
                print("  [Auto-Fix] Lock file removed. Please restart.")
                return 
            except Exception as lock_e:
                 print(f"  [Auto-Fix Failed] Could not remove lock file: {lock_e}")

        print("  [Action Required] Please ensure no other Chrome/Playwright instances are running.")
        print("  [Info] Try 'taskkill /F /IM chrome.exe /T' if this persists.")
        return

    try:
        # 2. Load or create session
        # Note: navigator now accepts context directly
        page = await load_or_create_session(context)
        await log_page_title(page, "Session Loaded")
        
        # Activate Vigilance
        PageMonitor.attach_listeners(page)

        # 2b. Clear any existing bets in the slip
        await clear_bet_slip(page)

        # 3. Extract balance
        balance = await extract_balance(page)
        print(f"  [Balance] Current balance: NGN {balance}")

        # 4. Process each day's predictions
        for target_date, day_predictions in sorted(predictions_by_date.items()):
            # Check browser/page state 
            if not page or page.is_closed():
                print("  [Fatal] Browser connection lost or page closed. Aborting cycle.")
                break

            print(f"\n--- Booking for Date: {target_date} ---")

            # Ensure we're on the main football page
            print("  [Navigation] Navigating to schedule...")
            try:
                await navigate_to_schedule(page)
                await log_page_title(page, "Navigated to Schedule")
                # await asyncio.sleep(5)  # Optimization: removed fixed sleep, reliance on navigate_to_schedule internal waits
            except Exception as nav_e:
                print(f"  [Error] Navigation failed for {target_date}: {nav_e}. Trying url navigation...")
                await page.goto("https://www.football.com/ng/m/sport/football", wait_until='domcontentloaded', timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
                await log_page_title(page, "Navigated (Fallback)")
                continue

            # Navigate to schedule and select date

            if not await select_target_date(page, target_date):
                print(f"[Info] Date {target_date} not available for selection. Skipping.")
                continue

            # Extract matches
            site_matches = await extract_league_matches(page, target_date)

            # Match with predictions
            matched_urls = await match_predictions_with_site(day_predictions, site_matches)

            # Place bets
            if matched_urls:
                await place_bets_for_matches(page, matched_urls, day_predictions, target_date)
            else:
                print(f"[Info] No bets selected for {target_date}.")
                continue
                
    except Exception as e:
        print(f"[FATAL BOOKING ERROR] {e}")
        if page:
            await log_error_state(page, "football_com_fatal", e)
    finally:
        if context:
            await context.close()

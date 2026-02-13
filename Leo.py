# Leo.py: The central orchestrator for the LeoBook system.
# Refactored for Clean Architecture (v2.7)
# This script is a pure orchestrator containing NO business logic.

import asyncio
import nest_asyncio
import os
import sys
from datetime import datetime as dt
from dotenv import load_dotenv
from playwright.async_api import async_playwright

# Apply nest_asyncio for nested loops
nest_asyncio.apply()

# Load environment variables
load_dotenv()

# Modular Imports
from Core.System.lifecycle import (
    log_state, log_audit_state, setup_terminal_logging, parse_args, state
)
from Core.System.telegram_bridge import start_telegram_listener
from Core.System.withdrawal_checker import (
    check_triggers, propose_withdrawal, calculate_proposed_amount, get_latest_win
)
from Data.Access.db_helpers import init_csvs, log_audit_event
from Modules.Flashscore.manager import run_flashscore_analysis, run_flashscore_offline_repredict
from Modules.FootballCom.fb_manager import run_football_com_booking
from Core.System.monitoring import run_chapter_3_oversight

# Configuration
CYCLE_WAIT_HOURS = 6
LOCK_FILE = "leo.lock"

async def main():
    """Main execution loop adhering to the 'Observe, Decide, Act' chapters."""
    # Singleton Check
    if os.path.exists(LOCK_FILE):
        try:
            with open(LOCK_FILE, "r") as f:
                old_pid = int(f.read().strip())
                import psutil
                if psutil.pid_exists(old_pid):
                    print(f"   [System Error] Leo is already running (PID: {old_pid}).")
                    sys.exit(1)
        except: pass

    with open(LOCK_FILE, "w") as f:
        f.write(str(os.getpid()))

    try:
        init_csvs()
        asyncio.create_task(start_telegram_listener())

        async with async_playwright() as p:
            while True:
                try:
                    state["cycle_count"] += 1
                    state["cycle_start_time"] = dt.now()
                    log_state(chapter="Cycle Start", action=f"Starting Cycle #{state['cycle_count']}")

                    # --- PROLOGUE: DATA ENRICHMENT ---
                    log_state(chapter="Prologue", action="Enriching Match Schedules")
                    from Scripts.enrich_all_schedules import enrich_all_schedules
                    try:
                        # Run enrichment with standings extraction
                        await enrich_all_schedules(extract_standings=True)
                    except Exception as e:
                        print(f"  [Error] Prologue failed: {e}")

                    # --- CHAPTER 0: REVIEW ---
                    log_state(chapter="Chapter 0", action="Reviewing Outcomes")
                    from Data.Access.review_outcomes import run_review_process
                    from Data.Access.prediction_accuracy import print_accuracy_report
                    try:
                        await run_review_process(p)
                        print_accuracy_report()
                    except Exception as e:
                        print(f"  [Error] Chapter 0 failed: {e}")

                    # --- CHAPTER 1A/B: EXTRACTION & PREDICTION ---
                    log_state(chapter="Chapter 1A", action="Data Extraction & Prediction")
                    await run_flashscore_analysis(p)
                    
                    # --- SYNC: PREDICTIONS TO CLOUD ---
                    log_state(chapter="Sync", action="Pushing Predictions to Supabase")
                    from Data.Access.sync_manager import run_predictions_sync
                    run_predictions_sync()

                    # --- CHAPTER 1C/2A: ODDS & BOOKING ---
                    log_state(chapter="Chapter 2A", action="Automated Booking")
                    await run_football_com_booking(p)
                    
                    # --- CHAPTER 2B: FUNDS & WITHDRAWAL ---
                    from Modules.FootballCom.navigator import extract_balance
                    try:
                        async with await p.chromium.launch(headless=True) as check_browser:
                            check_page = await check_browser.new_page()
                            state["current_balance"] = await extract_balance(check_page)
                        
                        if await check_triggers():
                            proposed_amount = calculate_proposed_amount(state["current_balance"], get_latest_win())
                            await propose_withdrawal(proposed_amount)
                    except Exception as e:
                        print(f"  [Warning] Balance/Withdrawal check failed: {e}")

                    # --- CHAPTER 3: MONITORING ---
                    log_state(chapter="Chapter 3", action="Running Oversight")
                    await run_chapter_3_oversight()

                    log_audit_event("CYCLE_COMPLETE", f"Cycle #{state['cycle_count']} finished.")
                    print(f"   [System] Cycle #{state['cycle_count']} finished at {dt.now().strftime('%H:%M:%S')}. Sleeping {CYCLE_WAIT_HOURS}h...")
                    await asyncio.sleep(CYCLE_WAIT_HOURS * 6) #reduced to 6s for quick pre depolyment analysis

                except Exception as e:
                    state["error_log"].append(f"{dt.now()}: {e}")
                    print(f"[ERROR] Main loop: {e}")
                    await asyncio.sleep(60)
    finally:
        if os.path.exists(LOCK_FILE): os.remove(LOCK_FILE)

async def main_offline_repredict():
    """Run offline reprediction."""
    print("    --- LEO: Offline Reprediction Mode ---      ")
    init_csvs()
    async with async_playwright() as p:
        try:
            from Data.Access.review_outcomes import run_review_process
            from Data.Access.prediction_accuracy import print_accuracy_report
            await run_review_process(p)
            print_accuracy_report()
            await run_flashscore_offline_repredict(p)
        except Exception as e:
            print(f"[ERROR] Offline repredict: {e}")

if __name__ == "__main__":
    args = parse_args()
    log_file, original_stdout, original_stderr = setup_terminal_logging(args)
    try:
        if args.offline_repredict: asyncio.run(main_offline_repredict())
        else: asyncio.run(main())
    except KeyboardInterrupt:
        print("\n   --- LEO: Shutting down. ---")
    finally:
        sys.stdout, sys.stderr = original_stdout, original_stderr
        log_file.close()

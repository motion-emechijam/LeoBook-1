#!/usr/bin/env python3
"""
Match Enrichment Pipeline: Process ALL schedules to extract missing data
Author: LeoBook Team
Date: 2026-02-13

Purpose:
  - Visit ALL match URLs in schedules.csv (22k+)
  - Extract team IDs, league IDs, final scores, crests, URLs
  - Upsert teams.csv and region_league.csv with ALL columns
  - (--standings) Click Standings tab, extract league table, save to standings.csv
  - (--backfill-predictions) Fix region_league/crest URLs in predictions.csv
  - Fix "Unknown" or "N/A" entries
  - Smart date/time parsing for merged datetime strings
  - ALL selectors loaded dynamically from knowledge.json

Usage:
  python Scripts/enrich_all_schedules.py [--limit N] [--dry-run] [--standings] [--backfill-predictions]
"""

import asyncio
import csv
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from playwright.async_api import Playwright, async_playwright, Browser
from Data.Access.db_helpers import (
    SCHEDULES_CSV, TEAMS_CSV, REGION_LEAGUE_CSV, STANDINGS_CSV, PREDICTIONS_CSV,
    save_team_entry, save_region_league_entry, save_schedule_entry,
    save_standings, backfill_prediction_entry
)
from Data.Access.outcome_reviewer import smart_parse_datetime
from Core.Browser.Extractors.standings_extractor import extract_standings_data, activate_standings_tab
from Modules.Flashscore.fs_utils import retry_extraction
from Core.Utils.constants import NAVIGATION_TIMEOUT, WAIT_FOR_LOAD_STATE_TIMEOUT

# Configuration
CONCURRENCY = 3  # Reduced for stability (prevents "Page crashed")
BATCH_SIZE = 50  # Process more matches per browser restart
KNOWLEDGE_PATH = Path(__file__).parent.parent / "Config" / "knowledge.json"

# Selective dynamic selectors will still be used but Core/ extracts will handle standings


def load_selectors() -> Dict[str, str]:
    """Load fs_match_page selectors from knowledge.json."""
    with open(KNOWLEDGE_PATH, 'r', encoding='utf-8') as f:
        knowledge = json.load(f)
    selectors = knowledge.get("fs_match_page", {})
    if not selectors:
        raise RuntimeError("fs_match_page selectors not found in knowledge.json")
    print(f"[INFO] Loaded {len(selectors)} selectors from knowledge.json (fs_match_page)")
    return selectors


async def _safe_attr(page, selector: str, attr: str) -> Optional[str]:
    """Safely query a selector and extract an attribute value."""
    try:
        el = await page.query_selector(selector)
        if el:
            val = await el.get_attribute(attr)
            return val.strip() if val else None
    except:
        pass
    return None


async def _safe_text(page, selector: str) -> Optional[str]:
    """Safely query a selector and extract inner text."""
    try:
        el = await page.query_selector(selector)
        if el:
            val = await el.inner_text()
            return val.strip() if val else None
    except:
        pass
    return None


def _id_from_href(href: str) -> Optional[str]:
    """Extract entity ID from a flashscore URL like /team/name/ABC123/."""
    if not href:
        return None
    parts = href.strip('/').split('/')
    return parts[-1] if len(parts) >= 2 else None


def _standardize_url(url: str) -> str:
    """Ensure flashscore URLs are absolute."""
    if not url:
        return ''
    if url.startswith('//'):
        return 'https:' + url
    if url.startswith('/'):
        return 'https://www.flashscore.com' + url
    return url


async def extract_match_enrichment(page, match_url: str, sel: Dict[str, str],
                                    extract_standings: bool = False) -> Optional[Dict]:
    """
    Extract team IDs, crests, URLs, league info, score, datetime, and optionally standings.
    """
    try:
        # Use retry for navigation
        async def _navigate():
            await page.goto(match_url, wait_until='domcontentloaded', timeout=NAVIGATION_TIMEOUT)
            await asyncio.sleep(1.0)
        
        await retry_extraction(_navigate)

        enriched = {}

        # --- HOME TEAM ---
        home_href = await _safe_attr(page, sel.get('home_name', ''), 'href')
        if home_href:
            enriched['home_team_id'] = _id_from_href(home_href)
            enriched['home_team_url'] = _standardize_url(home_href)
        home_name = await _safe_text(page, sel.get('home_name', ''))
        if home_name:
            enriched['home_team_name'] = home_name
        home_crest_src = await _safe_attr(page, sel.get('home_crest', ''), 'src')
        if home_crest_src:
            enriched['home_team_crest'] = _standardize_url(home_crest_src)

        # --- AWAY TEAM ---
        away_href = await _safe_attr(page, sel.get('away_name', ''), 'href')
        if away_href:
            enriched['away_team_id'] = _id_from_href(away_href)
            enriched['away_team_url'] = _standardize_url(away_href)
        away_name = await _safe_text(page, sel.get('away_name', ''))
        if away_name:
            enriched['away_team_name'] = away_name
        away_crest_src = await _safe_attr(page, sel.get('away_crest', ''), 'src')
        if away_crest_src:
            enriched['away_team_crest'] = _standardize_url(away_crest_src)

        # --- REGION + LEAGUE ---
        region_name = await _safe_text(page, sel.get('region_name', ''))
        if region_name:
            enriched['region'] = region_name

        region_flag_src = await _safe_attr(page, sel.get('region_flag_img', ''), 'src')
        if region_flag_src:
            enriched['region_flag'] = region_flag_src

        region_url_href = await _safe_attr(page, sel.get('region_url', ''), 'href')
        if region_url_href:
            enriched['region_url'] = _standardize_url(region_url_href)

        league_url_href = await _safe_attr(page, sel.get('league_url', ''), 'href')
        if league_url_href:
            enriched['league_url'] = _standardize_url(league_url_href)
            enriched['rl_id'] = _id_from_href(league_url_href)

        league_name_text = await _safe_text(page, sel.get('league_url', ''))
        if league_name_text:
            enriched['league'] = league_name_text

        if region_name and league_name_text:
            enriched['region_league'] = f"{region_name.upper()} - {league_name_text}"

        # --- FINAL SCORE ---
        home_score = await _safe_text(page, sel.get('final_score_home', ''))
        away_score = await _safe_text(page, sel.get('final_score_away', ''))
        if home_score:
            enriched['home_score'] = home_score
        if away_score:
            enriched['away_score'] = away_score

        # --- MATCH DATETIME ---
        try:
            dt_text = await _safe_text(page, sel.get('match_time', ''))
            if dt_text:
                date_part, time_part = smart_parse_datetime(dt_text)
                if date_part:
                    enriched['date'] = date_part
                if time_part:
                    enriched['match_time'] = time_part
        except:
            pass

        # --- STANDINGS (optional) ---
        if extract_standings:
            if await activate_standings_tab(page):
                standings_result = await retry_extraction(extract_standings_data, page)
                if standings_result:
                    enriched['_standings_data'] = standings_result

        return enriched if enriched else None

    except Exception as e:
        print(f"      [ERROR] Failed to enrich {match_url}: {e}")
        return None


async def process_match_task_isolated(browser: Browser, match: Dict, sel: Dict[str, str], extract_standings: bool) -> Dict:
    """Worker to enrich a single match within its own context."""
    context = await browser.new_context(
        viewport={'width': 1280, 'height': 720},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        ignore_https_errors=True
    )
    page = await context.new_page()
    try:
        enriched = await extract_match_enrichment(page, match['match_link'], sel, extract_standings)
        if enriched:
            match.update(enriched)
        return match
    finally:
        await context.close()


async def enrich_batch(playwright: Playwright, matches: List[Dict], batch_num: int,
                       sel: Dict[str, str], extract_standings: bool = False) -> List[Dict]:
    """Process a batch of matches with isolated contexts and throttled concurrency."""
    browser = await playwright.chromium.launch(
        headless=True,
        args=['--disable-gpu', '--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
    )
    
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def worker(match):
        async with semaphore:
            # Brief jitter/stagger to prevent simultaneous CPU bursts
            await asyncio.sleep(0.5)
            return await process_match_task_isolated(browser, match, sel, extract_standings)

    # Gather results for all matches in the batch
    results = await asyncio.gather(*(worker(m) for m in matches))
    
    await browser.close()
    return list(results)


from Data.Access.sync_manager import SyncManager

# ...

async def enrich_all_schedules(limit: Optional[int] = None, dry_run: bool = False,
                                extract_standings: bool = False,
                                backfill_predictions: bool = False):
    """
    Main enrichment pipeline.
    
    Args:
        limit: Process only first N matches (for testing)
        dry_run: If True, don't write to CSV files
        extract_standings: If True, also extract standings data
        backfill_predictions: If True, fix region_league/crests in predictions.csv
    """
    print("=" * 80)
    print("  MATCH ENRICHMENT PIPELINE")
    flags = []
    if extract_standings: flags.append("standings")
    if backfill_predictions: flags.append("backfill-predictions")
    print(f"  Mode: {' + '.join(flags) if flags else 'Standard'}")
    print(f"  Concurrency: {CONCURRENCY}")
    print(f"  Batch Size: {BATCH_SIZE}")
    print("=" * 80)

    # Initialize Sync Manager
    sync_manager = SyncManager()
    if not dry_run:
        await sync_manager.sync_on_startup()

    # Load selectors
    if not KNOWLEDGE_PATH.exists():
        print(f"[ERROR] Knowledge file not found at {KNOWLEDGE_PATH}")
        return

    with open(KNOWLEDGE_PATH, 'r', encoding='utf-8') as f:
        knowledge = json.load(f)
        sel = knowledge.get('fs_match_page', {})
    
    print(f"[INFO] Loaded {len(sel)} selectors from knowledge.json (fs_match_page)")

    # Load ALL matches
    with open(SCHEDULES_CSV, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        all_matches = list(reader)
    
    # Filter matches that need enrichment
    to_enrich = [
        m for m in all_matches
        if m.get('match_link') and (
            not m.get('home_team_id') or
            not m.get('away_team_id') or
            m.get('region_league') in ('Unknown', 'N/A', '') or
            len(m.get('match_time', '')) > 5 or  # Fix merged date-times "DD.MM.YYYY HH:MM"
            m.get('match_time') in ('Unknown', 'N/A', '')
        )
    ]

    if limit:
        to_enrich = to_enrich[:limit]

    print(f"[INFO] Total matches: {len(all_matches)}")
    print(f"[INFO] Matches to enrich: {len(to_enrich)}")

    if dry_run:
        print("[DRY-RUN] Simulating enrichment...")

    # Process in batches
    total_batches = (len(to_enrich) + BATCH_SIZE - 1) // BATCH_SIZE
    enriched_count = 0
    teams_added = set()
    leagues_added = set()
    standings_saved = 0
    predictions_backfilled = 0

    # Sync buffers
    sync_buffer_schedules = []
    sync_buffer_teams = []
    sync_buffer_leagues = []
    sync_buffer_standings = []

    async with async_playwright() as playwright:
        for batch_idx in range(0, len(to_enrich), BATCH_SIZE):
            batch = to_enrich[batch_idx:batch_idx + BATCH_SIZE]
            batch_num = (batch_idx // BATCH_SIZE) + 1

            print(f"\n[BATCH {batch_num}/{total_batches}] Processing {len(batch)} matches...")

            enriched_batch = await enrich_batch(playwright, batch, batch_num, sel, extract_standings)

            if not dry_run:
                # Save enriched data
                for match in enriched_batch:
                    # Update schedule
                    save_schedule_entry(match)
                    sync_buffer_schedules.append(match)

                    # Build rl_id for team -> league mapping
                    rl_id = match.get('rl_id', '')
                    region = match.get('region', '')
                    league = match.get('league', '')
                    if not rl_id and region and league:
                        rl_id = f"{region}_{league}".replace(' ', '_').replace('-', '_').upper()

                    # Upsert home team with ALL columns
                    if match.get('home_team_id'):
                        home_team_data = {
                            'team_id': match['home_team_id'],
                            'team_name': match.get('home_team_name', match.get('home_team', 'Unknown')),
                            'rl_ids': rl_id,
                            'team_crest': match.get('home_team_crest', ''),
                            'team_url': match.get('home_team_url', '')
                        }
                        save_team_entry(home_team_data)
                        teams_added.add(match['home_team_id'])
                        sync_buffer_teams.append(home_team_data)

                    # Upsert away team with ALL columns
                    if match.get('away_team_id'):
                        away_team_data = {
                            'team_id': match['away_team_id'],
                            'team_name': match.get('away_team_name', match.get('away_team', 'Unknown')),
                            'rl_ids': rl_id,
                            'team_crest': match.get('away_team_crest', ''),
                            'team_url': match.get('away_team_url', '')
                        }
                        save_team_entry(away_team_data)
                        teams_added.add(match['away_team_id'])
                        sync_buffer_teams.append(away_team_data)

                    # Upsert region_league with ALL columns
                    if rl_id:
                        league_data = {
                            'rl_id': rl_id,
                            'region': region,
                            'region_flag': match.get('region_flag', ''),
                            'region_url': match.get('region_url', ''),
                            'league': league,
                            'league_url': match.get('league_url', ''),
                            'league_crest': ''  # Not available on match page
                        }
                        save_region_league_entry(league_data)
                        leagues_added.add(rl_id)
                        sync_buffer_leagues.append(league_data)

                    # --- Save standings if extracted ---
                    standings_result = match.pop('_standings_data', None)
                    if standings_result:
                        s_data = standings_result.get('standings', [])
                        s_league = standings_result.get('region_league', 'Unknown')
                        s_url = standings_result.get('league_url', '')
                        if s_league == 'Unknown' and match.get('region_league'):
                            s_league = match['region_league']
                        if s_data and s_league != 'Unknown':
                            for row in s_data:
                                row['url'] = s_url or match.get('league_url', '')
                            save_standings(s_data, s_league)
                            standings_saved += len(s_data)
                            sync_buffer_standings.extend(s_data)

                    # --- Backfill prediction if requested ---
                    if backfill_predictions and match.get('fixture_id'):
                        region_league = match.get('region_league', '')
                        updates = {}
                        if region_league and region_league != 'Unknown':
                            updates['region_league'] = region_league
                        if match.get('home_team_crest'):
                            updates['home_crest_url'] = match['home_team_crest']
                        if match.get('away_team_crest'):
                            updates['away_crest_url'] = match['away_team_crest']
                        if match.get('match_link'):
                            updates['match_link'] = match['match_link']
                        if updates:
                            was_updated = backfill_prediction_entry(match['fixture_id'], updates)
                            if was_updated:
                                predictions_backfilled += 1
                                # We should sync updated predictions too.
                                # But backfill_prediction_entry doesn't return the full row.
                                # This is complex. For now, rely on sync-on-startup or nightly sync.

                    enriched_count += 1
                
                # --- PERIODIC SYNC (Every 10 batches) ---
                if batch_num % 10 == 0:
                    print(f"   [SYNC] Upserting buffered data to Supabase...")
                    if sync_buffer_schedules:
                        await sync_manager.batch_upsert('schedules', sync_buffer_schedules)
                        sync_buffer_schedules = []
                    if sync_buffer_teams:
                        await sync_manager.batch_upsert('teams', sync_buffer_teams)
                        sync_buffer_teams = []
                    if sync_buffer_leagues:
                        await sync_manager.batch_upsert('region_league', sync_buffer_leagues)
                        sync_buffer_leagues = []
                    if sync_buffer_standings:
                        await sync_manager.batch_upsert('standings', sync_buffer_standings)
                        sync_buffer_standings = []

            print(f"   [+] Enriched {len(enriched_batch)} matches")
            print(f"   [+] Teams: {len(teams_added)}, Leagues: {len(leagues_added)}")
            if extract_standings:
                print(f"   [+] Standings rows saved: {standings_saved}")
            if backfill_predictions:
                print(f"   [+] Predictions backfilled: {predictions_backfilled}")
        
        # --- FINAL SYNC ---
        if not dry_run:
            print(f"   [SYNC] Upserting remaining data to Supabase...")
            if sync_buffer_schedules:
                await sync_manager.batch_upsert('schedules', sync_buffer_schedules)
            if sync_buffer_teams:
                await sync_manager.batch_upsert('teams', sync_buffer_teams)
            if sync_buffer_leagues:
                await sync_manager.batch_upsert('region_league', sync_buffer_leagues)
            if sync_buffer_standings:
                await sync_manager.batch_upsert('standings', sync_buffer_standings)

    # Summary
    print("\n" + "=" * 80)
    print("  ENRICHMENT COMPLETE")
    print("=" * 80)
    print(f"  Total enriched:          {enriched_count}")
    print(f"  Teams updated:           {len(teams_added)}")
    print(f"  Leagues updated:         {len(leagues_added)}")
    if extract_standings:
        print(f"  Standings rows saved:    {standings_saved}")
    if backfill_predictions:
        print(f"  Predictions backfilled:  {predictions_backfilled}")

    if dry_run:
        print("\n[DRY-RUN] No files were modified")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description='Enrich all match schedules')
    parser.add_argument('--limit', type=int, help='Process only first N matches (for testing)')
    parser.add_argument('--dry-run', action='store_true', help='Simulate without writing files')
    parser.add_argument('--standings', action='store_true', help='Also extract standings data from Standings tab')
    parser.add_argument('--backfill-predictions', action='store_true', help='Fix region_league/crests in predictions.csv')
    args = parser.parse_args()

    asyncio.run(enrich_all_schedules(
        limit=args.limit,
        dry_run=args.dry_run,
        extract_standings=args.standings,
        backfill_predictions=args.backfill_predictions
    ))

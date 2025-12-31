"""
Matcher Module
Handles matching predictions.csv data with extracted Football.com matches using Gemini AI.
"""

import csv
import difflib
from typing import List, Dict, Optional
from datetime import datetime, timedelta

from pathlib import Path
from Helpers.DB_Helpers.db_helpers import PREDICTIONS_CSV, update_prediction_status
try:
    from Helpers.AI.llm_matcher import SemanticMatcher
    HAS_LLM = True
except ImportError:
    HAS_LLM = False
    print("  [Matcher] Warning: LLM dependencies not found. Falling back to simple fuzzy matching.")

# Import RapidFuzz for faster and more accurate fuzzy matching
try:
    from rapidfuzz import fuzz, process
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False
    print("  [Matcher] Warning: RapidFuzz not found. Falling back to difflib.")


async def filter_pending_predictions() -> List[Dict]:
    """Load and filter predictions that are pending booking."""
    pending_predictions = []
    csv_path = Path(PREDICTIONS_CSV)
    if csv_path.exists():
        with open(csv_path, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            pending_predictions = [row for row in reader if row.get('status') == 'pending']
    print(f"  [Matcher] Found {len(pending_predictions)} pending predictions.")
    return pending_predictions


def normalize_team_name(name: str) -> str:
    """Basic normalization: lower, strip, remove common suffixes/prefixes."""
    if not name:
        return ""
    name = name.lower().strip()
    # Remove common suffixes like FC, AFC, CF, etc.
    suffixes = ['fc', 'afc', 'cf', 'sc', 'ac', 'club', 'united', 'city', 'athletic']
    for suffix in suffixes:
        if name.endswith(' ' + suffix):
            name = name[:-len(suffix)-1].strip()
        elif name == suffix:
            name = ""
    return name


def calculate_similarity(str1: str, str2: str) -> float:
    """Calculate similarity using RapidFuzz (token_set_ratio) or fallback to difflib."""
    if not str1 or not str2:
        return 0.0
    norm1 = normalize_team_name(str1)
    norm2 = normalize_team_name(str2)
    if HAS_RAPIDFUZZ:
        return fuzz.token_set_ratio(norm1, norm2) / 100.0
    else:
        return difflib.SequenceMatcher(None, norm1, norm2).ratio()


def build_match_string(region_league: str, home: str, away: str, date: str, time: str) -> str:
    """
    Build a canonical full match string for holistic comparison:
    "Region - League: Home Team vs Away Team - Date - Time"
    """
    return f"{region_league}: {home} vs {away} - {date} - {time}".strip().lower()


def parse_match_datetime(date_str: str, time_str: str, is_site_format: bool = False) -> Optional[datetime]:
    """
    Parse date and time strings into a datetime object (assumed UTC for predictions, displayed UTC+1 for site).
    """
    if not date_str or not time_str:
        return None

    time_str = time_str.strip()
    date_str = date_str.strip()

    if is_site_format:
        if ',' not in time_str:
            return None
        try:
            parts = time_str.split(',', 1)
            site_date_part = parts[0].strip()   # e.g. "17 Dec"
            site_time_part = parts[1].strip()   # e.g. "20:30"

            year = datetime.strptime(date_str, "%d.%m.%Y").year

            dt_str = f"{site_date_part} {year} {site_time_part}"
            return datetime.strptime(dt_str, "%d %b %Y %H:%M")
        except (ValueError, IndexError):
            return None
    else:
        try:
            return datetime.strptime(f"{date_str} {time_str}", "%d.%m.%Y %H:%M")
        except ValueError:
            return None


async def match_predictions_with_site(day_predictions: List[Dict], site_matches: List[Dict]) -> Dict[str, str]:
    """
    Match predictions to site matches primarily by holistic string similarity on the full
    "Region - League: Home vs Away - Date - Time" descriptor, with datetime priority and optional LLM fallback.
    """
    # Filter out predictions for matches that have already started (with 5-minute grace)
    now_utc = datetime.utcnow()
    future_predictions = []
    for pred in day_predictions:
        pred_date = pred.get('date', '').strip()
        pred_time = pred.get('match_time', '').strip()
        pred_utc_dt = parse_match_datetime(pred_date, pred_time, is_site_format=False)
        if pred_utc_dt and pred_utc_dt > (now_utc - timedelta(minutes=5)):
            future_predictions.append(pred)

    if not future_predictions:
        print("  [Matcher] No future pending predictions found.")
        return {}

    day_predictions = future_predictions
    print(f"  [Matcher] Attempting to match {len(day_predictions)} future predictions.")

    if not site_matches:
        print("  [Matcher] No site matches provided.")
        return {}

    # Initialise LLM matcher once if available
    llm_matcher: Optional[SemanticMatcher] = None
    if HAS_LLM:
        try:
            llm_matcher = SemanticMatcher()
            print("  [Matcher] LLM Semantic Matcher initialized.")
        except Exception as e:
            print(f"  [Matcher] Failed to initialise LLM matcher: {e}")

    mapping: Dict[str, str] = {}
    used_site_urls = set()

    for pred in day_predictions:
        pred_id = str(pred.get('fixture_id', ''))
        pred_region_league = pred.get('region_league', '').strip()
        pred_home = pred.get('home_team', '').strip()
        pred_away = pred.get('away_team', '').strip()
        pred_date = pred.get('date', '').strip()
        pred_time = pred.get('match_time', '').strip()

        pred_full_str = build_match_string(pred_region_league, pred_home, pred_away, pred_date, pred_time)

        pred_utc_dt = parse_match_datetime(pred_date, pred_time, is_site_format=False)

        best_match: Optional[Dict] = None
        best_score = 0.0

        for site_match in site_matches:
            site_url = site_match.get('url', '')
            if not site_url or site_url in used_site_urls:
                continue

            site_region_league = site_match.get('league', '').strip()
            site_home = site_match.get('home', '').strip()
            site_away = site_match.get('away', '').strip()
            site_date = site_match.get('date', '').strip()
            site_time = site_match.get('time', '').strip()

            site_full_str = build_match_string(site_region_league, site_home, site_away, site_date, site_time)

            # Primary holistic similarity on the full combined string
            full_similarity = calculate_similarity(pred_full_str, site_full_str)

            # Datetime bonus (converted to UTC)
            site_display_dt = parse_match_datetime(site_date, site_time, is_site_format=True)
            site_utc_dt = (site_display_dt - timedelta(hours=1)) if site_display_dt else None

            time_bonus = 0.0
            if pred_utc_dt and site_utc_dt:
                time_diff_minutes = abs((pred_utc_dt - site_utc_dt).total_seconds()) / 60
                if time_diff_minutes <= 60:
                    time_bonus = 0.3
                elif time_diff_minutes <= 180:
                    time_bonus = 0.15

            base_score = full_similarity
            total_score = base_score + time_bonus

            # LLM boost for borderline cases
            llm_confirmed = False
            if llm_matcher and 0.65 <= base_score <= 0.90 and best_score < 0.9:
                print(f"    [LLM Check] Asking AI if prediction '{pred_home} vs {pred_away}' ({pred_region_league}) "
                      f"matches site '{site_home} vs {site_away}' ({site_region_league})")
                if llm_matcher.is_match(
                    f"{pred_home} vs {pred_away} in {pred_region_league}",
                    f"{site_home} vs {site_away} in {site_region_league}",
                    league=pred_region_league
                ):
                    print("      -> AI confirmed match!")
                    total_score = 0.99
                    llm_confirmed = True
                else:
                    print("      -> AI rejected match.")
                    total_score *= 0.4

            # Debug output
            if total_score > 0.6:
                time_info = f"Pred:{pred_utc_dt} SiteUTC:{site_utc_dt}" if pred_utc_dt and site_utc_dt else "Time parse failed"
                print(f"    [Candidate] FullStrSim: {full_similarity:.3f} | Total: {total_score:.3f} "
                      f"| {pred_home} vs {pred_away} ({pred_region_league}) ↔ {site_home} vs {site_away} ({site_region_league}) {time_info}")

            # Acceptance threshold
            if total_score > best_score and total_score >= 0.80:
                best_score = total_score
                best_match = site_match

        if best_match:
            mapping[pred_id] = best_match['url']
            used_site_urls.add(best_match['url'])
            time_str = pred_utc_dt.strftime('%Y-%m-%d %H:%M') if pred_utc_dt else 'N/A'
            print(f"  ✓ Matched prediction {pred_id} ({pred_home} vs {pred_away} @ {time_str}) "
                  f"→ {best_match.get('home')} vs {best_match.get('away')} (score {best_score:.3f})")
        else:
            print(f"  ✗ No reliable match found for prediction {pred_id} ({pred_home} vs {pred_away})")

    print(f"  [Matcher] Matching complete: {len(mapping)}/{len(day_predictions)} predictions matched.")
    return mapping
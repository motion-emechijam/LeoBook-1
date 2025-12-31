"""
Extractor Module
Handles extraction of leagues and matches from Football.com schedule pages.
"""

import asyncio
from typing import List, Dict

from playwright.async_api import Page

from Neo.selector_manager import SelectorManager
from Neo.intelligence import get_selector
from Helpers.constants import WAIT_FOR_LOAD_STATE_TIMEOUT
from .navigator import hide_overlays


async def extract_league_matches(page: Page, target_date: str) -> List[Dict]:
    """Iterates through all league headers, expands them, and extracts matches for a specific date."""
    print("  [Harvest] Starting 'Expand & Harvest' sequence...")
    await hide_overlays(page)
    all_matches = []
    
    league_header_sel = get_selector("fb_schedule_page", "league_header") or ".league-title-wrapper"
    match_card_sel = get_selector("fb_schedule_page", "match_rows") or ".match-card-section.match-card"
    match_url_sel = get_selector("fb_schedule_page", "match_url") or ".match-card > a.card-link"
    league_title_sel = get_selector("fb_schedule_page", "league_title_link") or ".league-link"
    
    # Match row specific selectors
    home_team_sel = get_selector("fb_schedule_page", "match_row_home_team_name") or ".home-team-name"
    away_team_sel = get_selector("fb_schedule_page", "match_row_away_team_name") or ".away-team-name"
    time_sel = get_selector("fb_schedule_page", "match_row_time") or ".time"

    try:
        league_headers = await page.locator(league_header_sel).all()
        print(f"  [Harvest] Found {len(league_headers)} league headers.")

        for i, header_locator in enumerate(league_headers):
            try:
                # Extract League Name
                league_element = header_locator.locator(league_title_sel).first
                if await league_element.is_visible():
                    league_text = (await league_element.inner_text(timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)).strip().replace('\n', ' - ')
                elif await header_locator.locator("h4").count() > 0:
                    league_text = (await header_locator.locator("h4").first.inner_text()).strip().replace('\n', ' - ')
                else:
                    league_text = f"Unknown League {i+1}"
                
                print(f"  -> Processing League {i+1}: {league_text}")

                if league_text.startswith("Simulated Reality League"):
                     print(f"    -> Skipping Simulated Reality League.")
                     continue

                # Expansion Logic
                if i == 0:
                     print(f"    -> {league_text}: Default open state (League 1). Skipping expand click.")
                     await asyncio.sleep(1.0)
                else:
                     # Click to expand - Primary Method with Force & JS Fallback
                     try:
                         target_el = league_element if await league_element.is_visible() else header_locator
                         await target_el.scroll_into_view_if_needed()
                         # Center the element to avoid bottom nav
                         await target_el.evaluate("el => el.scrollIntoView({block: 'center', inline: 'nearest'})")
                         await asyncio.sleep(0.5)
                         
                         await target_el.click(force=True, timeout=5000)
                     except Exception as click_error:
                         print(f"    [Harvest Warning] Standard click failed for {league_text}, trying JS click: {click_error}")
                         # Fallback to JS click which ignores overlays
                         target_el = league_element if await league_element.is_visible() else header_locator
                         await target_el.evaluate("el => el.click()")
                     
                     await asyncio.sleep(1.0)

                # Extraction Function (Reusable blob)
                matches_in_section = []
                matches_container = await header_locator.evaluate_handle('(el) => el.nextElementSibling')
                
                await asyncio.sleep(1.0)
                if matches_container:
                    matches_in_section = await matches_container.evaluate("""(container, args) => {
                        const { selectors, leagueText } = args;
                        const results = [];
                        const cards = container.querySelectorAll(selectors.match_card_sel);
                        cards.forEach(card => {
                            const homeEl = card.querySelector(selectors.home_team_sel);
                            const awayEl = card.querySelector(selectors.away_team_sel);
                            const timeEl = card.querySelector(selectors.time_sel);
                            const linkEl = card.querySelector(selectors.match_url_sel) || card.closest('a');
                            
                            if (homeEl && awayEl) {
                                results.push({ 
                                    home: homeEl.innerText.trim(), 
                                    away: awayEl.innerText.trim(), 
                                    time: timeEl ? timeEl.innerText.trim() : "N/A", 
                                    league: leagueText, 
                                    url: linkEl ? linkEl.href : "", 
                                    date: args.targetDate 
                                });
                            }
                        });
                        return results;
                    }""", {
                        "selectors": {
                            "match_card_sel": match_card_sel, 
                            "match_url_sel": match_url_sel,
                            "home_team_sel": home_team_sel,
                            "away_team_sel": away_team_sel,
                            "time_sel": time_sel
                        }, 
                        "leagueText": league_text, 
                        "targetDate": target_date
                    })

                # Retry Logic for non-first leagues if empty
                if not matches_in_section and i > 0:
                     print(f"    -> {league_text}: No matches found. Retrying expansion with alternative click (Header Text)...")
                     await page.locator(f'h4:has-text("{league_text}")').click()
                     await asyncio.sleep(1.0)
                     
                     # Re-evaluate
                     matches_container = await header_locator.evaluate_handle('(el) => el.nextElementSibling')
                     if matches_container:
                        matches_in_section = await matches_container.evaluate("""(container, args) => {
                            const { selectors, leagueText } = args;
                            const results = [];
                            const cards = container.querySelectorAll(selectors.match_card_sel);
                            cards.forEach(card => {
                                const homeEl = card.querySelector(selectors.home_team_sel);
                                const awayEl = card.querySelector(selectors.away_team_sel);
                                const timeEl = card.querySelector(selectors.time_sel);
                                const linkEl = card.querySelector(selectors.match_url_sel) || card.closest('a');
                                
                                if (homeEl && awayEl) {
                                    results.push({ 
                                        home: homeEl.innerText.trim(), 
                                        away: awayEl.innerText.trim(), 
                                        time: timeEl ? timeEl.innerText.trim() : "N/A", 
                                        league: leagueText, 
                                        url: linkEl ? linkEl.href : "", 
                                        date: args.targetDate 
                                    });
                                }
                            });
                            return results;
                        }""", {
                            "selectors": {
                                "match_card_sel": match_card_sel, 
                                "match_url_sel": match_url_sel,
                                "home_team_sel": home_team_sel,
                                "away_team_sel": away_team_sel,
                                "time_sel": time_sel
                            }, 
                            "leagueText": league_text, 
                            "targetDate": target_date
                        })

                # Result Handling
                if matches_in_section:
                    all_matches.extend(matches_in_section)
                    print(f"    -> {league_text}: Extracted {len(matches_in_section)} matches.")
                else:
                    print(f"    -> {league_text}: No matches found in section after attempts.")

                # Cleanup: Toggle to close
                print(f"    -> {league_text}: Closing section.")
                if await league_element.is_visible():
                     await league_element.click()
                else:
                     await header_locator.click()
                await asyncio.sleep(.5)

            except Exception as e:
                print(f"    [Harvest Error] Failed to process a league header: {e}")
    except Exception as e:
        print(f"  [Harvest] Overall harvesting error: {e}")

    print(f"  [Harvest] Total matches found: {len(all_matches)}")
    return all_matches
 

async def validate_match_data(matches: List[Dict]) -> List[Dict]:
    """Validate and clean extracted match data."""
    valid_matches = []
    for match in matches:
        if all(k in match for k in ['home', 'away', 'url', 'league']):
            # Basic validation
            if match['home'] and match['away'] and match['url']:
                valid_matches.append(match)
        else:
            print(f"    [Validation] Skipping invalid match: {match}")
    print(f"  [Validation] {len(valid_matches)}/{len(matches)} matches valid.")
    return valid_matches

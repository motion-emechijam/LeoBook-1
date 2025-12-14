# standings_extractor.py

import re
from playwright.async_api import Page, TimeoutError, ElementHandle
import re
from typing import Dict, Any, List
from Neo.intelligence import get_selector_auto, get_selector

async def extract_standings_data(page: Page, context: str = "standings_tab") -> Dict[str, Any]:
    """
    Extracts essential standings data: position, team, stats, and league info.
    """
    print("      [Extractor] Extracting Standings tab...")

    selectors = {
        "standings_row": get_selector(context, "standings_row") or ".ui-table__row",
        "standings_col_rank": get_selector(context, "standings_col_rank") or ".tableCellRank",
        "standings_col_team_name": get_selector(context, "standings_col_team_name") or ".tableCellParticipant__name",
        "standings_col_team_link": get_selector(context, "standings_col_team_link") or ".tableCellParticipant__name a",
        "standings_col_matches_played": get_selector(context, "standings_col_matches_played") or "td:nth-child(3)",
        "standings_col_wins": get_selector(context, "standings_col_wins") or "td:nth-child(4)",
        "standings_col_draws": get_selector(context, "standings_col_draws") or "td:nth-child(5)",
        "standings_col_losses": get_selector(context, "standings_col_losses") or "td:nth-child(6)",
        "standings_col_goals": get_selector(context, "standings_col_goals") or "td:nth-child(7)",
        "standings_col_points": get_selector(context, "standings_col_points") or ".tableCellPoints",
        "standings_col_form": get_selector(context, "standings_col_form") or ".tableCellForm",
        "meta_breadcrumb_country": get_selector(context, "meta_breadcrumb_country") or ".tournamentHeader__country",
        "meta_breadcrumb_league": get_selector(context, "meta_breadcrumb_league") or ".tournamentHeader__league a",
    }

    try:
        from Helpers.constants import WAIT_FOR_LOAD_STATE_TIMEOUT
        await page.wait_for_selector(selectors['standings_row'], timeout=WAIT_FOR_LOAD_STATE_TIMEOUT)
    except TimeoutError:
        print("      [Extractor] Warning: No standings table rows found.")
        return {"standings": [], "region_league": "Unknown", "parsing_errors": ["Standings table not found."]}

    js_code = r"""(selectors) => {
        const getText = (el, sel) => {
            const elem = el?.querySelector(sel);
            return elem ? elem.innerText?.trim() : null;
        };
        const getInt = (text) => {
            if (text === null) return null;
            const parsed = parseInt(text.replace(/[()]/g, ''), 10);
            return isNaN(parsed) ? null : parsed;
        };
        const getHref = (el, sel) => {
            const elem = el?.querySelector(sel);
            return elem ? elem.href : null;
        };

        const table = [];

        const rows = document.querySelectorAll(selectors.standings_row);
        if (rows.length === 0) {
            return { standings: [], region_league: 'Unknown', parsing_errors: ['No table rows found'] };
        }

        rows.forEach((row, index) => {
            const teamLink = getHref(row, selectors.standings_col_team_link);
            let teamId = null;
            if (teamLink) {
                const parts = teamLink.split('/').filter(p => p);
                const teamIndex = parts.indexOf('team');
                if (teamIndex !== -1 && parts.length > teamIndex + 2) {
                    teamId = parts[teamIndex + 2];
                }
            }

            let gf = null, ga = null;
            const goals = getText(row, selectors.standings_col_goals);
            if (goals && goals.includes(':')) {
                [gf, ga] = goals.split(':').map(p => {
                    const parsed = parseInt(p.trim());
                    return isNaN(parsed) ? null : parsed;
                });
            }

            const positionText = getText(row, selectors.standings_col_rank);
            const position = getInt(positionText) || (index + 1);

            const teamName = getText(row, selectors.standings_col_team_name);
            const team = teamName || `Team ${index + 1}`;

            table.push({
                position: position,
                team_name: team,
                team_id: teamId,
                played: getInt(getText(row, selectors.standings_col_matches_played)),
                wins: getInt(getText(row, selectors.standings_col_wins)),
                draws: getInt(getText(row, selectors.standings_col_draws)),
                losses: getInt(getText(row, selectors.standings_col_losses)),
                goals_for: gf,
                goals_against: ga,
                goal_difference: (gf !== null && ga !== null) ? (gf - ga) : null,
                points: getInt(getText(row, selectors.standings_col_points)),
                form: getText(row, selectors.standings_col_form),
            });
        });

        const country = document.querySelector(selectors.meta_breadcrumb_country)?.innerText?.trim()?.toUpperCase();
        const leagueEl = document.querySelector(selectors.meta_breadcrumb_league);
        const league = leagueEl?.innerText?.trim();
        const league_url = leagueEl?.href || null;
        const region_league = (country && league) ? `${country} - ${league}` : 'Unknown';

        return {
            standings: table,
            region_league: region_league,
            league_url: league_url,
            parsing_errors: []
        };
    }"""

    evaluation_result = await page.evaluate(js_code, selectors)

    team_count = len(evaluation_result.get('standings', []))
    league_name = evaluation_result.get('region_league', 'Unknown League')
    print(f"      [Extractor] Found {team_count} teams in standings for '{league_name}'.")

    return evaluation_result

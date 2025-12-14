"""
Page Analyzer Module
Handles webpage content analysis, data extraction, and league information processing.
Responsible for extracting structured data from web pages for prediction analysis.
"""

from typing import Dict, Any, List, Optional

from Helpers.Neo_Helpers.Managers.db_manager import knowledge_db


class PageAnalyzer:
    """Handles webpage content analysis and data extraction"""

    @staticmethod
    async def extract_league_data(
        page, context_key: str = "home_page"
    ) -> Dict[str, List[str]]:
        """Extract league and match data from webpage"""
        selectors = knowledge_db.get(context_key, {})
        if not selectors:
            return {"leagues": []}

        required = ["sport_container", "league_header", "match_rows"]
        if not all(k in selectors for k in required):
            return {"leagues": []}

        try:
            data = await page.evaluate(
                """(selectors) => {
                const container = document.querySelector(selectors.sport_container);
                if (!container) return { leagues: [] };

                const results = [];
                let currentLeagueStr = "";
                let currentMatches = [];

                const getText = (parent, sel) => {
                    if (!sel) return "";
                    const el = parent.querySelector(sel);
                    return el ? el.innerText.trim() : "";
                };

                const flushCurrentLeague = () => {
                    if (currentLeagueStr) {
                        const fullString = currentLeagueStr + (currentMatches.length ? ', ' + currentMatches.join(', ') : '');
                        results.push(fullString);
                    }
                };

                const children = Array.from(container.children);
                const flushCurrentLeague = () => {
                    if (currentLeagueStr) {
                        const fullString = currentLeagueStr + (currentMatches.length ? ', ' + currentMatches.join(', ') : '');
                        results.push(fullString);
                    }
                };

                children.forEach(el => {
                    let header = null;
                    if (el.matches(selectors.league_header)) header = el;
                    else if (el.querySelector(selectors.league_header)) header = el.querySelector(selectors.league_header);

                    if (header) {
                        flushCurrentLeague();
                        const country = getText(header, selectors.league_category) || "Unknown";
                        const name = getText(header, selectors.league_title_link) || "League";
                        const linkEl = header.querySelector(selectors.league_title_link);
                        const href = linkEl ? linkEl.href : "";

                        currentLeagueStr = `${country}: ${name}, ${href}`;
                        currentMatches = [];
                    }
                    else if (el.matches(selectors.match_rows)) {
                        if (currentLeagueStr) {
                            const linkEl = selectors.event_row_link ?
                                       el.querySelector(selectors.event_row_link) :
                                       el.querySelector('a');
                            if (linkEl && linkEl.href) currentMatches.push(linkEl.href);
                        }
                    }
                });

                flushCurrentLeague();
                return { leagues: results };
            }""",
                selectors,
            )

            return data

        except Exception as e:
            print(f"    [EXTRACT ERROR] Failed to extract data: {e}")
            return {"leagues": []}

    @staticmethod
    async def get_league_url(page) -> str:
        """Extract league URL from match page"""
        try:
            # Look for breadcrumb links to league
            league_link_sel = "a[href*='/football/'][href$='/']"
            league_link = page.locator(league_link_sel).first
            href = await league_link.get_attribute('href', timeout=2000)
            if href:
                return href
        except:
            pass
        return ""

    @staticmethod
    async def get_final_score(page) -> str:
        """Extract final score from match page"""
        try:
            # Import here to avoid circular imports
            from .selector_manager import SelectorManager

            # Check Status
            status_selector = await SelectorManager.get_selector_auto(page, "match_page", "meta_match_status")
            if not status_selector:
                status_selector = "div.fixedHeaderDuel__detailStatus"

            try:
                status_text = await page.locator(status_selector).inner_text(timeout=3000)
            except:
                status_text = "finished"

            if "finished" not in status_text.lower() and "aet" not in status_text.lower() and "pen" not in status_text.lower():
                return "NOT_FINISHED"

            # Extract Score
            home_score_sel = await SelectorManager.get_selector_auto(page, "match_page", "header_score_home")
            if not home_score_sel:
                home_score_sel = "div.detailScore__wrapper > span:nth-child(1)"

            away_score_sel = await SelectorManager.get_selector_auto(page, "match_page", "header_score_away")
            if not away_score_sel:
                away_score_sel = "div.detailScore__wrapper > span:nth-child(3)"

            home_score = await page.locator(home_score_sel).first.inner_text(timeout=2000)
            away_score = await page.locator(away_score_sel).first.inner_text(timeout=2000)

            final_score = f"{home_score.strip() if home_score else ''}-{away_score.strip() if away_score else ''}"
            return final_score

        except Exception as e:
            print(f"    [SCORE ERROR] Failed to extract score: {e}")
            return "Error"

    @staticmethod
    async def extract_match_metadata(page, context: str = "match_page") -> Dict[str, Any]:
        """Extract comprehensive match metadata"""
        metadata = {}

        try:
            # Import here to avoid circular imports
            from .selector_manager import SelectorManager

            # Extract basic match info
            selectors_to_try = {
                "home_team": "header_home_name",
                "away_team": "header_away_name",
                "match_time": "meta_match_time",
                "match_status": "meta_match_status",
                "league_country": "meta_breadcrumb_country",
                "league_name": "meta_breadcrumb_league"
            }

            for field, selector_key in selectors_to_try.items():
                selector = await SelectorManager.get_selector_auto(page, context, selector_key)
                if selector:
                    try:
                        element = page.locator(selector).first
                        if await element.count() > 0:
                            text = await element.inner_text(timeout=2000)
                            metadata[field] = text.strip()
                    except:
                        pass

            # Extract score if match is finished
            if metadata.get("match_status", "").lower() == "finished":
                score = await PageAnalyzer.get_final_score(page)
                if score not in ["Error", "NOT_FINISHED"]:
                    metadata["final_score"] = score

        except Exception as e:
            print(f"    [METADATA ERROR] Failed to extract match metadata: {e}")

        return metadata

    @staticmethod
    async def analyze_page_structure(page, context: str = "generic") -> Dict[str, Any]:
        """Analyze overall page structure and identify key elements"""
        structure = {
            "has_navigation": False,
            "has_content": False,
            "has_forms": False,
            "has_buttons": False,
            "has_links": False,
            "estimated_content_size": 0
        }

        try:
            # Quick structural analysis
            nav_count = await page.locator("nav, [role='navigation'], .nav, .navbar").count()
            structure["has_navigation"] = nav_count > 0

            content_count = await page.locator("main, .content, .main, article, section").count()
            structure["has_content"] = content_count > 0

            form_count = await page.locator("form").count()
            structure["has_forms"] = form_count > 0

            button_count = await page.locator("button").count()
            structure["has_buttons"] = button_count > 0

            link_count = await page.locator("a").count()
            structure["has_links"] = link_count > 0

            # Estimate content size
            body_text = await page.locator("body").inner_text()
            structure["estimated_content_size"] = len(body_text) if body_text else 0

        except Exception as e:
            print(f"    [STRUCTURE ERROR] Failed to analyze page structure: {e}")

        return structure

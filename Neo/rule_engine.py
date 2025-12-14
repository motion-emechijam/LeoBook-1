"""
Rule Engine Module
Core rule-based prediction engine for LeoBook.
Handles main analysis combining rules, xG, ML, and market selection.
"""

from typing import List, Dict, Any
from datetime import datetime, timedelta
import numpy as np

from .learning_engine import LearningEngine
from .ml_model import MLModel
from .tag_generator import TagGenerator
from .goal_predictor import GoalPredictor
from .betting_markets import BettingMarkets


class RuleEngine:
    @staticmethod
    def analyze(vision_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        MAIN PREDICTION ENGINE — Returns full market predictions
        """
        h2h_data = vision_data.get("h2h_data", {})
        standings = vision_data.get("standings", [])
        home_team = h2h_data.get("home_team")
        away_team = h2h_data.get("away_team")

        if not home_team or not away_team:
            return {"type": "SKIP", "confidence": "Low", "reason": "Missing teams"}

        home_form = [m for m in h2h_data.get("home_last_10_matches", []) if m][:10]
        away_form = [m for m in h2h_data.get("away_last_10_matches", []) if m][:10]
        h2h_raw = h2h_data.get("head_to_head", [])

        # Filter H2H to last ~18 months
        cutoff = datetime.now() - timedelta(days=540)
        h2h = []
        for m in h2h_raw:
            if not m:
                continue
            try:
                date_str = m.get("date", "")
                if date_str:
                    if "-" in date_str and len(date_str.split("-")[0]) == 4:
                        d = datetime.strptime(date_str, "%Y-%m-%d")
                    else:
                        d = datetime.strptime(date_str, "%d.%m.%Y")
                    if d >= cutoff:
                        h2h.append(m)
            except:
                h2h.append(m)  # keep if date parse fails

        # Generate all tags using TagGenerator
        home_tags = TagGenerator.generate_form_tags(home_form, home_team, standings)
        away_tags = TagGenerator.generate_form_tags(away_form, away_team, standings)
        h2h_tags = TagGenerator.generate_h2h_tags(h2h, home_team, away_team)
        standings_tags = TagGenerator.generate_standings_tags(standings, home_team, away_team)

        # Goal distribution & probabilities using GoalPredictor (moved early)
        home_dist = GoalPredictor.predict_goals_distribution(home_form, home_team, True)
        away_dist = GoalPredictor.predict_goals_distribution(away_form, away_team, False)

        home_xg = sum(float(k.replace("3+", "3.5")) * v for k, v in home_dist["goals_scored"].items())
        away_xg = sum(float(k.replace("3+", "3.5")) * v for k, v in away_dist["goals_scored"].items())

        # Prepare ML features
        ml_features = MLModel.prepare_features(vision_data)
        ml_prediction = MLModel.predict(ml_features) if ml_features else {"confidence": 0.5, "prediction": "UNKNOWN"}

        # Load learned weights
        weights = LearningEngine.load_weights()

        # Weighted rule voting using learned weights
        home_score = away_score = draw_score = over25_score = 0
        reasoning = []

        # Incorporate xG into voting early
        if home_xg > away_xg + 0.5:
            home_score += weights.get("xg_advantage", 3); reasoning.append("Home xG advantage")
        elif away_xg > home_xg + 0.5:
            away_score += weights.get("xg_advantage", 3); reasoning.append("Away xG advantage")
        elif abs(home_xg - away_xg) < 0.3:
            draw_score += weights.get("xg_draw", 2); reasoning.append("Close xG suggests draw")

        home_slug = home_team.replace(" ", "_").upper()
        away_slug = away_team.replace(" ", "_").upper()

        # H2H signals with learned weights
        if any(t.startswith(f"{home_slug}_WINS_H2H") for t in h2h_tags):
            home_score += weights.get("h2h_home_win", 3); reasoning.append("H2H home strong")
        if any(t.startswith(f"{away_slug}_WINS_H2H") for t in h2h_tags):
            away_score += weights.get("h2h_away_win", 3); reasoning.append("H2H away strong")
        if any(t.startswith("H2H_D") for t in h2h_tags):
            draw_score += weights.get("h2h_draw", 4); reasoning.append("H2H drawish")
        if any(t in h2h_tags for t in ["H2H_O25", "H2H_O25_third"]):
            over25_score += weights.get("h2h_over25", 3)

        # Standings signals with learned weights
        if f"{home_slug}_TOP3" in standings_tags and f"{away_slug}_BOTTOM5" in standings_tags:
            home_score += weights.get("standings_top_vs_bottom", 6); reasoning.append("Top vs Bottom")
        if f"{away_slug}_TOP3" in standings_tags and f"{home_slug}_BOTTOM5" in standings_tags:
            away_score += weights.get("standings_top_vs_bottom", 6); reasoning.append("Top vs Bottom")
        if f"{home_slug}_TABLE_ADV8+" in standings_tags: home_score += weights.get("standings_table_advantage", 3)
        if f"{away_slug}_TABLE_ADV8+" in standings_tags: away_score += weights.get("standings_table_advantage", 3)
        if f"{home_slug}_GD_POS_STRONG" in standings_tags: home_score += weights.get("standings_gd_strong", 2); reasoning.append(f"{home_team} strong GD")
        if f"{away_slug}_GD_POS_STRONG" in standings_tags: away_score += weights.get("standings_gd_strong", 2); reasoning.append(f"{away_team} strong GD")
        if f"{home_slug}_GD_NEG_WEAK" in standings_tags: away_score += weights.get("standings_gd_weak", 2); reasoning.append(f"{home_team} weak GD")
        if f"{away_slug}_GD_NEG_WEAK" in standings_tags: home_score += weights.get("standings_gd_weak", 2); reasoning.append(f"{away_team} weak GD")

        # Form signals (goal-centric) with learned weights
        if f"{home_slug}_FORM_S2+" in home_tags: home_score += weights.get("form_score_2plus", 4); over25_score += 2; reasoning.append(f"{home_team} scores 2+")
        if f"{away_slug}_FORM_S2+" in away_tags: away_score += weights.get("form_score_2plus", 4); over25_score += 2; reasoning.append(f"{away_team} scores 2+")
        if f"{home_slug}_FORM_S3+" in home_tags: home_score += weights.get("form_score_3plus", 2); over25_score += 1
        if f"{away_slug}_FORM_S3+" in away_tags: away_score += weights.get("form_score_3plus", 2); over25_score += 1

        if f"{away_slug}_FORM_C2+" in away_tags: home_score += weights.get("form_concede_2plus", 4); over25_score += 2; reasoning.append(f"{away_team} concedes 2+")
        if f"{home_slug}_FORM_C2+" in home_tags: away_score += weights.get("form_concede_2plus", 4); over25_score += 2; reasoning.append(f"{home_team} concedes 2+")

        if f"{home_slug}_FORM_SNG" in home_tags: away_score += weights.get("form_no_score", 5); reasoning.append(f"{home_team} fails to score")
        if f"{away_slug}_FORM_SNG" in away_tags: home_score += weights.get("form_no_score", 5); reasoning.append(f"{away_team} fails to score")

        if f"{home_slug}_FORM_CS" in home_tags: home_score += weights.get("form_clean_sheet", 5); reasoning.append(f"{home_team} strong defense (CS)")
        if f"{away_slug}_FORM_CS" in away_tags: away_score += weights.get("form_clean_sheet", 5); reasoning.append(f"{away_team} strong defense (CS)")

        if any("vs_top" in t.lower() and "_w" in t.lower() for t in home_tags): home_score += weights.get("form_vs_top_win", 3); reasoning.append("Beats top teams")
        if any("vs_top" in t.lower() and "_w" in t.lower() for t in away_tags): away_score += weights.get("form_vs_top_win", 3); reasoning.append("Beats top teams")

        # Calculate probabilities and scores from distributions


        keys = ["0", "1", "2", "3+"]
        btts_prob = sum(home_dist["goals_scored"].get(h,0) * away_dist["goals_scored"].get(a,0)
                        for h in keys for a in keys if h != "0" and a != "0")

        over25_prob = sum(home_dist["goals_scored"].get(h,0) * away_dist["goals_scored"].get(a,0)
                          for h in keys for a in keys
                          if int(h.replace("3+", "3")) + int(a.replace("3+", "3")) > 2)

        # Top correct scores
        scores = []
        for hg in "01233+":
            for ag in "01233+":
                p = home_dist["goals_scored"].get(hg, 0) * away_dist["goals_scored"].get(ag, 0)
                if p > 0.03:
                    scores.append({"score": f"{hg.replace('3+', '3+')}-{ag.replace('3+', '3+')}", "prob": round(p, 3)})
        scores.sort(key=lambda x: x["prob"], reverse=True)

        # Final decision logic
        prediction = "SKIP"
        confidence = "Low"

        if not reasoning:
            return {
                "type": "SKIP",
                "confidence": "Low",
                "reason": ["No strong signal"],
                "xg_home": round(home_xg, 2),
                "xg_away": round(away_xg, 2),
                "btts": "YES" if btts_prob > 0.6 else "NO" if btts_prob < 0.4 else "50/50",
                "over_2.5": "YES" if over25_prob > 0.65 else "NO" if over25_prob < 0.45 else "50/50",
                "best_score": scores[0]["score"] if scores else "1-1",
                "top_scores": scores[:5],
                "home_tags": home_tags,
                "away_tags": away_tags,
                "h2h_tags": h2h_tags,
                "standings_tags": standings_tags,
                "h2h_n": len(h2h),
                "home_form_n": len(home_form),
                "away_form_n": len(away_form),
            }

        # Determine base confidence
        if draw_score > max(home_score, away_score) and draw_score >= 4:
            prediction = "DRAW"
            base_confidence = "High" if draw_score >= 6 else "Medium"
        elif home_score > away_score + 3:
            prediction = "HOME_WIN"
            base_confidence = "Very High" if home_score >= 12 else "High"
            if over25_prob > 0.65:
                prediction = "HOME_WIN_AND_OVER_2.5"
        elif away_score > home_score + 3:
            prediction = "AWAY_WIN"
            base_confidence = "Very High" if away_score >= 12 else "High"
            if over25_prob > 0.65:
                prediction = "AWAY_WIN_AND_OVER_2.5"
        elif over25_prob > 0.75:
            prediction = "OVER_2.5"
            base_confidence = "Very High" if over25_prob > 0.85 else "High"
        else:
            base_confidence = "Low"

        # Apply learned confidence calibration
        confidence_calibration = weights.get("confidence_calibration", {})
        calibrated_score = confidence_calibration.get(base_confidence, 0.5)

        # Adjust confidence based on calibration
        if calibrated_score > 0.7:
            confidence = "Very High"
        elif calibrated_score > 0.55:
            confidence = "High"
        elif calibrated_score > 0.45:
            confidence = "Medium"
        else:
            confidence = "Low"

        # Alignment check: Skip if prediction opposes xG significantly
        if prediction.startswith("HOME_WIN") and away_xg > home_xg + 0.5:
            prediction = "SKIP"
            confidence = "Low"
            reasoning.append("xG opposes home win")
        elif prediction.startswith("AWAY_WIN") and home_xg > away_xg + 0.5:
            prediction = "SKIP"
            confidence = "Low"
            reasoning.append("xG opposes away win")
        elif prediction == "DRAW" and abs(home_xg - away_xg) > 1.0:
            prediction = "SKIP"
            confidence = "Low"
            reasoning.append("xG opposes draw")

        # Incorporate ML confidence if available
        final_confidence = confidence
        if ml_prediction["prediction"] != "UNKNOWN":
            ml_confidence_score = ml_prediction["confidence"]
            # Blend rule-based and ML confidence
            blended_confidence = (calibrated_score + ml_confidence_score) / 2

            if blended_confidence > 0.7:
                final_confidence = "Very High"
            elif blended_confidence > 0.55:
                final_confidence = "High"
            elif blended_confidence > 0.45:
                final_confidence = "Medium"
            else:
                final_confidence = "Low"

        # Generate comprehensive betting market predictions using BettingMarkets
        betting_markets = BettingMarkets.generate_betting_market_predictions(
            home_team, away_team, home_score, away_score, draw_score, btts_prob, over25_prob,
            scores, home_xg, away_xg, reasoning
        )

        # PRIORITIZE XG ALIGNMENT: Select predictions that align with expected goals
        xg_diff = home_xg - away_xg

        if xg_diff > 0.8:
            if home_score > away_score + 3 and "1X2" in betting_markets:
                best_prediction = betting_markets["1X2"]
                if best_prediction["market_prediction"] == "Draw":
                    best_prediction = betting_markets.get("double_chance", best_prediction)
            else:
                best_prediction = betting_markets.get("double_chance", betting_markets.get("btts", list(betting_markets.values())[0]))

        elif xg_diff < -0.8:
            if away_score > home_score + 3 and "1X2" in betting_markets:
                best_prediction = betting_markets["1X2"]
                if best_prediction["market_prediction"] == "Draw":
                    best_prediction = betting_markets.get("double_chance", best_prediction)
            else:
                best_prediction = betting_markets.get("double_chance", betting_markets.get("btts", list(betting_markets.values())[0]))

        else:
            xg_aligned_markets = ["btts", "over_under", "goal_range", "draw_no_bet"]
            max_confidence = 0
            best_prediction = betting_markets.get("btts", list(betting_markets.values())[0])

            for market_key in xg_aligned_markets:
                if market_key in betting_markets:
                    confidence = betting_markets[market_key].get("confidence_score", 0)
                    if confidence > max_confidence:
                        max_confidence = confidence
                        best_prediction = betting_markets[market_key]

        # Format prediction with market context for clarity
        market_type_short = best_prediction["market_type"].split("(")[0].strip()
        prediction_text = best_prediction["market_prediction"]

        if prediction_text in ["Yes", "No"] and "BTTS" in market_type_short:
            formatted_prediction = f"BTTS {prediction_text}"
        elif prediction_text in ["Yes", "No"]:
            formatted_prediction = f"{market_type_short} {prediction_text}"
        else:
            formatted_prediction = prediction_text

        return {
            "type": formatted_prediction,
            "market_type": best_prediction["market_type"],
            "confidence": final_confidence,
            "reason": reasoning[:3],
            "xg_home": round(home_xg, 2),
            "xg_away": round(away_xg, 2),
            "btts": "YES" if btts_prob > 0.6 else "NO" if btts_prob < 0.4 else "50/50",
            "over_2.5": "YES" if over25_prob > 0.65 else "NO" if over25_prob < 0.45 else "50/50",
            "best_score": scores[0]["score"] if scores else "1-1",
            "top_scores": scores[:5],
            "home_tags": home_tags,
            "away_tags": away_tags,
            "h2h_tags": h2h_tags,
            "standings_tags": standings_tags,
            "ml_confidence": ml_prediction.get("confidence", 0.5),
            "betting_markets": betting_markets,
            "h2h_n": len(h2h),
            "home_form_n": len(home_form),
            "away_form_n": len(away_form),
        }

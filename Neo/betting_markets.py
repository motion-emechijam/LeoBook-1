"""
Betting Markets Module
Generates predictions for comprehensive betting markets with a focus on safety and certainty.
"""

from typing import List, Dict, Any

class BettingMarkets:
    """Generates predictions for various betting markets"""

    @staticmethod
    def generate_betting_market_predictions(
        home_team: str, away_team: str, home_score: float, away_score: float, draw_score: float,
        btts_prob: float, over25_prob: float, scores: List[Dict], home_xg: float, away_xg: float,
        reasoning: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Generate predictions for comprehensive betting markets.
        Returns a dictionary of market predictions with confidence scores.
        """
        predictions = {}

        # Helper function to calculate confidence score
        def calc_confidence(base_score: float, threshold: float = 0.5) -> float:
            return min(base_score / threshold, 1.0) if base_score > threshold else base_score / threshold * 0.5

        # Calculate SAFE metrics
        # Over 1.5 Probability using top scores
        over15_prob = 0.0
        total_prob_analyzed = 0.0
        if scores:
            for s in scores:
                try:
                    score_str = s['score']
                    h, a = score_str.split('-')
                    # handle 3+
                    h = 3.5 if '3+' in h else float(h)
                    a = 3.5 if '3+' in a else float(a)
                    total_prob_analyzed += s['prob']
                    if h + a > 1.5:
                        over15_prob += s['prob']
                except: pass
            
            # Normalize if we only looked at top N scores
            if total_prob_analyzed > 0:
                over15_prob = over15_prob / total_prob_analyzed
            else:
                over15_prob = min(over25_prob + 0.2, 0.95) # Fallback heuristic
        else:
             over15_prob = min(over25_prob + 0.2, 0.95)

        # 1. Full Time Result (1X2)
        max_score = max(home_score, away_score, draw_score)
        if draw_score == max_score:
            predictions["1X2"] = {
                "market_type": "Full Time Result (1X2)",
                "market_prediction": "Draw",
                "confidence_score": calc_confidence(draw_score, 6),
                "reason": "Draw most likely outcome"
            }
        elif home_score == max_score:
            predictions["1X2"] = {
                "market_type": "Full Time Result (1X2)",
                "market_prediction": f"{home_team} to win",
                "confidence_score": calc_confidence(home_score, 8),
                "reason": f"{home_team} favored to win"
            }
        else:
            predictions["1X2"] = {
                "market_type": "Full Time Result (1X2)",
                "market_prediction": f"{away_team} to win",
                "confidence_score": calc_confidence(away_score, 8),
                "reason": f"{away_team} favored to win"
            }

        # 2. Double Chance
        if home_score + draw_score > away_score + 2:
            base_conf = calc_confidence((home_score + draw_score) / 2, 5) # Lower threshold for safe bet
            # Reduce confidence if xG strongly opposes (away favored)
            if away_xg > home_xg + 0.5:
                base_conf *= 0.7  # Reduce by 30%
            
            predictions["double_chance"] = {
                "market_type": "Double Chance",
                "market_prediction": f"{home_team} or Draw",
                "confidence_score": base_conf,
                "reason": f"{home_team} unlikely to lose"
            }
        elif away_score + draw_score > home_score + 2:
            base_conf = calc_confidence((away_score + draw_score) / 2, 5)
            # Reduce confidence if xG strongly opposes (home favored)
            if home_xg > away_xg + 0.5:
                base_conf *= 0.7  # Reduce by 30%
            
            predictions["double_chance"] = {
                "market_type": "Double Chance",
                "market_prediction": f"{away_team} or Draw",
                "confidence_score": base_conf,
                "reason": f"{away_team} unlikely to lose"
            }
        else:
            predictions["double_chance"] = {
                "market_type": "Double Chance",
                "market_prediction": f"{home_team} or {away_team}",
                "confidence_score": calc_confidence(max(home_score, away_score), 4),
                "reason": "Draw unlikely (12)"
            }

        # 3. Draw No Bet (Less safe than DC, safer than 1X2)
        if home_score > away_score + 3:
            predictions["draw_no_bet"] = {
                "market_type": "Draw No Bet",
                "market_prediction": f"{home_team} to win (DNB)",
                "confidence_score": calc_confidence(home_score - away_score, 3),
                "reason": f"{home_team} clear favorite"
            }
        elif away_score > home_score + 3:
            predictions["draw_no_bet"] = {
                "market_type": "Draw No Bet",
                "market_prediction": f"{away_team} to win (DNB)",
                "confidence_score": calc_confidence(away_score - home_score, 3),
                "reason": f"{away_team} clear favorite"
            }

        # 4. BTTS (Both Teams To Score)
        predictions["btts"] = {
            "market_type": "Both Teams To Score (BTTS)",
            "market_prediction": "Yes" if btts_prob > 0.5 else "No",
            "confidence_score": btts_prob if btts_prob > 0.5 else 1 - btts_prob,
            "reason": f"BTTS probability: {btts_prob:.2f}"
        }

        # 5. Over/Under Markets (Safety Hierarchy)
        # Safe Option: Over 1.5
        if over15_prob > 0.75:
            predictions["over_1.5"] = {
               "market_type": "Over/Under 1.5 Goals",
               "market_prediction": "Over 1.5",
               "confidence_score": over15_prob,
               "reason": "Safe goal expectation"
            }
        
        # Standard Option: Over 2.5
        if over25_prob > 0.65:
            predictions["over_under"] = {
                "market_type": "Over/Under 2.5 Goals",
                "market_prediction": "Over 2.5",
                "confidence_score": over25_prob,
                "reason": f"High goal expectation: {home_xg + away_xg:.1f}"
            }
        elif over25_prob < 0.35:
            predictions["over_under"] = {
                "market_type": "Over/Under 2.5 Goals",
                "market_prediction": "Under 2.5",
                "confidence_score": 1 - over25_prob,
                "reason": f"Low goal expectation: {home_xg + away_xg:.1f}"
            }

        # 6. Team Goals (Safe Options)
        if home_xg > 1.3:
            predictions["home_over_0.5"] = {
                "market_type": "Home Team Goals",
                "market_prediction": f"{home_team} Over 0.5",
                "confidence_score": 0.85, # Generally very high if xG > 1.3
                "reason": f"{home_team} expected to score"
            }
        if away_xg > 1.3:
            predictions["away_over_0.5"] = {
                "market_type": "Away Team Goals",
                "market_prediction": f"{away_team} Over 0.5",
                "confidence_score": 0.85, 
                "reason": f"{away_team} expected to score"
            }

        # 7. Winner and BTTS (Risky)
        if home_score > away_score + 2 and btts_prob > 0.6:
            predictions["winner_btts"] = {
                "market_type": "Final Result & BTTS",
                "market_prediction": f"{home_team} to win & BTTS Yes",
                "confidence_score": min(home_score / 12, btts_prob) * 0.9, # Discount for combined risk
                "reason": f"{home_team} likely to win with both teams scoring"
            }
        elif away_score > home_score + 2 and btts_prob > 0.6:
            predictions["winner_btts"] = {
                "market_type": "Final Result & BTTS",
                "market_prediction": f"{away_team} to win & BTTS Yes",
                "confidence_score": min(away_score / 12, btts_prob) * 0.9,
                "reason": f"{away_team} likely to win with both teams scoring"
            }

        return predictions

    @staticmethod
    def select_best_market(predictions: Dict[str, Dict], risk_preference: str = "medium") -> Dict[str, Any]:
        """
        Select the best market based on confidence and risk preference.
        RISK_PREFERENCE: 'conservative' (Safety First), 'medium', 'aggressive'
        """
        if not predictions:
            return {}

        # 1. Prioritize Very High Confidence
        very_high_conf = [m for m in predictions.values() if m["confidence_score"] >= 0.8]
        if very_high_conf:
             # Sort by confidence
             very_high_conf.sort(key=lambda x: x["confidence_score"], reverse=True)
             return {
                 "market_key": "best_safe",
                 "market_type": very_high_conf[0]["market_type"],
                 "prediction": very_high_conf[0]["market_prediction"],
                 "confidence": very_high_conf[0]["confidence_score"],
                 "reason": very_high_conf[0]["reason"]
             }

        # 2. Safety First Logic (Conservative default)
        # Prioritize Double Chance and Over 1.5 if available and > 0.65 confidence
        safe_markets = ["double_chance", "over_1.5", "home_over_0.5", "away_over_0.5"]
        safe_candidates = [predictions[k] for k in safe_markets if k in predictions and predictions[k]["confidence_score"] > 0.65]
        
        if safe_candidates:
            safe_candidates.sort(key=lambda x: x["confidence_score"], reverse=True)
            return {
                 "market_key": "safe_bet",
                 "market_type": safe_candidates[0]["market_type"],
                 "prediction": safe_candidates[0]["market_prediction"],
                 "confidence": safe_candidates[0]["confidence_score"],
                 "reason": safe_candidates[0]["reason"]
             }

        # 3. Fallback to highest confidence
        sorted_markets = sorted(
            predictions.values(),
            key=lambda x: x.get("confidence_score", 0),
            reverse=True
        )
        
        if sorted_markets:
            top = sorted_markets[0]
            return {
                "market_key": "fallback",
                "market_type": top.get("market_type"),
                "prediction": top.get("market_prediction"),
                "confidence": top.get("confidence_score"),
                "reason": top.get("reason")
            }

        return {}

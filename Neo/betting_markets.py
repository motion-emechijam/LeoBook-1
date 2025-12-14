"""
Betting Markets Module
Generates predictions for comprehensive betting markets.
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
            base_conf = calc_confidence((home_score + draw_score) / 2, 6)
            # Reduce confidence if xG strongly opposes (away favored)
            if away_xg > home_xg + 0.5:
                base_conf *= 0.7  # Reduce by 30%
            elif abs(home_xg - away_xg) < 0.2 and home_score < draw_score + 2:
                base_conf *= 0.8  # Reduce if xG close and not strong home advantage
            predictions["double_chance"] = {
                "market_type": "Double Chance",
                "market_prediction": f"{home_team} or Draw",
                "confidence_score": base_conf,
                "reason": f"{home_team} unlikely to lose"
            }
        elif away_score + draw_score > home_score + 2:
            base_conf = calc_confidence((away_score + draw_score) / 2, 6)
            # Reduce confidence if xG strongly opposes (home favored)
            if home_xg > away_xg + 0.5:
                base_conf *= 0.7  # Reduce by 30%
            elif abs(home_xg - away_xg) < 0.2 and away_score < draw_score + 2:
                base_conf *= 0.8  # Reduce if xG close and not strong away advantage
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
                "confidence_score": calc_confidence(max(home_score, away_score), 5),
                "reason": "Draw unlikely"
            }

        # 3. Draw No Bet
        if home_score > away_score + 3:
            predictions["draw_no_bet"] = {
                "market_type": "Draw No Bet",
                "market_prediction": home_team,
                "confidence_score": calc_confidence(home_score - away_score, 3),
                "reason": f"{home_team} clear favorite"
            }
        elif away_score > home_score + 3:
            predictions["draw_no_bet"] = {
                "market_type": "Draw No Bet",
                "market_prediction": away_team,
                "confidence_score": calc_confidence(away_score - home_score, 3),
                "reason": f"{away_team} clear favorite"
            }
        else:
            predictions["draw_no_bet"] = {
                "market_type": "Draw No Bet",
                "market_prediction": home_team,
                "confidence_score": 0.4,  # Low confidence when close
                "reason": "Very close match"
            }

        # 4. BTTS (Both Teams To Score)
        btts_confidence = btts_prob if btts_prob > 0.5 else 1 - btts_prob
        predictions["btts"] = {
            "market_type": "Both Teams To Score (BTTS)",
            "market_prediction": "Yes" if btts_prob > 0.5 else "No",
            "confidence_score": btts_confidence,
            "reason": f"BTTS probability: {btts_prob:.2f}"
        }

        # 5. Over/Under Total Goals
        if over25_prob > 0.7:
            predictions["over_under"] = {
                "market_type": "Over/Under Total Goals",
                "market_prediction": "Over 2.5",
                "confidence_score": over25_prob,
                "reason": f"High goal expectation: {home_xg + away_xg:.1f}"
            }
        elif over25_prob < 0.3:
            predictions["over_under"] = {
                "market_type": "Over/Under Total Goals",
                "market_prediction": "Under 2.5",
                "confidence_score": 1 - over25_prob,
                "reason": f"Low goal expectation: {home_xg + away_xg:.1f}"
            }
        else:
            predictions["over_under"] = {
                "market_type": "Over/Under Total Goals",
                "market_prediction": "Over 2.5",
                "confidence_score": over25_prob,
                "reason": f"Moderate goal expectation: {home_xg + away_xg:.1f}"
            }

        # 6. BTTS and Win combinations
        if btts_prob > 0.6 and home_score > away_score + 2:
            predictions["btts_win"] = {
                "market_type": "BTTS and Win",
                "market_prediction": f"BTTS and {home_team} to win",
                "confidence_score": min(btts_prob, home_score / 10),
                "reason": f"{home_team} likely to win with goals"
            }
        elif btts_prob > 0.6 and away_score > home_score + 2:
            predictions["btts_win"] = {
                "market_type": "BTTS and Win",
                "market_prediction": f"BTTS and {away_team} to win",
                "confidence_score": min(btts_prob, away_score / 10),
                "reason": f"{away_team} likely to win with goals"
            }
        elif btts_prob > 0.6 and draw_score > max(home_score, away_score):
            predictions["btts_win"] = {
                "market_type": "BTTS and Win",
                "market_prediction": "BTTS and Draw",
                "confidence_score": min(btts_prob, draw_score / 8),
                "reason": "Draw expected with both teams scoring"
            }

        # 7. Goal Range
        expected_goals = home_xg + away_xg
        if expected_goals < 1.5:
            predictions["goal_range"] = {
                "market_type": "Goal Range",
                "market_prediction": "0-1 goals",
                "confidence_score": max(0.3, 2 - expected_goals),
                "reason": f"Low scoring match expected: {expected_goals:.1f} goals"
            }
        elif expected_goals < 3:
            predictions["goal_range"] = {
                "market_type": "Goal Range",
                "market_prediction": "2-3 goals",
                "confidence_score": 0.6,
                "reason": f"Moderate scoring expected: {expected_goals:.1f} goals"
            }
        elif expected_goals < 5:
            predictions["goal_range"] = {
                "market_type": "Goal Range",
                "market_prediction": "4-6 goals",
                "confidence_score": min(0.8, expected_goals / 6),
                "reason": f"High scoring match expected: {expected_goals:.1f} goals"
            }
        else:
            predictions["goal_range"] = {
                "market_type": "Goal Range",
                "market_prediction": "7+ goals",
                "confidence_score": min(0.9, expected_goals / 8),
                "reason": f"Very high scoring match expected: {expected_goals:.1f} goals"
            }

        # 8. Correct Score (from top predictions)
        if scores and scores[0]["prob"] > 0.08:
            predictions["correct_score"] = {
                "market_type": "Correct Score",
                "market_prediction": scores[0]["score"],
                "confidence_score": scores[0]["prob"] * 2,  # Scale up for significance
                "reason": f"Most probable score: {scores[0]['prob']:.3f} probability"
            }

        # 9. Asian Handicap (simplified)
        goal_diff = abs(home_xg - away_xg)
        if goal_diff > 1:
            if home_xg > away_xg:
                predictions["asian_handicap"] = {
                    "market_type": "Asian Handicap",
                    "market_prediction": f"{home_team} -1",
                    "confidence_score": min(0.8, goal_diff / 2),
                    "reason": f"{home_team} expected to win by margin"
                }
            else:
                predictions["asian_handicap"] = {
                    "market_type": "Asian Handicap",
                    "market_prediction": f"{away_team} -1",
                    "confidence_score": min(0.8, goal_diff / 2),
                    "reason": f"{away_team} expected to win by margin"
                }

        # 10. Clean Sheet
        home_defense_strength = sum(1 for r in reasoning if "strong defense" in r and home_team in r)
        away_defense_strength = sum(1 for r in reasoning if "strong defense" in r and away_team in r)

        if home_defense_strength > 0:
            predictions["clean_sheet"] = {
                "market_type": "Clean Sheet",
                "market_prediction": f"{home_team} Clean Sheet",
                "confidence_score": min(0.7, home_defense_strength * 0.3),
                "reason": f"{home_team} strong defensive record"
            }
        elif away_defense_strength > 0:
            predictions["clean_sheet"] = {
                "market_type": "Clean Sheet",
                "market_prediction": f"{away_team} Clean Sheet",
                "confidence_score": min(0.7, away_defense_strength * 0.3),
                "reason": f"{away_team} strong defensive record"
            }

        # 11. Winner and Over/Under
        if home_score > away_score + 3 and over25_prob > 0.65:
            predictions["winner_over_under"] = {
                "market_type": "Winner & Over/Under",
                "market_prediction": f"{home_team} to win & Over 2.5",
                "confidence_score": min(home_score / 12, over25_prob),
                "reason": f"{home_team} strong favorite with high goals expected"
            }
        elif away_score > home_score + 3 and over25_prob > 0.65:
            predictions["winner_over_under"] = {
                "market_type": "Winner & Over/Under",
                "market_prediction": f"{away_team} to win & Over 2.5",
                "confidence_score": min(away_score / 12, over25_prob),
                "reason": f"{away_team} strong favorite with high goals expected"
            }

        # 12. Team Over/Under Goals
        home_expected = home_xg
        away_expected = away_xg

        if home_expected > 1.2:
            predictions["team_over_under"] = {
                "market_type": "Team Over/Under Goals",
                "market_prediction": f"{home_team} Over 1.5",
                "confidence_score": min(0.8, home_expected / 2),
                "reason": f"{home_team} expected {home_expected:.1f} goals"
            }
        elif away_expected > 1.2:
            predictions["team_over_under"] = {
                "market_type": "Team Over/Under Goals",
                "market_prediction": f"{away_team} Over 1.5",
                "confidence_score": min(0.8, away_expected / 2),
                "reason": f"{away_team} expected {away_expected:.1f} goals"
            }

        # 13. Winner and BTTS
        if home_score > away_score + 2 and btts_prob > 0.55:
            predictions["winner_btts"] = {
                "market_type": "Final Result & BTTS",
                "market_prediction": f"{home_team} to win & BTTS Yes",
                "confidence_score": min(home_score / 10, btts_prob),
                "reason": f"{home_team} likely to win with both teams scoring"
            }
        elif away_score > home_score + 2 and btts_prob > 0.55:
            predictions["winner_btts"] = {
                "market_type": "Final Result & BTTS",
                "market_prediction": f"{away_team} to win & BTTS Yes",
                "confidence_score": min(away_score / 10, btts_prob),
                "reason": f"{away_team} likely to win with both teams scoring"
            }

        return predictions

    @staticmethod
    def get_market_confidence_distribution(predictions: Dict[str, Dict]) -> Dict[str, int]:
        """
        Analyze confidence distribution across all markets.
        Returns count of markets by confidence level.
        """
        distribution = {"Very High": 0, "High": 0, "Medium": 0, "Low": 0}

        for market_key, market_data in predictions.items():
            confidence = market_data.get("confidence_score", 0)
            if confidence >= 0.7:
                distribution["Very High"] += 1
            elif confidence >= 0.55:
                distribution["High"] += 1
            elif confidence >= 0.45:
                distribution["Medium"] += 1
            else:
                distribution["Low"] += 1

        return distribution

    @staticmethod
    def select_best_market(predictions: Dict[str, Dict], risk_preference: str = "medium") -> Dict[str, Any]:
        """
        Select the best market based on confidence and risk preference.
        """
        if not predictions:
            return {}

        # Sort by confidence score
        sorted_markets = sorted(
            predictions.items(),
            key=lambda x: x[1].get("confidence_score", 0),
            reverse=True
        )

        # Apply risk preference filter
        if risk_preference == "conservative":
            # Only consider Very High confidence markets
            filtered = [m for m in sorted_markets if m[1].get("confidence_score", 0) >= 0.7]
        elif risk_preference == "aggressive":
            # Include all markets
            filtered = sorted_markets
        else:  # medium
            # Include High and above
            filtered = [m for m in sorted_markets if m[1].get("confidence_score", 0) >= 0.55]

        if filtered:
            market_key, market_data = filtered[0]
            return {
                "market_key": market_key,
                "market_type": market_data.get("market_type"),
                "prediction": market_data.get("market_prediction"),
                "confidence": market_data.get("confidence_score"),
                "reason": market_data.get("reason")
            }

        return {}

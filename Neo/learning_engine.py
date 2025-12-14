"""
Learning Engine Module
Handles prediction learning, performance analysis, and weight adaptation.
Responsible for analyzing prediction outcomes and updating rule effectiveness.
"""

import json
import os
from typing import Dict, Any, List


class LearningEngine:
    """Self-learning component that analyzes prediction performance and adjusts weights"""

    LEARNING_DB = "DB/learning_weights.json"

    DEFAULT_WEIGHTS = {
        "h2h_home_win": 3,
        "h2h_away_win": 3,
        "h2h_draw": 4,
        "h2h_over25": 3,
        "standings_top_vs_bottom": 6,
        "standings_table_advantage": 3,
        "standings_gd_strong": 2,
        "standings_gd_weak": 2,
        "form_score_2plus": 4,
        "form_score_3plus": 2,
        "form_concede_2plus": 4,
        "form_no_score": 5,
        "form_clean_sheet": 5,
        "form_vs_top_win": 3,
        "xg_advantage": 3,
        "xg_draw": 2,
        "confidence_calibration": {
            "Very High": 0.75,
            "High": 0.60,
            "Medium": 0.50,
            "Low": 0.40
        }
    }

    @staticmethod
    def load_weights() -> Dict[str, Any]:
        """Load learned weights from file"""
        if os.path.exists(LearningEngine.LEARNING_DB):
            try:
                with open(LearningEngine.LEARNING_DB, 'r') as f:
                    return json.load(f)
            except:
                pass
        return LearningEngine.DEFAULT_WEIGHTS.copy()

    @staticmethod
    def save_weights(weights: Dict[str, Any]):
        """Save learned weights to file"""
        os.makedirs("DB", exist_ok=True)
        with open(LearningEngine.LEARNING_DB, 'w') as f:
            json.dump(weights, f, indent=2)

    @staticmethod
    def analyze_performance() -> Dict[str, Any]:
        """Analyze past predictions to calculate rule effectiveness"""
        from Helpers.DB_Helpers.db_helpers import PREDICTIONS_CSV
        import csv

        if not os.path.exists(PREDICTIONS_CSV):
            return {}

        rule_performance = {
            "h2h_home_win": {"correct": 0, "total": 0},
            "h2h_away_win": {"correct": 0, "total": 0},
            "h2h_draw": {"correct": 0, "total": 0},
            "h2h_over25": {"correct": 0, "total": 0},
            "standings_top_vs_bottom": {"correct": 0, "total": 0},
            "standings_table_advantage": {"correct": 0, "total": 0},
            "standings_gd_strong": {"correct": 0, "total": 0},
            "standings_gd_weak": {"correct": 0, "total": 0},
            "form_score_2plus": {"correct": 0, "total": 0},
            "form_score_3plus": {"correct": 0, "total": 0},
            "form_concede_2plus": {"correct": 0, "total": 0},
            "form_no_score": {"correct": 0, "total": 0},
            "form_clean_sheet": {"correct": 0, "total": 0},
            "form_vs_top_win": {"correct": 0, "total": 0},
            "xg_advantage": {"correct": 0, "total": 0},
            "xg_draw": {"correct": 0, "total": 0},
        }

        # Read predictions and analyze which rules contributed to correct predictions
        with open(PREDICTIONS_CSV, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('outcome_correct') != 'True' or not row.get('reason'):
                    continue

                prediction_type = row.get('prediction', row.get('type', ''))
                is_correct = row.get('outcome_correct') == 'True'
                reasoning = row.get('reason', '')

                # Analyze which rules were triggered based on reasoning
                if 'H2H home strong' in reasoning:
                    rule_performance["h2h_home_win"]["total"] += 1
                    if is_correct: rule_performance["h2h_home_win"]["correct"] += 1

                if 'H2H away strong' in reasoning:
                    rule_performance["h2h_away_win"]["total"] += 1
                    if is_correct: rule_performance["h2h_away_win"]["correct"] += 1

                if 'H2H drawish' in reasoning:
                    rule_performance["h2h_draw"]["total"] += 1
                    if is_correct: rule_performance["h2h_draw"]["correct"] += 1

                if 'Top vs Bottom' in reasoning:
                    rule_performance["standings_top_vs_bottom"]["total"] += 1
                    if is_correct: rule_performance["standings_top_vs_bottom"]["correct"] += 1

                if 'strong GD' in reasoning:
                    rule_performance["standings_gd_strong"]["total"] += 1
                    if is_correct: rule_performance["standings_gd_strong"]["correct"] += 1

                if 'weak GD' in reasoning:
                    rule_performance["standings_gd_weak"]["total"] += 1
                    if is_correct: rule_performance["standings_gd_weak"]["correct"] += 1

                if 'scores 2+' in reasoning:
                    rule_performance["form_score_2plus"]["total"] += 1
                    if is_correct: rule_performance["form_score_2plus"]["correct"] += 1

                if 'concedes 2+' in reasoning:
                    rule_performance["form_concede_2plus"]["total"] += 1
                    if is_correct: rule_performance["form_concede_2plus"]["correct"] += 1

                if 'fails to score' in reasoning:
                    rule_performance["form_no_score"]["total"] += 1
                    if is_correct: rule_performance["form_no_score"]["correct"] += 1

                if 'strong defense' in reasoning:
                    rule_performance["form_clean_sheet"]["total"] += 1
                    if is_correct: rule_performance["form_clean_sheet"]["correct"] += 1

                if 'xG advantage' in reasoning:
                    rule_performance["xg_advantage"]["total"] += 1
                    if is_correct: rule_performance["xg_advantage"]["correct"] += 1

                if 'Close xG suggests draw' in reasoning:
                    rule_performance["xg_draw"]["total"] += 1
                    if is_correct: rule_performance["xg_draw"]["correct"] += 1

        return rule_performance

    @staticmethod
    def update_weights() -> Dict[str, Any]:
        """Update weights based on performance analysis"""
        performance = LearningEngine.analyze_performance()
        current_weights = LearningEngine.load_weights()

        for rule, stats in performance.items():
            if stats["total"] >= 10:  # Minimum sample size
                accuracy = stats["correct"] / stats["total"]
                # Adjust weight based on accuracy
                # If accuracy > 0.6, increase weight; if < 0.4, decrease weight
                if accuracy > 0.6:
                    current_weights[rule] = min(current_weights[rule] * 1.1, 10)  # Cap at 10
                elif accuracy < 0.4:
                    current_weights[rule] = max(current_weights[rule] * 0.9, 0.5)  # Floor at 0.5

        LearningEngine.save_weights(current_weights)
        return current_weights

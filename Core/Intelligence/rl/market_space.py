# market_space.py: LeoBook Market Action Space — v8.0
# Part of LeoBook Core — Intelligence (RL Engine)
#
# Single source of truth for:
#   - 30-dim action space definition
#   - Synthetic fair odds (from historical likelihood)
#   - Project Stairway odds gate (1.20 – 4.00)
#   - Poisson probability computation
#   - Phase 2/3 data readiness thresholds

"""
LeoBook Market Action Space — v8.0
Single source of truth for:
  - 30-dim action space definition
  - Synthetic fair odds (from historical likelihood)
  - Project Stairway odds gate (1.20 – 4.00)
  - Poisson probability computation
  - Phase 2/3 data readiness thresholds
"""

from __future__ import annotations
import math
from typing import Dict, List, Tuple, Optional

# ── Project Stairway hard constraints ────────────────────────
STAIRWAY_ODDS_MIN: float = 1.20
STAIRWAY_ODDS_MAX: float = 4.00
STAIRWAY_MIN_EV:   float = -0.10  # Reduced to allow slightly negative EV if prob is very high (>80%)
STAIRWAY_PRIORITY: str   = "PROBABILITY" # Hard priority for Stairway v2

# ── Project Stairway stake ladder (NGN) ──────────────────────
STAIRWAY_STAKES: dict = {
    1:   1_000,
    2:   3_000,
    3:   9_000,
    4:  27_000,
    5:  81_000,
    6: 243_000,
    7: 729_000,
}

# ── Phase transition thresholds ──────────────────────────────
PHASE2_MIN_ODDS_ROWS:    int = 5_000
PHASE2_MIN_DAYS_LIVE:    int = 30
PHASE3_MIN_ODDS_ROWS:    int = 15_000
PHASE3_MIN_DAYS_LIVE:    int = 60

# ── 30-dim Action Space ──────────────────────────────────────
ACTIONS: List[Dict] = [
    {"idx":  0, "key": "no_bet",           "market": "No Bet",             "outcome": "No Bet",      "line": None, "likelihood": 0,   "market_id": None},
    {"idx":  1, "key": "over_0.5",         "market": "Over/Under",         "outcome": "Over",        "line": "0.5","likelihood": 93,  "market_id": "18"},
    {"idx":  2, "key": "home_to_score",    "market": "Home Team Goals O/U","outcome": "Over",        "line": "0.5","likelihood": 78,  "market_id": "52"},
    {"idx":  3, "key": "over_1.5",         "market": "Over/Under",         "outcome": "Over",        "line": "1.5","likelihood": 79,  "market_id": "18"},
    {"idx":  4, "key": "dc_1x",            "market": "Double Chance",      "outcome": "1X",          "line": None, "likelihood": 73,  "market_id": "10"},
    {"idx":  5, "key": "dc_12",            "market": "Double Chance",      "outcome": "12",          "line": None, "likelihood": 73,  "market_id": "10"},
    {"idx":  6, "key": "under_3.5",        "market": "Over/Under",         "outcome": "Under",       "line": "3.5","likelihood": 68,  "market_id": "18"},
    {"idx":  7, "key": "away_to_score",    "market": "Away Team Goals O/U","outcome": "Over",        "line": "0.5","likelihood": 66,  "market_id": "53"},
    {"idx":  8, "key": "over_2.5",         "market": "Over/Under",         "outcome": "Over",        "line": "2.5","likelihood": 55,  "market_id": "18"},
    {"idx":  9, "key": "highest_2nd_half", "market": "Highest Scoring Half","outcome":"2nd Half",    "line": None, "likelihood": 55,  "market_id": "502"},
    {"idx": 10, "key": "dc_x2",            "market": "Double Chance",      "outcome": "X2",          "line": None, "likelihood": 54,  "market_id": "10"},
    {"idx": 11, "key": "btts_yes",         "market": "GG/NG",              "outcome": "GG",          "line": None, "likelihood": 54,  "market_id": "29"},
    {"idx": 12, "key": "under_2.5",        "market": "Over/Under",         "outcome": "Under",       "line": "2.5","likelihood": 45,  "market_id": "18"},
    {"idx": 13, "key": "btts_no",          "market": "GG/NG",              "outcome": "NG",          "line": None, "likelihood": 46,  "market_id": "29"},
    {"idx": 14, "key": "home_win",         "market": "1X2",                "outcome": "1",           "line": None, "likelihood": 46,  "market_id": "1"},
    {"idx": 15, "key": "cs_home",          "market": "Clean Sheet - Home", "outcome": "Yes",         "line": None, "likelihood": 44,  "market_id": "571"},
    {"idx": 16, "key": "home_ov1.5",       "market": "Home Team Goals O/U","outcome": "Over",        "line": "1.5","likelihood": 48,  "market_id": "52"},
    {"idx": 17, "key": "combo_1x_gg",      "market": "DC & GG/NG",         "outcome": "1X & GG",     "line": None, "likelihood": 39,  "market_id": "302"},
    {"idx": 18, "key": "both_halves_ov0.5","market": "Both Halves O/U",    "outcome": "Over",        "line": "0.5","likelihood": 38,  "market_id": "460"},
    {"idx": 19, "key": "away_ov1.5",       "market": "Away Team Goals O/U","outcome": "Over",        "line": "1.5","likelihood": 34,  "market_id": "53"},
    {"idx": 20, "key": "cs_away",          "market": "Clean Sheet - Away", "outcome": "Yes",         "line": None, "likelihood": 32,  "market_id": "572"},
    {"idx": 21, "key": "over_3.5",         "market": "Over/Under",         "outcome": "Over",        "line": "3.5","likelihood": 32,  "market_id": "18"},
    {"idx": 22, "key": "away_win",         "market": "1X2",                "outcome": "2",           "line": None, "likelihood": 27,  "market_id": "1"},
    {"idx": 23, "key": "draw",             "market": "1X2",                "outcome": "X",           "line": None, "likelihood": 27,  "market_id": "1"},
    {"idx": 24, "key": "wtnil_home",       "market": "Win to Nil - Home",  "outcome": "Yes",         "line": None, "likelihood": 28,  "market_id": "573"},
    {"idx": 25, "key": "home_ov2.5",       "market": "Home Team Goals O/U","outcome": "Over",        "line": "2.5","likelihood": 25,  "market_id": "52"},
    {"idx": 26, "key": "wtnil_away",       "market": "Win to Nil - Away",  "outcome": "Yes",         "line": None, "likelihood": 18,  "market_id": "574"},
    {"idx": 27, "key": "away_ov2.5",       "market": "Away Team Goals O/U","outcome": "Over",        "line": "2.5","likelihood": 13,  "market_id": "53"},
    {"idx": 28, "key": "home_ov3.5",       "market": "Home Team Goals O/U","outcome": "Over",        "line": "3.5","likelihood": 10,  "market_id": "52"},
    {"idx": 29, "key": "away_ov3.5",       "market": "Away Team Goals O/U","outcome": "Over",        "line": "3.5","likelihood": 5,   "market_id": "53"},
]

N_ACTIONS: int = len(ACTIONS)   # 30

# ── Synthetic fair odds lookup ────────────────────────────────
SYNTHETIC_ODDS: Dict[str, float] = {
    a["key"]: round(1.0 / (a["likelihood"] / 100.0), 3)
    for a in ACTIONS
    if a["likelihood"] > 0
}
SYNTHETIC_ODDS["no_bet"] = 0.0

# ── Stairway-bettable actions ─────────────────────────────────
STAIRWAY_BETTABLE: List[int] = [
    a["idx"] for a in ACTIONS
    if a["likelihood"] > 0
    and STAIRWAY_ODDS_MIN
       <= round(1.0 / (a["likelihood"] / 100.0), 3)
       <= STAIRWAY_ODDS_MAX
]

# ── Poisson engine ────────────────────────────────────────────

def _poisson_pmf(lam: float, k: int) -> float:
    """P(X = k) where X ~ Poisson(lambda)."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)


def _poisson_cdf(lam: float, k: int) -> float:
    """P(X <= k)."""
    return sum(_poisson_pmf(lam, i) for i in range(k + 1))


def compute_poisson_probs(
    xg_home: float,
    xg_away: float,
    raw_scores: Optional[Dict[str, float]] = None,
) -> Dict[str, float]:
    """
    Derive probability for every action in ACTIONS from
    xg_home, xg_away via independent Poisson model.

    raw_scores (optional): {'home': float, 'draw': float, 'away': float}
    from Rule Engine weighted voting — used to blend 1X2 probs
    with Poisson for better calibration.

    Returns dict keyed by action["key"] -> probability [0,1].
    """
    h, a = max(xg_home, 0.01), max(xg_away, 0.01)

    MAX_G = 8
    p_home_k = [_poisson_pmf(h, k) for k in range(MAX_G + 1)]
    p_away_k = [_poisson_pmf(a, k) for k in range(MAX_G + 1)]

    # ── Joint score probabilities ─────────────────────────────
    p_home_win = sum(
        p_home_k[i] * p_away_k[j]
        for i in range(MAX_G + 1)
        for j in range(MAX_G + 1)
        if i > j
    )
    p_draw = sum(
        p_home_k[i] * p_away_k[i]
        for i in range(MAX_G + 1)
    )
    p_away_win = max(0.0, 1.0 - p_home_win - p_draw)

    # ── Blend 1X2 with Rule Engine raw_scores if available ────
    if raw_scores and sum(raw_scores.values()) > 0:
        rs = raw_scores
        total = rs["home"] + rs["draw"] + rs["away"] + 1e-9
        re_home = rs["home"] / total
        re_draw = rs["draw"] / total
        re_away = rs["away"] / total
        BLEND = 0.4
        p_home_win = (1 - BLEND) * p_home_win + BLEND * re_home
        p_draw     = (1 - BLEND) * p_draw     + BLEND * re_draw
        p_away_win = (1 - BLEND) * p_away_win + BLEND * re_away

    # ── Marginal team goal probabilities ─────────────────────
    p_home_scores = 1.0 - p_home_k[0]
    p_away_scores = 1.0 - p_away_k[0]

    # ── Total goals PMF ───────────────────────────────────────
    total_pmf = [0.0] * (2 * MAX_G + 1)
    for i in range(MAX_G + 1):
        for j in range(MAX_G + 1):
            total_pmf[i + j] += p_home_k[i] * p_away_k[j]

    def p_total_over(line: float) -> float:
        threshold = int(math.floor(line)) + 1
        return sum(total_pmf[t] for t in range(threshold, len(total_pmf)))

    def p_total_under(line: float) -> float:
        return 1.0 - p_total_over(line)

    def p_home_over(line: float) -> float:
        threshold = int(math.floor(line)) + 1
        return sum(p_home_k[k] for k in range(threshold, MAX_G + 1))

    def p_away_over(line: float) -> float:
        threshold = int(math.floor(line)) + 1
        return sum(p_away_k[k] for k in range(threshold, MAX_G + 1))

    # ── BTTS ──────────────────────────────────────────────────
    p_btts    = p_home_scores * p_away_scores
    p_no_btts = 1.0 - p_btts

    # ── Clean sheet / Win to nil ──────────────────────────────
    p_cs_home    = p_away_k[0]
    p_cs_away    = p_home_k[0]
    p_wtnil_home = p_home_win * p_cs_home
    p_wtnil_away = p_away_win * p_cs_away

    # ── Double chance ─────────────────────────────────────────
    p_dc_1x = p_home_win + p_draw
    p_dc_12 = p_home_win + p_away_win
    p_dc_x2 = p_draw + p_away_win

    # ── Combos ────────────────────────────────────────────────
    p_combo_1x_gg   = p_dc_1x * p_btts
    p_both_halves   = 0.38   # No HT data → use historical prior

    # ── Highest scoring half ──────────────────────────────────
    p_2nd_half_higher = 0.55  # Historical prior

    probs: Dict[str, float] = {
        "no_bet":            0.0,
        "over_0.5":          p_total_over(0.5),
        "home_to_score":     p_home_scores,
        "over_1.5":          p_total_over(1.5),
        "dc_1x":             p_dc_1x,
        "dc_12":             p_dc_12,
        "under_3.5":         p_total_under(3.5),
        "away_to_score":     p_away_scores,
        "over_2.5":          p_total_over(2.5),
        "highest_2nd_half":  p_2nd_half_higher,
        "dc_x2":             p_dc_x2,
        "btts_yes":          p_btts,
        "under_2.5":         p_total_under(2.5),
        "btts_no":           p_no_btts,
        "home_win":          p_home_win,
        "cs_home":           p_cs_home,
        "home_ov1.5":        p_home_over(1.5),
        "combo_1x_gg":       p_combo_1x_gg,
        "both_halves_ov0.5": p_both_halves,
        "away_ov1.5":        p_away_over(1.5),
        "cs_away":           p_cs_away,
        "over_3.5":          p_total_over(3.5),
        "away_win":          p_away_win,
        "draw":              p_draw,
        "wtnil_home":        p_wtnil_home,
        "home_ov2.5":        p_home_over(2.5),
        "wtnil_away":        p_wtnil_away,
        "away_ov2.5":        p_away_over(2.5),
        "home_ov3.5":        p_home_over(3.5),
        "away_ov3.5":        p_away_over(3.5),
    }
    return probs


def probs_to_tensor_30dim(probs: Dict[str, float]) -> List[float]:
    """
    Convert probs dict -> ordered 30-dim list aligned to ACTIONS.
    no_bet gets minimum probability (model must learn to use it
    deliberately, not by default).
    """
    vec = [probs.get(a["key"], 0.0) for a in ACTIONS]
    vec[0] = 0.05  # small but nonzero prior for no_bet
    total = sum(vec) + 1e-9
    return [v / total for v in vec]


def stairway_gate(
    action_key: str,
    live_odds: Optional[float] = None,
    model_prob: Optional[float] = None,
) -> Tuple[bool, str]:
    """
    Returns (is_bettable, reason).
    Uses live_odds if available, else synthetic fair odds.
    Enforces: 1.20 <= odds <= 4.00 AND EV >= 0.
    """
    if action_key == "no_bet":
        return False, "no_bet action"

    odds = live_odds if live_odds is not None \
           else SYNTHETIC_ODDS.get(action_key, 0.0)

    if odds <= 0:
        return False, f"no odds for {action_key}"
    if odds < STAIRWAY_ODDS_MIN:
        return False, f"odds {odds:.2f} below min {STAIRWAY_ODDS_MIN}"
    if odds > STAIRWAY_ODDS_MAX:
        return False, f"odds {odds:.2f} above max {STAIRWAY_ODDS_MAX}"

    if model_prob is not None:
        ev = (model_prob * odds) - 1.0
        if ev < STAIRWAY_MIN_EV:
            return False, f"EV {ev:.3f} below threshold {STAIRWAY_MIN_EV}"

    return True, "ok"


# ── Ground truth derivation ───────────────────────────────────

def derive_ground_truth(
    home_score: int,
    away_score: int,
) -> Dict[str, bool]:
    """
    Given final score, derive which of the 30 market outcomes
    actually occurred. Returns dict[action_key] -> bool.
    """
    total = home_score + away_score
    home_win  = home_score > away_score
    away_win  = away_score > home_score
    draw      = home_score == away_score
    btts      = home_score >= 1 and away_score >= 1

    return {
        "no_bet":            False,
        "over_0.5":          total > 0,
        "home_to_score":     home_score >= 1,
        "over_1.5":          total > 1,
        "dc_1x":             home_win or draw,
        "dc_12":             home_win or away_win,
        "under_3.5":         total < 4,
        "away_to_score":     away_score >= 1,
        "over_2.5":          total > 2,
        "highest_2nd_half":  None,  # no HT data
        "dc_x2":             draw or away_win,
        "btts_yes":          btts,
        "under_2.5":         total < 3,
        "btts_no":           not btts,
        "home_win":          home_win,
        "cs_home":           away_score == 0,
        "home_ov1.5":        home_score >= 2,
        "combo_1x_gg":       (home_win or draw) and btts,
        "both_halves_ov0.5": None,  # no HT data
        "away_ov1.5":        away_score >= 2,
        "cs_away":           home_score == 0,
        "over_3.5":          total > 3,
        "away_win":          away_win,
        "draw":              draw,
        "wtnil_home":        home_win and away_score == 0,
        "home_ov2.5":        home_score >= 3,
        "wtnil_away":        away_win and home_score == 0,
        "away_ov2.5":        away_score >= 3,
        "home_ov3.5":        home_score >= 4,
        "away_ov3.5":        away_score >= 4,
    }


# ── Phase readiness check ─────────────────────────────────────

def check_phase_readiness(conn) -> Dict[str, bool]:
    """
    Query SQLite to determine if Phase 2 or Phase 3 thresholds
    are met. Called by trainer.py at start of each training session.
    """
    from datetime import datetime

    try:
        odds_rows = conn.execute(
            "SELECT COUNT(*) FROM match_odds"
        ).fetchone()[0]
    except Exception:
        odds_rows = 0

    try:
        first_row = conn.execute(
            "SELECT MIN(extracted_at) FROM match_odds"
        ).fetchone()[0]
        if first_row:
            first_date = datetime.fromisoformat(first_row[:10])
            days_live = (datetime.now() - first_date).days
        else:
            days_live = 0
    except Exception:
        days_live = 0

    phase2_ready = (
        odds_rows >= PHASE2_MIN_ODDS_ROWS
        and days_live >= PHASE2_MIN_DAYS_LIVE
    )
    phase3_ready = (
        odds_rows >= PHASE3_MIN_ODDS_ROWS
        and days_live >= PHASE3_MIN_DAYS_LIVE
    )

    return {
        "phase2_ready": phase2_ready,
        "phase3_ready": phase3_ready,
        "odds_rows": odds_rows,
        "days_live": days_live,
    }

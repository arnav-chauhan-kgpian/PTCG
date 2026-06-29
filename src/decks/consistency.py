"""
Consistency analysis.

Uses hypergeometric probability to estimate opening reliability,
and counts draw/search density to produce consistency scores.
"""

from __future__ import annotations

import math

from pydantic import BaseModel, ConfigDict

from src.decks.metrics import DeckMetrics
from src.decks.models import Deck


class ConsistencyReport(BaseModel):
    """Consistency metrics for a deck."""

    model_config = ConfigDict(frozen=True)

    # Probability of opening with at least 1 Basic Pokémon (no mulligan)
    p_opening_basic: float        # 0–1

    # Expected mulligans before a legal opening hand
    expected_mulligans: float

    # Draw power density (cards per deck that draw)
    draw_density: float           # cards / 60

    # Search density
    search_density: float         # cards / 60

    # Combined consistency score 0–100
    consistency_score: float

    # Breakdown explanations
    draw_grade: str               # "S" | "A" | "B" | "C" | "D" | "F"
    search_grade: str
    consistency_grade: str

    # Hand-size indicators
    avg_hand_size_t1: float       # estimated hand size after T1 draw


def _hypergeometric_p_at_least_one(N: int, K: int, n: int) -> float:
    """P(drawing ≥1 success) from N total, K successes, n draws (without replacement)."""
    if K <= 0:
        return 0.0
    if K >= N:
        return 1.0
    # P(0 successes) = C(N-K, n) / C(N, n)
    def comb(a: int, b: int) -> float:
        if b > a or b < 0:
            return 0.0
        return math.comb(a, b)

    p_none = comb(N - K, n) / comb(N, n)
    return max(0.0, min(1.0, 1.0 - p_none))


def _letter_grade(score: float) -> str:
    if score >= 90:
        return "S"
    if score >= 75:
        return "A"
    if score >= 60:
        return "B"
    if score >= 45:
        return "C"
    if score >= 30:
        return "D"
    return "F"


def compute_consistency(deck: Deck, metrics: DeckMetrics) -> ConsistencyReport:
    N = 60
    n_opening = 7  # starting hand size

    # P(at least 1 basic in opening 7)
    K_basic = metrics.basic_pokemon_count
    p_basic = _hypergeometric_p_at_least_one(N, K_basic, n_opening)

    # Expected mulligans: geometric series  E = (1-p) / p
    if p_basic >= 1.0:
        expected_mulligans = 0.0
    elif p_basic <= 0.0:
        expected_mulligans = float("inf")
    else:
        expected_mulligans = round((1 - p_basic) / p_basic, 2)

    # Draw density
    draw_density = round(metrics.draw_power / N, 3)
    search_density = round(metrics.search_power / N, 3)

    # Score components (0-100 each)
    # Basic consistency (30 pts): having reliable opening
    basic_score = p_basic * 30

    # Draw score (30 pts): draw_density targets ~0.25 (15/60)
    draw_score = min(30.0, draw_density * 120)

    # Search score (25 pts): search_density targets ~0.17 (10/60)
    search_score = min(25.0, search_density * 150)

    # Trainer density bonus (15 pts): 35-40% trainers is optimal
    trainer_ratio = metrics.trainer_count / N
    trainer_score = max(0.0, 15.0 - abs(trainer_ratio - 0.6) * 30)

    consistency_score = round(basic_score + draw_score + search_score + trainer_score, 1)

    # T1 hand estimate: 7 cards + any draw from supporters/items
    avg_hand_t1 = 7.0 + min(3.0, draw_density * 20)

    return ConsistencyReport(
        p_opening_basic=round(p_basic, 4),
        expected_mulligans=expected_mulligans,
        draw_density=draw_density,
        search_density=search_density,
        consistency_score=consistency_score,
        draw_grade=_letter_grade(min(100.0, draw_density * 400)),
        search_grade=_letter_grade(min(100.0, search_density * 600)),
        consistency_grade=_letter_grade(consistency_score),
        avg_hand_size_t1=round(avg_hand_t1, 1),
    )

"""
Two-tier scoring:
  fast_score  — metrics only, used during inner search loop
  full_score  — delegates to DeckAnalyzer + ObjectiveSet, used for final candidates
"""

from __future__ import annotations

from dataclasses import dataclass

from src.deck_builder.constraints import ConstraintConfig, check_all
from src.deck_builder.objectives import ObjectiveSet, fast_score_metrics
from src.decks.analyzer import DeckAnalyzer
from src.decks.models import Deck
from src.decks.reports import DeckReport


@dataclass(frozen=True)
class CandidateScore:
    """Score breakdown for one deck candidate."""
    total: float                   # 0–100 weighted objective sum
    objective_breakdown: dict[str, float]   # name → raw score (0–100)
    is_legal: bool
    violation_count: int


def score_deck_fast(deck: Deck) -> float:
    """Cheap metric-only score — no graph, no DeckAnalyzer."""
    from src.decks.metrics import compute_metrics
    m = compute_metrics(deck)
    return fast_score_metrics(
        draw_power=m.draw_power,
        search_power=m.search_power,
        basic_pokemon_count=m.basic_pokemon_count,
        energy_count=m.energy_count,
        max_damage=m.max_damage,
        recovery_score=m.recovery_score,
        avg_attack_cost=m.avg_attack_cost,
    )


def score_deck_full(
    deck: Deck,
    analyzer: DeckAnalyzer,
    objective_set: ObjectiveSet | None = None,
    config: ConstraintConfig | None = None,
) -> tuple[CandidateScore, DeckReport]:
    """Full scoring via DeckAnalyzer + weighted objectives."""
    if objective_set is None:
        objective_set = ObjectiveSet()
    if config is None:
        config = ConstraintConfig()

    report = analyzer.analyze(deck)
    breakdown = objective_set.score_all(report)
    total = objective_set.total(report)

    slots = {s.card_id: (s.card, s.count) for s in deck.slots}
    violations = check_all(slots, config)
    error_count = sum(1 for v in violations if v.severity == "error")

    # Legal decks get a bonus; illegal decks are heavily penalised
    if error_count > 0:
        total = max(0.0, total - error_count * 15.0)

    score = CandidateScore(
        total=round(total, 2),
        objective_breakdown=breakdown,
        is_legal=error_count == 0,
        violation_count=len(violations),
    )
    return score, report

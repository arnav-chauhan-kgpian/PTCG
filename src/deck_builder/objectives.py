"""
Scoring objectives for deck quality.

Each Objective extracts one numeric score (0–100) from a DeckReport.
ObjectiveSet combines them into a weighted total.

All scoring is delegated to existing Phase 5 analysis — no logic is duplicated.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol

from src.decks.reports import DeckReport


class Objective(Protocol):
    """Interface for a single scoring objective."""
    name: str
    weight: float

    def score(self, report: DeckReport) -> float:
        """Return 0–100 score for this objective."""
        ...


# ---------------------------------------------------------------------------
# Concrete objectives
# ---------------------------------------------------------------------------

@dataclass
class ConsistencyObjective:
    name: str = "consistency"
    weight: float = 0.25

    def score(self, report: DeckReport) -> float:
        return report.consistency.consistency_score


@dataclass
class SynergyObjective:
    name: str = "synergy"
    weight: float = 0.20

    def score(self, report: DeckReport) -> float:
        return report.synergy.synergy_score


@dataclass
class EnergyCurveObjective:
    name: str = "energy_curve"
    weight: float = 0.10

    def score(self, report: DeckReport) -> float:
        # Target: avg cost 1.5–2.5, skew "mid"
        cost = report.curves.avg_energy_cost
        skew = report.curves.energy_cost_skew
        if skew == "mid":
            base = 80.0
        elif skew == "low":
            base = 70.0
        else:
            base = 55.0
        penalty = abs(cost - 2.0) * 8
        return max(0.0, min(100.0, base - penalty))


@dataclass
class DrawEngineObjective:
    name: str = "draw_engine"
    weight: float = 0.12

    def score(self, report: DeckReport) -> float:
        m = report.metrics
        # Target: 10–18 draw cards
        draw = m.draw_power
        target = 14
        diff = abs(draw - target)
        score = max(0.0, 100.0 - diff * 5)
        return score


@dataclass
class SearchEngineObjective:
    name: str = "search_engine"
    weight: float = 0.08

    def score(self, report: DeckReport) -> float:
        search = report.metrics.search_power
        return min(100.0, search * 8.0)


@dataclass
class EvolutionObjective:
    name: str = "evolution_curve"
    weight: float = 0.08

    def score(self, report: DeckReport) -> float:
        cr = report.curves
        # Reward complete evolution lines, penalise missing pre-evos
        missing = sum(
            1 for i in report.validation.warnings
            if i.code == "MISSING_PRE_EVOLUTION"
        )
        setup = cr.setup_turns_estimate
        # Faster setup = higher score (cap at 4 turns)
        speed_score = max(0.0, 100.0 - (setup - 1.0) * 20)
        penalty = missing * 15
        return max(0.0, speed_score - penalty)


@dataclass
class DamageCeilingObjective:
    name: str = "damage_ceiling"
    weight: float = 0.08

    def score(self, report: DeckReport) -> float:
        max_dmg = report.metrics.max_damage
        # Target: 150+ for relevant damage, 250+ for OHKO potential
        return min(100.0, max_dmg / 3.0)


@dataclass
class PrizeLiabilityObjective:
    name: str = "prize_liability"
    weight: float = 0.04

    def score(self, report: DeckReport) -> float:
        # Lower prize liability = better (rule-box Pokémon give 2 prizes)
        # Score: 100 when no rule-box, 0 when all Pokémon are rule-box
        return max(0.0, 100.0 - report.metrics.prize_liability_score * 100)


@dataclass
class RecoveryObjective:
    name: str = "recovery"
    weight: float = 0.05

    def score(self, report: DeckReport) -> float:
        return min(100.0, report.metrics.recovery_score * 10.0)


# ---------------------------------------------------------------------------
# Penalty objectives (subtract from total)
# ---------------------------------------------------------------------------

@dataclass
class OrphanPenaltyObjective:
    name: str = "orphan_penalty"
    weight: float = -0.06   # negative weight = penalty

    def score(self, report: DeckReport) -> float:
        orphans = len(report.synergy.orphan_cards)
        return min(100.0, orphans * 10.0)  # higher = worse (weight is negative)


@dataclass
class EnergyMismatchObjective:
    name: str = "energy_mismatch"
    weight: float = -0.04

    def score(self, report: DeckReport) -> float:
        mismatch = sum(
            1 for i in report.validation.warnings
            if i.code == "MISSING_ENERGY_TYPE"
        )
        return mismatch * 25.0


# ---------------------------------------------------------------------------
# ObjectiveSet
# ---------------------------------------------------------------------------

DEFAULT_OBJECTIVES: list = [
    ConsistencyObjective(),
    SynergyObjective(),
    EnergyCurveObjective(),
    DrawEngineObjective(),
    SearchEngineObjective(),
    EvolutionObjective(),
    DamageCeilingObjective(),
    PrizeLiabilityObjective(),
    RecoveryObjective(),
    OrphanPenaltyObjective(),
    EnergyMismatchObjective(),
]


@dataclass
class ObjectiveSet:
    """Weighted combination of objectives."""
    objectives: list = field(default_factory=lambda: list(DEFAULT_OBJECTIVES))

    def apply_weight_overrides(self, overrides: dict[str, float]) -> None:
        for obj in self.objectives:
            if obj.name in overrides:
                object.__setattr__(obj, "weight", overrides[obj.name])

    def score_all(self, report: DeckReport) -> dict[str, float]:
        return {obj.name: obj.score(report) for obj in self.objectives}

    def total(self, report: DeckReport) -> float:
        total = 0.0
        for obj in self.objectives:
            s = obj.score(report)
            total += obj.weight * s
        # Clamp to [0, 100]
        return round(max(0.0, min(100.0, total * (1 / _total_positive_weight(self)))), 2)


def _total_positive_weight(obj_set: ObjectiveSet) -> float:
    total = sum(abs(o.weight) for o in obj_set.objectives if o.weight > 0)
    return total if total > 0 else 1.0


# ---------------------------------------------------------------------------
# Fast scoring (no graph, no DeckReport — purely from metrics)
# ---------------------------------------------------------------------------

def fast_score_metrics(
    draw_power: int,
    search_power: int,
    basic_pokemon_count: int,
    energy_count: int,
    max_damage: int,
    recovery_score: int,
    avg_attack_cost: float,
    synergy_score: float = 50.0,
) -> float:
    """Lightweight score 0–100 without full DeckReport — used in inner search loop."""
    draw_s = min(30.0, draw_power * 2.0)
    search_s = min(20.0, search_power * 2.0)
    basic_s = min(15.0, basic_pokemon_count * 2.0)
    energy_s = max(0.0, 15.0 - abs(energy_count - 14) * 1.5)
    damage_s = min(10.0, max_damage / 30.0)
    rec_s = min(5.0, recovery_score * 1.0)
    syn_s = synergy_score * 0.05
    return round(draw_s + search_s + basic_s + energy_s + damage_s + rec_s + syn_s, 2)

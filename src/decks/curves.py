"""
Energy curve, evolution curve, and retreat curve analysis.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from src.cards.enums import Stage
from src.cards.models import PokemonCard
from src.decks.models import Deck


class CurveReport(BaseModel):
    """Structured curve data for a deck."""

    model_config = ConfigDict(frozen=True)

    # Energy curve: how many energy tokens are demanded per attack tier
    energy_curve: dict[int, int]   # total_cost → number of attacks at that cost
    avg_energy_cost: float
    energy_cost_skew: str          # "low" | "mid" | "high"

    # Evolution curve: turn estimate to set up main attacker
    setup_turns_estimate: float    # weighted average setup turns
    has_stage2: bool
    has_stage1: bool
    evolution_depth: int           # 0=basic-only, 1=stage1, 2=stage2

    # Retreat curve
    retreat_curve: dict[int, int]  # retreat_cost → count of Pokémon
    avg_retreat: float
    high_retreat_count: int        # retreat_cost >= 3

    # Speed rating
    speed_rating: str              # "very-fast" | "fast" | "medium" | "slow" | "very-slow"


def compute_curves(deck: Deck) -> CurveReport:
    energy_curve: dict[int, int] = {}
    retreat_curve: dict[int, int] = {}

    attack_costs: list[int] = []
    retreat_costs: list[int] = []
    has_stage1 = False
    has_stage2 = False

    for slot in deck.pokemon_slots():
        card = slot.card
        if not isinstance(card, PokemonCard):
            continue

        if card.stage == Stage.STAGE_1:
            has_stage1 = True
        elif card.stage == Stage.STAGE_2:
            has_stage2 = True

        # Retreat curve
        rc = card.retreat_cost
        retreat_curve[rc] = retreat_curve.get(rc, 0) + slot.count
        retreat_costs.extend([rc] * slot.count)

        # Energy curve (per attack, weighted by slot count)
        for attack in card.attacks:
            cost = attack.cost.total_count
            energy_curve[cost] = energy_curve.get(cost, 0) + slot.count
            attack_costs.extend([cost] * slot.count)

    avg_energy_cost = sum(attack_costs) / len(attack_costs) if attack_costs else 0.0
    avg_retreat = sum(retreat_costs) / len(retreat_costs) if retreat_costs else 0.0
    high_retreat = sum(1 for c in retreat_costs if c >= 3)

    # Evolution depth and setup turns estimate
    if has_stage2:
        evolution_depth = 2
        setup_turns = 3.0  # T3 ideal for Stage 2
    elif has_stage1:
        evolution_depth = 1
        setup_turns = 2.0
    else:
        evolution_depth = 0
        setup_turns = 1.0

    # Adjust for energy demand
    if avg_energy_cost >= 3:
        setup_turns += 1.0
    elif avg_energy_cost <= 1:
        setup_turns = max(1.0, setup_turns - 0.5)

    # Skew classification
    if avg_energy_cost <= 1.5:
        skew = "low"
    elif avg_energy_cost <= 2.5:
        skew = "mid"
    else:
        skew = "high"

    # Speed rating (combines evolution depth + energy cost)
    total_setup = setup_turns + avg_energy_cost * 0.3
    if total_setup <= 1.5:
        speed = "very-fast"
    elif total_setup <= 2.2:
        speed = "fast"
    elif total_setup <= 3.0:
        speed = "medium"
    elif total_setup <= 4.0:
        speed = "slow"
    else:
        speed = "very-slow"

    return CurveReport(
        energy_curve=energy_curve,
        avg_energy_cost=round(avg_energy_cost, 2),
        energy_cost_skew=skew,
        setup_turns_estimate=round(setup_turns, 1),
        has_stage2=has_stage2,
        has_stage1=has_stage1,
        evolution_depth=evolution_depth,
        retreat_curve=retreat_curve,
        avg_retreat=round(avg_retreat, 2),
        high_retreat_count=high_retreat,
        speed_rating=speed,
    )

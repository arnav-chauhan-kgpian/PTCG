"""
Crossover operators — combine two parent decks into offspring.

After crossover the result may be illegal; RepairEngine is called automatically.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.cards.models import EnergyCard, PokemonCard

if TYPE_CHECKING:
    from src.deck_builder.repair import RepairEngine


@dataclass(frozen=True)
class CrossoverResult:
    child_slots: dict[str, tuple]
    description: str


def uniform_crossover(
    parent_a: dict[str, tuple],
    parent_b: dict[str, tuple],
    rng: random.Random,
    repair: RepairEngine,
) -> CrossoverResult:
    """
    For each card present in either parent, include it in the child with
    probability 0.5.  Apply repair to normalise size and legality.
    """
    all_ids = set(parent_a) | set(parent_b)
    child: dict[str, tuple] = {}

    for cid in all_ids:
        if cid in parent_a and cid in parent_b:
            # Both have it — take average count rounded randomly
            ca, cnt_a = parent_a[cid]
            _, cnt_b = parent_b[cid]
            avg = (cnt_a + cnt_b) / 2
            cnt = int(avg) + (1 if rng.random() < (avg % 1) else 0)
            if cnt > 0:
                child[cid] = (ca, cnt)
        elif rng.random() < 0.5:
            # Only one parent has it — take with 50% chance
            src = parent_a if cid in parent_a else parent_b
            card, cnt = src[cid]
            child[cid] = (card, cnt)

    result = repair.repair(child)
    return CrossoverResult(result.slots, "uniform_crossover")


def segment_crossover(
    parent_a: dict[str, tuple],
    parent_b: dict[str, tuple],
    rng: random.Random,
    repair: RepairEngine,
) -> CrossoverResult:
    """
    Split parents by card category: take Pokémon from one parent,
    Trainers from the other, then fill Energy from both.
    """
    take_pokemon_from_a = rng.random() < 0.5

    child: dict[str, tuple] = {}

    pokemon_src = parent_a if take_pokemon_from_a else parent_b
    trainer_src = parent_b if take_pokemon_from_a else parent_a

    for cid, (card, cnt) in pokemon_src.items():
        if isinstance(card, PokemonCard):
            child[cid] = (card, cnt)

    for cid, (card, cnt) in trainer_src.items():
        from src.cards.models import TrainerCard
        if isinstance(card, TrainerCard):
            child[cid] = (card, cnt)

    # Energy: blend from both
    seen_energy: set[str] = set()
    for src in (parent_a, parent_b):
        for cid, (card, cnt) in src.items():
            if isinstance(card, EnergyCard) and cid not in seen_energy:
                child[cid] = (card, (cnt + 1) // 2)
                seen_energy.add(cid)

    result = repair.repair(child)
    return CrossoverResult(result.slots, "segment_crossover")

"""
Mutation operators for deck optimisation.

Each mutation takes a slot dict and returns a new slot dict (or None if inapplicable).
Mutations preserve legality where possible; the caller should run RepairEngine if not.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.cards.enums import EnergyType, Stage
from src.cards.models import EnergyCard, PokemonCard, TrainerCard

if TYPE_CHECKING:
    from src.cards.relationships.graph import CardGraph
    from src.deck_builder.generators import CardIndex


@dataclass(frozen=True)
class MutationResult:
    slots: dict[str, tuple]
    description: str
    success: bool


def _copy(slots: dict) -> dict:
    return dict(slots.items())


def _total(slots: dict) -> int:
    return sum(c for _, c in slots.values())


def _add_card(slots: dict, card, count: int, max_copies: int = 4) -> bool:
    """Add `count` copies of card. Returns True if space allows."""
    from src.cards.models import EnergyCard
    cid = str(card.card_id)
    current = slots.get(cid, (card, 0))[1]
    is_basic_energy = isinstance(card, EnergyCard) and card.energy_type == EnergyType.BASIC
    cap = count if is_basic_energy else min(count, max_copies - current)
    if cap <= 0:
        return False
    slots[cid] = (card, current + cap)
    return True


def _remove_card(slots: dict, cid: str, count: int = 1) -> bool:
    if cid not in slots:
        return False
    card, cnt = slots[cid]
    new_cnt = cnt - count
    if new_cnt <= 0:
        del slots[cid]
    else:
        slots[cid] = (card, new_cnt)
    return True


# ---------------------------------------------------------------------------
# Individual mutations
# ---------------------------------------------------------------------------

def swap_card(
    slots: dict,
    card_index: CardIndex,
    rng: random.Random,
    *,
    prefer_trainer: bool = False,
) -> MutationResult:
    """Replace one card copy with a random card from the database."""
    s = _copy(slots)
    # Pick a target to remove (prefer non-energy, non-critical)
    candidates = [
        cid for cid, (card, cnt) in s.items()
        if not (isinstance(card, EnergyCard) and card.energy_type == EnergyType.BASIC)
    ]
    if not candidates:
        return MutationResult(slots, "swap_card: no non-basic-energy to swap", False)

    remove_id = rng.choice(candidates)
    removed_card, _ = s[remove_id]
    _remove_card(s, remove_id, 1)

    # Pick replacement from DB
    if prefer_trainer:
        pool = card_index.trainers()
    else:
        pool = card_index.all_cards()
    pool = [c for c in pool if str(c.card_id) != remove_id]
    if not pool:
        return MutationResult(slots, "swap_card: empty pool", False)

    new_card = rng.choice(pool)
    _add_card(s, new_card, 1)
    return MutationResult(s, f"Swapped '{removed_card.name}' → '{new_card.name}'", True)


def increase_draw(
    slots: dict,
    card_index: CardIndex,
    rng: random.Random,
) -> MutationResult:
    """Add a draw-effect trainer and remove the lowest-priority energy."""
    s = _copy(slots)
    draw_trainers = card_index.draw_trainers()
    already = {card.name for card, _ in s.values()}
    candidates = [c for c in draw_trainers if c.name not in already]
    if not candidates:
        candidates = draw_trainers
    if not candidates:
        return MutationResult(slots, "increase_draw: no draw trainers available", False)

    card = rng.choice(candidates[:10])
    # Remove 1 energy to make room
    energy_ids = [cid for cid, (c, _) in s.items() if isinstance(c, EnergyCard)]
    if not energy_ids:
        return MutationResult(slots, "increase_draw: no energy to remove", False)
    rng.shuffle(energy_ids)
    _remove_card(s, energy_ids[0], 1)
    _add_card(s, card, 1)
    return MutationResult(s, f"Added draw trainer '{card.name}', removed 1 energy", True)


def reduce_energy(
    slots: dict,
    card_index: CardIndex,
    rng: random.Random,
) -> MutationResult:
    """Remove 1 energy and add 1 trainer."""
    s = _copy(slots)
    energy_ids = [cid for cid, (c, cnt) in s.items()
                  if isinstance(c, EnergyCard) and cnt > 1]
    if not energy_ids:
        return MutationResult(slots, "reduce_energy: cannot reduce further", False)
    _remove_card(s, rng.choice(energy_ids), 1)
    trainers = [c for c in card_index.trainers()
                if str(c.card_id) not in s]
    if not trainers:
        return MutationResult(slots, "reduce_energy: no new trainer available", False)
    t = rng.choice(trainers[:20])
    _add_card(s, t, 1)
    return MutationResult(s, f"Reduced energy, added trainer '{t.name}'", True)


def increase_energy(
    slots: dict,
    rng: random.Random,
) -> MutationResult:
    """Add 1 basic energy and remove 1 low-value trainer."""
    s = _copy(slots)
    # Find basic energy already in deck
    be = [(cid, card, cnt) for cid, (card, cnt) in s.items()
          if isinstance(card, EnergyCard) and card.energy_type == EnergyType.BASIC]
    if not be:
        return MutationResult(slots, "increase_energy: no basic energy in deck", False)
    # Find trainer to remove
    trainers = [cid for cid, (card, cnt) in s.items() if isinstance(card, TrainerCard)]
    if not trainers:
        return MutationResult(slots, "increase_energy: no trainers to remove", False)
    remove_id = rng.choice(trainers)
    removed_name = s[remove_id][0].name
    _remove_card(s, remove_id, 1)
    # Add energy
    ecid, ecard, ecnt = rng.choice(be)
    _add_card(s, ecard, 1)
    return MutationResult(s, f"Removed 1 trainer '{removed_name}', added 1 basic energy", True)


def replace_evolution_line(
    slots: dict,
    card_index: CardIndex,
    rng: random.Random,
) -> MutationResult:
    """Replace one Stage-2 evolution family with another."""
    s = _copy(slots)
    stage2_ids = [cid for cid, (card, _) in s.items()
                  if isinstance(card, PokemonCard) and card.stage == Stage.STAGE_2]
    if not stage2_ids:
        return MutationResult(slots, "replace_evo: no Stage 2 in deck", False)

    old_id = rng.choice(stage2_ids)
    old_card, old_cnt = s[old_id]

    # Collect entire old family
    old_names: set[str] = {old_card.name}
    if old_card.previous_stage:
        old_names.add(old_card.previous_stage)
        # look one more level back
        for c, _ in s.values():
            if isinstance(c, PokemonCard) and c.name in old_names and c.previous_stage:
                old_names.add(c.previous_stage)

    # Remove old family
    to_remove = [cid for cid, (c, _) in s.items()
                 if isinstance(c, PokemonCard) and c.name in old_names]
    removed_count = sum(s[cid][1] for cid in to_remove)
    for cid in to_remove:
        del s[cid]

    # Pick new Stage 2
    new_s2_pool = [c for c in card_index.pokemon_by_stage(Stage.STAGE_2)
                   if c.name != old_card.name]
    if not new_s2_pool:
        return MutationResult(slots, "replace_evo: no alternative Stage 2", False)
    new_s2 = rng.choice(new_s2_pool[:20])
    _add_card(s, new_s2, min(2, removed_count // 3 or 1))

    # Add pre-evolutions
    if new_s2.previous_stage:
        prev1 = card_index.by_name(new_s2.previous_stage)
        if prev1:
            _add_card(s, prev1[0], min(3, removed_count // 3 + 1))
            if prev1[0].previous_stage:
                prev0 = card_index.by_name(prev1[0].previous_stage)
                if prev0:
                    _add_card(s, prev0[0], min(4, removed_count // 3 + 2))

    return MutationResult(s, f"Replaced '{old_card.name}' family with '{new_s2.name}' family", True)


def add_synergy_partner(
    slots: dict,
    card_index: CardIndex,
    graph: CardGraph,
    rng: random.Random,
) -> MutationResult:
    """Add a high-synergy partner for one of the core Pokémon."""
    s = _copy(slots)
    poke_ids = [cid for cid, (card, _) in s.items() if isinstance(card, PokemonCard)]
    if not poke_ids:
        return MutationResult(slots, "add_synergy: no Pokémon in deck", False)

    seed_id = rng.choice(poke_ids)
    from src.cards.relationships.traversal import GraphTraversal
    t = GraphTraversal(graph)
    partners = t.recommend_partners(seed_id, top_n=20)
    deck_ids = set(s.keys())
    new_partners = [pid for pid in partners if pid not in deck_ids]
    if not new_partners:
        return MutationResult(slots, "add_synergy: all partners already in deck", False)

    partner_id = rng.choice(new_partners[:5])
    partner_card = card_index.by_id(partner_id)
    if partner_card is None:
        return MutationResult(slots, "add_synergy: partner card not in index", False)

    # Remove one energy to make room
    energy_ids = [cid for cid, (c, cnt) in s.items()
                  if isinstance(c, EnergyCard) and cnt > 1]
    if not energy_ids:
        return MutationResult(slots, "add_synergy: no energy to remove", False)
    _remove_card(s, energy_ids[0], 1)
    _add_card(s, partner_card, 1)
    seed_name = s.get(seed_id, (None, 0))[0]
    return MutationResult(
        s,
        f"Added synergy partner '{partner_card.name}' for '{seed_name and seed_name.name}'",
        True,
    )


def diversify(
    slots: dict,
    card_index: CardIndex,
    rng: random.Random,
) -> MutationResult:
    """Replace a 4-of non-core card with two different 2-ofs."""
    s = _copy(slots)
    high_count = [cid for cid, (card, cnt) in s.items()
                  if cnt >= 4 and not (isinstance(card, EnergyCard) and card.energy_type == EnergyType.BASIC)]
    if not high_count:
        return MutationResult(slots, "diversify: no 4-of to diversify", False)

    target_id = rng.choice(high_count)
    card, cnt = s[target_id]
    _remove_card(s, target_id, 2)
    pool = [c for c in card_index.all_cards() if c.name != card.name]
    if not pool:
        return MutationResult(slots, "diversify: no alternatives", False)
    alt = rng.choice(pool[:30])
    _add_card(s, alt, 2)
    return MutationResult(s, f"Diversified: '{card.name}' 4→2, added '{alt.name}' ×2", True)


# ---------------------------------------------------------------------------
# Dispatcher — pick a random mutation
# ---------------------------------------------------------------------------

_MUTATION_WEIGHTS = [
    ("swap_card", 30),
    ("increase_draw", 20),
    ("reduce_energy", 15),
    ("increase_energy", 10),
    ("add_synergy", 15),
    ("diversify", 10),
]


def random_mutation(
    slots: dict,
    card_index: CardIndex,
    graph: CardGraph,
    rng: random.Random,
) -> MutationResult:
    """Apply a randomly selected mutation."""
    names, weights = zip(*_MUTATION_WEIGHTS)
    choice = rng.choices(names, weights=weights, k=1)[0]

    if choice == "swap_card":
        return swap_card(slots, card_index, rng)
    if choice == "increase_draw":
        return increase_draw(slots, card_index, rng)
    if choice == "reduce_energy":
        return reduce_energy(slots, card_index, rng)
    if choice == "increase_energy":
        return increase_energy(slots, rng)
    if choice == "add_synergy":
        return add_synergy_partner(slots, card_index, graph, rng)
    if choice == "diversify":
        return diversify(slots, card_index, rng)
    return MutationResult(slots, "noop", False)

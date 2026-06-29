"""
Energy attachment and retreat-cost utilities.

Energy tokens are tracked as the count attached per Pokémon.  Type
checking (e.g. {R} vs {C}) uses ``EnergyCard.provides`` against attack
``EnergyCostModel.tokens``.
"""

from __future__ import annotations

from collections import Counter

from src.cards.enums import PokemonType
from src.cards.models import EnergyCard, EnergyCostModel, PokemonCard
from src.game_state.models import CardInstance
from src.game_state.state import GameState
from src.simulator.rules import COLORLESS


def attached_energy_provides(
    state: GameState, pokemon: CardInstance, energy_lookup
) -> Counter[str]:
    """
    Count energy types (as token strings, e.g. '{R}') attached to *pokemon*.

    energy_lookup(card_id) → EnergyCard | None (caller supplies, usually
    the simulator's CardRepository).
    """
    counts: Counter[str] = Counter()
    for eid in pokemon.attached_energy_ids:
        e_inst = state.card_instances.get(eid)
        if e_inst is None:
            continue
        card = energy_lookup(e_inst.card_id)
        if card is None:
            counts[COLORLESS] += 1
            continue
        # EnergyCard.provides → tuple[PokemonType, ...]
        provides = getattr(card, "provides", ()) or ()
        if not provides:
            counts[COLORLESS] += 1
            continue
        for ptype in provides:
            counts[_type_to_token(ptype)] += 1
    return counts


def _type_to_token(ptype: PokemonType) -> str:
    # PokemonType values already map to their CSV symbol like "{R}", "{W}"
    # (DRAGON is the exception — uses a non-ASCII glyph).
    value = ptype.value if isinstance(ptype, PokemonType) else str(ptype)
    if value.startswith("{") and value.endswith("}"):
        return value
    if ptype == PokemonType.DRAGON:
        return "{N}"
    return COLORLESS


def has_energy_for_cost(
    state: GameState, pokemon: CardInstance,
    cost: EnergyCostModel, energy_lookup,
) -> bool:
    """True if *pokemon* has enough attached energy to satisfy *cost*."""
    if cost.is_free:
        return True
    available = attached_energy_provides(state, pokemon, energy_lookup)
    total_attached = sum(available.values())
    if total_attached < cost.total_count:
        return False

    # Specific colours must each be satisfied by a matching token.
    needed = Counter(cost.tokens)
    # First satisfy non-colourless requirements
    available_copy = Counter(available)
    for token, required in needed.items():
        if token == COLORLESS:
            continue
        if available_copy[token] < required:
            return False
        available_copy[token] -= required
    # Colourless can be paid by anything remaining
    remaining = sum(v for v in available_copy.values() if v > 0)
    return remaining >= needed.get(COLORLESS, 0)


def retreat_cost(card: PokemonCard | None) -> int:
    """Return the printed retreat cost of *card*, defaulting to 1."""
    if card is None:
        return 1
    return getattr(card, "retreat_cost", 1) or 0


def energy_card_provides(card: EnergyCard | None) -> tuple[PokemonType, ...]:
    if card is None:
        return ()
    return getattr(card, "provides", ()) or ()

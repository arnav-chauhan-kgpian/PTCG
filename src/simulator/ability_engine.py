"""
Ability execution placeholder.

Abilities in PTCG are extremely card-specific and would require a
per-card handler dictionary to model faithfully.  For the production
simulator we mark the ability as used and rely on the
``effects.apply_effect`` dispatcher to handle the structured effect when
one has been parsed.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.cards.models import Ability, PokemonCard
from src.game_state.state import GameState
from src.simulator._lookup import safe_get

if TYPE_CHECKING:
    from src.cards.repository import CardRepository


def get_ability(card: PokemonCard | None) -> Ability | None:
    if card is None:
        return None
    return getattr(card, "ability", None)


def can_use_ability(state: GameState, instance_id: str,
                    repository: CardRepository) -> bool:
    inst = state.card_instances.get(instance_id)
    if inst is None or inst.ability_used:
        return False
    card = safe_get(repository, inst.card_id)
    return get_ability(card) is not None

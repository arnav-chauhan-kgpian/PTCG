"""
Evolution execution — replace a Pokémon with its next-stage card while
keeping attached energy, tools, and damage counters in place.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.cards.enums import Stage
from src.cards.models import PokemonCard
from src.game_state.state import GameState
from src.game_state.zones import PokemonStage as PStage
from src.simulator._lookup import safe_get
from src.simulator.actions import parse_target

if TYPE_CHECKING:
    from src.cards.repository import CardRepository


_STAGE_MAP = {
    Stage.BASIC:  PStage.BASIC,
    Stage.STAGE_1: PStage.STAGE_1,
    Stage.STAGE_2: PStage.STAGE_2,
}


def evolve_pokemon(
    state: GameState,
    player_id: int,
    evolution_hand_id: str,
    target_descriptor: str,
    repository: CardRepository,
) -> GameState:
    """
    Replace the target Pokémon with the evolution card from hand.

    The evolution card itself remains the in-play instance; its previous
    stage is recorded for later discard-on-KO handling.
    """
    player = state.players[player_id]
    evo_inst = state.card_instances.get(evolution_hand_id)
    if evo_inst is None:
        return state
    evo_card = safe_get(repository, evo_inst.card_id)
    if not isinstance(evo_card, PokemonCard):
        return state

    target_kind, target_idx = parse_target(target_descriptor)
    if target_kind == "active":
        target_id = player.active
    else:
        target_id = player.bench[target_idx] if target_idx < len(player.bench) else None
    if not target_id:
        return state

    target_inst = state.card_instances.get(target_id)
    if target_inst is None:
        return state

    # The evolution card inherits attachments, damage, and conditions
    new_evo = evo_inst.model_copy(update={
        "zone": target_inst.zone,
        "base_hp": getattr(evo_card, "hp", target_inst.base_hp) or target_inst.base_hp,
        "damage_taken": target_inst.damage_taken,
        "attached_energy_ids": target_inst.attached_energy_ids,
        "attached_tool_id": target_inst.attached_tool_id,
        "special_conditions": (),  # evolution removes special conditions
        "stage": _STAGE_MAP.get(evo_card.stage, PStage.BASIC),
        "prize_value": PStage.prize_value(_STAGE_MAP.get(evo_card.stage, PStage.BASIC)),
        "previous_stage_instance_id": target_id,
        "is_evolved_this_turn": True,
        "turn_entered_play": state.turn_number,
        "has_attacked": False,
        "has_retreated": False,
        "ability_used": False,
    })

    # The previous instance becomes a "stacked" card (still tracked for KO discard)
    old_inst = target_inst.model_copy(update={
        "attached_energy_ids": (),
        "attached_tool_id": None,
    })

    state = state.with_instance(new_evo).with_instance(old_inst)

    # Replace target_id with evolution_hand_id in active/bench, remove from hand
    new_hand = tuple(iid for iid in player.hand if iid != evolution_hand_id)
    if target_kind == "active":
        new_active = evolution_hand_id
        new_bench = player.bench
    else:
        new_active = player.active
        new_bench = tuple(
            evolution_hand_id if i == target_idx else b
            for i, b in enumerate(player.bench)
        )

    new_player = player.model_copy(update={
        "active": new_active,
        "bench": new_bench,
        "hand": new_hand,
        "hand_count": max(0, player.hand_count - 1),
    })
    return state.with_player(player_id, new_player)

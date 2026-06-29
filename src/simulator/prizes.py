"""
Prize-related helpers — counted by ``knockout.process_knockout`` but
exposed here for direct manipulation in tests and effects.
"""

from __future__ import annotations

from src.game_state.state import GameState
from src.game_state.zones import Zone


def take_prize(state: GameState, player_id: int) -> GameState:
    """Move one prize card to *player_id*'s hand."""
    player = state.players[player_id]
    if player.prizes_remaining <= 0 or not player.prizes:
        return state
    prize_id = player.prizes[0]
    new_prizes = player.prizes[1:]
    new_hand = player.hand + (prize_id,)
    new_player = player.model_copy(update={
        "prizes": new_prizes,
        "prizes_remaining": max(0, player.prizes_remaining - 1),
        "hand": new_hand,
        "hand_count": player.hand_count + 1,
    })
    state = state.with_player(player_id, new_player)
    inst = state.card_instances.get(prize_id)
    if inst is not None:
        state = state.with_instance(inst.with_zone(Zone.HAND))
    return state

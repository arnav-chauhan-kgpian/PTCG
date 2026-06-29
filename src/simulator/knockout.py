"""
Knockout detection + prize award.
"""

from __future__ import annotations

from src.game_state.actions import KnockoutRecord
from src.game_state.state import GameState
from src.simulator.zones import discard_pokemon


def detect_knockouts(state: GameState) -> list[tuple[int, str]]:
    """Return list of (owner_id, instance_id) for all KO'd Pokémon."""
    out: list[tuple[int, str]] = []
    for pidx, player in enumerate(state.players):
        for iid in player.all_pokemon_ids:
            inst = state.card_instances.get(iid)
            if inst is not None and inst.is_knocked_out:
                out.append((pidx, iid))
    return out


def process_knockout(
    state: GameState,
    owner_id: int,
    pokemon_id: str,
    by_player: int,
    attack_name: str = "",
) -> GameState:
    """
    Apply a single knockout: take prizes, move card to discard, log.
    """
    pokemon = state.card_instances.get(pokemon_id)
    if pokemon is None:
        return state

    prizes_taken = pokemon.prize_value

    # Award prizes to `by_player`: each prize → top card moves to hand
    by_player_state = state.players[by_player]
    available_prizes = list(by_player_state.prizes)
    new_prizes_remaining = by_player_state.prizes_remaining
    new_hand = list(by_player_state.hand)
    new_hand_count = by_player_state.hand_count

    for _ in range(prizes_taken):
        if new_prizes_remaining <= 0 or not available_prizes:
            break
        prize_id = available_prizes.pop(0)
        new_prizes_remaining -= 1
        if prize_id:
            new_hand.append(prize_id)
            new_hand_count += 1
            inst = state.card_instances.get(prize_id)
            if inst is not None:
                from src.game_state.zones import Zone
                state = state.with_instance(inst.with_zone(Zone.HAND))

    new_by_player = by_player_state.model_copy(update={
        "prizes": tuple(available_prizes),
        "prizes_remaining": new_prizes_remaining,
        "hand": tuple(new_hand),
        "hand_count": new_hand_count,
    })
    state = state.with_player(by_player, new_by_player)

    # Discard the KO'd Pokémon
    state = discard_pokemon(state, owner_id, pokemon_id)

    # Record the knockout
    state = state.with_knockout(KnockoutRecord(
        turn=state.turn_number,
        knocked_out_instance_id=pokemon_id,
        knocked_out_name=pokemon.card_name,
        owner=owner_id,
        by_player=by_player,
        by_attack_name=attack_name,
        prizes_taken=prizes_taken,
    ))
    return state


def process_all_knockouts(
    state: GameState, by_player: int, attack_name: str = ""
) -> GameState:
    """Detect and process every pending knockout in *state*."""
    for owner_id, pokemon_id in detect_knockouts(state):
        state = process_knockout(state, owner_id, pokemon_id, by_player, attack_name)
    return state

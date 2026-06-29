"""
Immutable zone-movement helpers.

All helpers return a *new* GameState; the input state is never mutated.
"""

from __future__ import annotations

from src.game_state.player import PlayerState
from src.game_state.state import GameState
from src.game_state.zones import Zone

# -------------------------------------------------------------------------
# Player updates
# -------------------------------------------------------------------------

def _set_player(state: GameState, player_id: int, new: PlayerState) -> GameState:
    return state.with_player(player_id, new)


# -------------------------------------------------------------------------
# Single-card moves (between zones)
# -------------------------------------------------------------------------

def move_to_hand_from_deck(state: GameState, player_id: int) -> tuple[GameState, str | None]:
    """Draw the top card of player's deck into their hand. Returns (state, drawn_id)."""
    player = state.players[player_id]
    if not player.deck_order:
        return state, None
    drawn_id = player.deck_order[0]
    new_order = player.deck_order[1:]
    new_hand = player.hand + (drawn_id,)
    new_player = player.model_copy(update={
        "deck_order": new_order,
        "deck_size": len(new_order),
        "hand": new_hand,
        "hand_count": player.hand_count + 1,
    })
    new_state = _set_player(state, player_id, new_player)
    inst = new_state.card_instances.get(drawn_id)
    if inst is not None:
        new_state = new_state.with_instance(inst.with_zone(Zone.HAND))
    return new_state, drawn_id


def move_hand_to_bench(state: GameState, player_id: int, instance_id: str) -> GameState:
    """Move a card from hand to the bench (as a new Basic Pokémon in play)."""
    player = state.players[player_id]
    new_hand = tuple(iid for iid in player.hand if iid != instance_id)
    new_bench = player.bench + (instance_id,)
    new_player = player.model_copy(update={
        "hand": new_hand,
        "hand_count": max(0, player.hand_count - 1),
        "bench": new_bench,
        "bench_count": len(new_bench),
    })
    state = _set_player(state, player_id, new_player)
    inst = state.card_instances.get(instance_id)
    if inst is not None:
        state = state.with_instance(inst.with_zone(Zone.BENCH).model_copy(
            update={"turn_entered_play": state.turn_number}
        ))
    return state


def move_hand_to_active(state: GameState, player_id: int, instance_id: str) -> GameState:
    """Move a card from hand directly to the Active slot (only when active is empty)."""
    player = state.players[player_id]
    if player.active is not None:
        return state
    new_hand = tuple(iid for iid in player.hand if iid != instance_id)
    new_player = player.model_copy(update={
        "hand": new_hand,
        "hand_count": max(0, player.hand_count - 1),
        "active": instance_id,
    })
    state = _set_player(state, player_id, new_player)
    inst = state.card_instances.get(instance_id)
    if inst is not None:
        state = state.with_instance(inst.with_zone(Zone.ACTIVE).model_copy(
            update={"turn_entered_play": state.turn_number}
        ))
    return state


def discard_from_hand(state: GameState, player_id: int, instance_id: str) -> GameState:
    player = state.players[player_id]
    if instance_id not in player.hand:
        return state
    new_hand = tuple(iid for iid in player.hand if iid != instance_id)
    new_discard = player.discard + (instance_id,)
    new_player = player.model_copy(update={
        "hand": new_hand,
        "hand_count": max(0, player.hand_count - 1),
        "discard": new_discard,
        "discard_count": len(new_discard),
    })
    state = _set_player(state, player_id, new_player)
    inst = state.card_instances.get(instance_id)
    if inst is not None:
        state = state.with_instance(inst.with_zone(Zone.DISCARD))
    return state


def discard_attached_energy(state: GameState, owner_id: int, pokemon_id: str,
                            energy_id: str) -> GameState:
    """Detach an energy from a Pokémon and move it to discard."""
    pokemon = state.card_instances.get(pokemon_id)
    if pokemon is None:
        return state
    new_pokemon = pokemon.without_energy(energy_id)
    state = state.with_instance(new_pokemon)
    # Move energy itself to discard
    player = state.players[owner_id]
    energy = state.card_instances.get(energy_id)
    if energy is not None:
        state = state.with_instance(energy.with_zone(Zone.DISCARD))
    new_discard = player.discard + (energy_id,)
    new_player = player.model_copy(update={
        "discard": new_discard,
        "discard_count": len(new_discard),
    })
    return _set_player(state, owner_id, new_player)


def attach_energy_to_pokemon(state: GameState, player_id: int,
                              energy_id: str, pokemon_id: str) -> GameState:
    """Attach an energy card from hand to a Pokémon in play."""
    player = state.players[player_id]
    new_hand = tuple(iid for iid in player.hand if iid != energy_id)
    new_player = player.model_copy(update={
        "hand": new_hand,
        "hand_count": max(0, player.hand_count - 1),
        "energy_attached_this_turn": True,
    })
    state = _set_player(state, player_id, new_player)
    pokemon = state.card_instances.get(pokemon_id)
    if pokemon is not None:
        new_pokemon = pokemon.with_energy_attached(energy_id)
        state = state.with_instance(new_pokemon)
    energy = state.card_instances.get(energy_id)
    if energy is not None:
        state = state.with_instance(energy.with_zone(Zone.ATTACHED))
    return state


# -------------------------------------------------------------------------
# Bulk: shuffle deck
# -------------------------------------------------------------------------

def shuffle_deck(state: GameState, player_id: int, shuffled_order: tuple[str, ...]) -> GameState:
    """Replace deck_order with the supplied shuffled ordering."""
    player = state.players[player_id]
    new_player = player.model_copy(update={
        "deck_order": shuffled_order,
        "deck_size": len(shuffled_order),
    })
    return _set_player(state, player_id, new_player)


# -------------------------------------------------------------------------
# Promote bench → active (after a knockout)
# -------------------------------------------------------------------------

def promote_bench_to_active(state: GameState, player_id: int,
                             bench_idx: int) -> GameState:
    player = state.players[player_id]
    if bench_idx >= len(player.bench):
        return state
    chosen = player.bench[bench_idx]
    new_bench = tuple(b for i, b in enumerate(player.bench) if i != bench_idx)
    new_player = player.model_copy(update={
        "active": chosen,
        "bench": new_bench,
        "bench_count": len(new_bench),
    })
    state = _set_player(state, player_id, new_player)
    inst = state.card_instances.get(chosen)
    if inst is not None:
        # The promoted Pokémon was on the Bench, so any prior status was
        # already cleared when it left the Active spot.  Carrying that
        # invariant forward makes promote idempotent.
        state = state.with_instance(inst.with_zone(Zone.ACTIVE))
    return state


def swap_active_with_bench(state: GameState, player_id: int,
                            bench_idx: int) -> GameState:
    """Move bench[idx] to Active and current Active to that bench slot."""
    player = state.players[player_id]
    if bench_idx >= len(player.bench) or player.active is None:
        return state
    chosen = player.bench[bench_idx]
    old_active = player.active
    new_bench = list(player.bench)
    new_bench[bench_idx] = old_active
    new_player = player.model_copy(update={
        "active": chosen,
        "bench": tuple(new_bench),
    })
    state = _set_player(state, player_id, new_player)
    # Update zones for both
    chosen_inst = state.card_instances.get(chosen)
    if chosen_inst is not None:
        state = state.with_instance(chosen_inst.with_zone(Zone.ACTIVE).model_copy(
            update={"has_retreated": True}
        ))
    # ── Leaving the Active Spot clears all Special Conditions (P0.4) ──
    old_active_inst = state.card_instances.get(old_active)
    if old_active_inst is not None:
        state = state.with_instance(
            old_active_inst.with_zone(Zone.BENCH).model_copy(
                update={"special_conditions": ()}
            )
        )
    return state


# -------------------------------------------------------------------------
# Move pokemon to discard (after KO)
# -------------------------------------------------------------------------

def discard_pokemon(state: GameState, player_id: int, pokemon_id: str) -> GameState:
    """Send a knocked-out Pokémon + all attachments to the discard pile."""
    player = state.players[player_id]
    pokemon = state.card_instances.get(pokemon_id)
    if pokemon is None:
        return state

    # Detach and discard energy + tool
    instances_to_discard = list(pokemon.attached_energy_ids)
    if pokemon.attached_tool_id:
        instances_to_discard.append(pokemon.attached_tool_id)
    instances_to_discard.append(pokemon_id)

    # Discard previous-stage cards too
    prev = pokemon.previous_stage_instance_id
    while prev:
        instances_to_discard.append(prev)
        p_inst = state.card_instances.get(prev)
        prev = p_inst.previous_stage_instance_id if p_inst else None

    new_discard = list(player.discard) + instances_to_discard

    # Remove from active or bench
    if player.active == pokemon_id:
        new_active = None
        new_bench = player.bench
    else:
        new_active = player.active
        new_bench = tuple(b for b in player.bench if b != pokemon_id)

    new_player = player.model_copy(update={
        "active": new_active,
        "bench": new_bench,
        "bench_count": len(new_bench),
        "discard": tuple(new_discard),
        "discard_count": len(new_discard),
    })
    state = _set_player(state, player_id, new_player)

    # Update zones
    for iid in instances_to_discard:
        inst = state.card_instances.get(iid)
        if inst is not None:
            state = state.with_instance(inst.with_zone(Zone.DISCARD))
    return state

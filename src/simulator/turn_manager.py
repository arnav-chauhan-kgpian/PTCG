"""
Turn lifecycle: between-turn upkeep, turn-flag reset, status condition effects.
"""

from __future__ import annotations

from src.game_state.state import GameState
from src.game_state.zones import SpecialCondition
from src.simulator import zones as Z
from src.simulator.knockout import process_all_knockouts
from src.simulator.victory import apply_victory_check


def begin_turn(state: GameState, drawing_player: int) -> GameState:
    """Reset turn-level flags and draw one card for *drawing_player*.

    If the deck is empty and the player must draw, the game ends
    immediately with the opposing player winning (deck-out rule).
    """
    # ─── Deck-out check (must run BEFORE the draw attempt) ───
    from src.game_state.zones import GameStatus
    p = state.players[drawing_player]
    if p.deck_size == 0:
        # Drawing player loses immediately.
        winner = 1 - drawing_player
        new_status = (
            GameStatus.PLAYER_0_WIN if winner == 0 else GameStatus.PLAYER_1_WIN
        )
        return state.with_status(new_status, winner=winner)

    new_p = p.reset_turn_flags()
    state = state.with_player(drawing_player, new_p)
    # Reset per-Pokémon turn flags for current player's in-play Pokémon
    for iid in p.all_pokemon_ids:
        inst = state.card_instances.get(iid)
        if inst is None:
            continue
        state = state.with_instance(inst.model_copy(update={
            "has_attacked": False,
            "has_retreated": False,
            "is_evolved_this_turn": False,
            "ability_used": False,
        }))
    # Draw
    state, _ = Z.move_to_hand_from_deck(state, drawing_player)
    return state


def end_turn(state: GameState, randomizer=None) -> GameState:
    """End-of-turn upkeep: status damage, then hand off to opponent.

    ``randomizer`` is optional for backward compatibility; without it
    Asleep auto-wakes (deterministic), which matches pre-P0.4 behaviour.
    """
    # Apply between-turn status conditions to the current player's active
    state = apply_between_turn_status(state, state.current_player, randomizer)
    # Process any KOs that resulted from status damage
    state = process_all_knockouts(state, by_player=1 - state.current_player)
    state = apply_victory_check(state)
    if state.is_terminal:
        return state
    # Advance to next turn
    next_player = 1 - state.current_player
    state = state.with_next_turn()
    state = begin_turn(state, next_player)
    return state


def apply_between_turn_status(state: GameState, player_id: int,
                               randomizer=None) -> GameState:
    """Apply between-turn condition effects on *player_id*'s Active.

    Order of resolution (official rules):
      1. Burned → 20 damage placed on the affected Pokémon.
      2. Poisoned → 10 damage placed on the affected Pokémon.
      3. Asleep → coin flip; heads = wake up, tails = remain asleep.
      4. Paralyzed → automatically clears (lasts exactly one opponent turn).

    Confusion is **not** a between-turn check — it triggers on attack.
    """
    player = state.players[player_id]
    if not player.active:
        return state
    active = state.card_instances.get(player.active)
    if active is None:
        return state

    # 1+2 ── Burn / Poison damage ──
    damage = 0
    for cond in active.special_conditions:
        if cond == SpecialCondition.POISONED:
            damage += 10
        elif cond == SpecialCondition.BURNED:
            damage += 20
    if damage > 0:
        state = state.with_instance(active.with_added_damage(damage))
        active = state.card_instances[player.active]

    # 3 ── Asleep coin flip ──
    keep: list[SpecialCondition] = []
    for cond in active.special_conditions:
        if cond == SpecialCondition.ASLEEP:
            woke = randomizer.coin_flip() if randomizer is not None else True
            if not woke:
                keep.append(cond)
        elif cond == SpecialCondition.PARALYZED:
            # 4 ── Paralysis always clears at end of the affected turn ──
            pass
        else:
            keep.append(cond)

    new_conditions = tuple(keep)
    if new_conditions != active.special_conditions:
        state = state.with_instance(
            active.model_copy(update={"special_conditions": new_conditions})
        )

    return state

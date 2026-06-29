"""
Enumerate the set of legal actions for the current player.

Conservatively legal — anything that *might* be playable based on public
state.  Action execution still revalidates and may no-op on failure.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.cards.enums import Stage, TrainerType
from src.cards.models import EnergyCard, PokemonCard, TrainerCard
from src.game_state.state import GameState
from src.game_state.zones import GameStatus, SpecialCondition
from src.mcts.node import MCTSAction
from src.simulator import actions as A
from src.simulator._lookup import safe_get, safe_lookup_fn
from src.simulator.energy_engine import has_energy_for_cost
from src.simulator.rules import GameRules

if TYPE_CHECKING:
    from src.cards.repository import CardRepository


def legal_actions(
    state: GameState,
    repository: CardRepository,
    rules: GameRules,
) -> list[MCTSAction]:
    if state.is_terminal:
        return []
    if state.game_status != GameStatus.ONGOING:
        return []

    player = state.current_player_state
    result: list[MCTSAction] = []

    # ─── Forced promotion: when active is empty, promotion is the ONLY ───
    # legal action.  All other actions (including end_turn) are blocked
    # until a new Active Pokémon is chosen.
    if player.active is None:
        # Prefer promoting from bench (mandatory if bench non-empty)
        for bench_idx in range(len(player.bench)):
            result.append(A.promote_to_active(bench_idx))
        # If bench is empty, the player must play a Basic from hand to fill
        # Active.  (If neither is possible, the no-Pokémon victory check
        # triggers; this branch returns an empty list and MCTS treats it as
        # terminal.)
        if not result:
            for idx, hand_id in enumerate(player.hand):
                inst = state.card_instances.get(hand_id)
                if inst is None:
                    continue
                card = safe_get(repository, inst.card_id)
                if isinstance(card, PokemonCard) and card.stage == Stage.BASIC:
                    result.append(A.play_pokemon(idx))
        return result

    # End turn is always legal (when an Active Pokémon is present)
    result.append(A.end_turn())

    active = state.card_instances.get(player.active)
    if active is None:
        return result

    # --- Play hand cards ---
    for idx, hand_id in enumerate(player.hand):
        inst = state.card_instances.get(hand_id)
        if inst is None:
            continue
        card = safe_get(repository, inst.card_id)
        if card is None:
            continue

        if isinstance(card, PokemonCard):
            if card.stage == Stage.BASIC:
                if len(player.bench) < rules.bench_size:
                    result.append(A.play_pokemon(idx))
            else:
                # Evolution: target must be a Pokémon whose card.name matches
                # card.previous_stage AND was not played this turn.
                prev_name = getattr(card, "previous_stage", None)
                if prev_name:
                    for target_inst_id, target_str in _all_in_play(state, player):
                        target = state.card_instances.get(target_inst_id)
                        if target is None:
                            continue
                        target_card = safe_get(repository, target.card_id)
                        if (
                            target_card is not None
                            and getattr(target_card, "name", "") == prev_name
                            and target.turn_entered_play < state.turn_number
                            and not target.is_evolved_this_turn
                        ):
                            result.append(A.evolve(idx, target_str))

        elif isinstance(card, EnergyCard):
            # Attach energy (if not yet attached this turn)
            if not player.energy_attached_this_turn:
                for target_id, target_str in _all_in_play(state, player):
                    result.append(A.attach_energy(idx, target_str))

        elif isinstance(card, TrainerCard):
            ttype = card.trainer_type
            if ttype == TrainerType.SUPPORTER:
                if not player.supporter_played_this_turn:
                    result.append(A.play_supporter(idx))
            elif ttype == TrainerType.ITEM:
                result.append(A.play_item(idx))
            elif ttype == TrainerType.STADIUM:
                if not player.stadium_played_this_turn:
                    result.append(A.play_stadium(idx))
            elif ttype == TrainerType.POKEMON_TOOL:
                # Attach to any in-play Pokémon without a tool
                for target_id, target_str in _all_in_play(state, player):
                    inst = state.card_instances.get(target_id)
                    if inst is not None and inst.attached_tool_id is None:
                        result.append(A.attach_tool(idx, target_str))

    # --- Retreat ---
    active_card = safe_get(repository, active.card_id) if active else None
    # Sleep and Paralysis prevent the Active Pokémon from retreating.
    retreat_locked = active is not None and any(
        c in active.special_conditions
        for c in (SpecialCondition.ASLEEP, SpecialCondition.PARALYZED)
    )
    if (
        active is not None
        and not active.has_retreated
        and len(player.bench) > 0
        and not retreat_locked
    ):
        for bench_idx in range(len(player.bench)):
            result.append(A.retreat(bench_idx, []))

    # --- Attack ---
    # Sleep and Paralysis prevent the Active Pokémon from attacking.
    # (Confusion does NOT block attack selection — the coin flip happens
    # during execution; the attack is still legal to declare.)
    attack_locked = active is not None and any(
        c in active.special_conditions
        for c in (SpecialCondition.ASLEEP, SpecialCondition.PARALYZED)
    )
    if active is not None and not active.has_attacked and not attack_locked:
        # First-player turn-1 restriction
        if not (
            rules.first_player_no_attack_turn_1
            and state.turn_number == 1
            and state.current_player == 0
        ):
            if isinstance(active_card, PokemonCard):
                for slot, atk in enumerate(active_card.attacks):
                    if has_energy_for_cost(
                        state, active, atk.cost, safe_lookup_fn(repository)
                    ):
                        result.append(A.attack(slot))

    return result


def _all_in_play(state: GameState, player) -> list[tuple[str, str]]:
    """Return [(instance_id, target_descriptor)] for active + bench."""
    out: list[tuple[str, str]] = []
    if player.active:
        out.append((player.active, A.target_active()))
    for i, bid in enumerate(player.bench):
        out.append((bid, A.target_bench(i)))
    return out

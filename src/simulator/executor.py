"""
Action dispatcher — applies an ``MCTSAction`` to a ``GameState``.

Returns a new GameState; the input is never mutated.  Illegal actions
are no-ops (the original state is returned).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.cards.enums import TrainerType
from src.cards.models import PokemonCard, TrainerCard
from src.game_state.actions import ActionRecord, ActionType
from src.game_state.state import GameState
from src.mcts.node import MCTSAction
from src.simulator import actions as A
from src.simulator import zones as Z
from src.simulator._lookup import safe_get
from src.simulator.attack_engine import apply_damage, compute_damage
from src.simulator.evolution_engine import evolve_pokemon
from src.simulator.knockout import process_all_knockouts
from src.simulator.rules import GameRules
from src.simulator.trainer_engine import execute_trainer
from src.simulator.turn_manager import end_turn as advance_turn
from src.simulator.victory import apply_victory_check

if TYPE_CHECKING:
    from src.cards.repository import CardRepository
    from src.simulator.randomizer import Randomizer


def execute(
    state: GameState,
    action: MCTSAction,
    repository: CardRepository,
    randomizer: Randomizer,
    rules: GameRules,
) -> GameState:
    if state.is_terminal:
        return state

    player_id = state.current_player
    handler = _DISPATCH.get(action.action_type)
    if handler is None:
        return state

    new_state = handler(state, action, player_id, repository, randomizer, rules)

    # Log the action
    new_state = new_state.with_action(
        ActionRecord(
            action_type=_ACTION_TYPE_MAP.get(action.action_type, ActionType.PASS),
            player=player_id,
            turn=state.turn_number,
            card_instance_id=None,
            target_instance_id=None,
            details=action.details,
        )
    )

    # Victory check after every action
    return apply_victory_check(new_state)


# -------------------------------------------------------------------------
# Individual handlers
# -------------------------------------------------------------------------

def _h_end_turn(state, action, pid, repo, rng, rules) -> GameState:
    return advance_turn(state, randomizer=rng)


def _h_promote_to_active(state, action, pid, repo, rng, rules) -> GameState:
    """Promote the chosen bench Pokémon to fill an empty Active slot."""
    player = state.players[pid]
    if player.active is not None:
        return state
    bench_idx = A.get_int(action, "bench_idx")
    return Z.promote_bench_to_active(state, pid, bench_idx)


def _h_play_pokemon(state, action, pid, repo, rng, rules) -> GameState:
    hand_idx = A.get_int(action, "hand_idx")
    player = state.players[pid]
    if hand_idx >= len(player.hand):
        return state
    instance_id = player.hand[hand_idx]
    inst = state.card_instances.get(instance_id)
    if inst is None:
        return state
    card = safe_get(repo, inst.card_id)
    if not isinstance(card, PokemonCard):
        return state
    # If active is empty, promote here; else bench
    if player.active is None:
        return Z.move_hand_to_active(state, pid, instance_id)
    if len(player.bench) >= rules.bench_size:
        return state
    return Z.move_hand_to_bench(state, pid, instance_id)


def _h_attach_energy(state, action, pid, repo, rng, rules) -> GameState:
    player = state.players[pid]
    if player.energy_attached_this_turn:
        return state
    hand_idx = A.get_int(action, "hand_idx")
    target = A.get_str(action, "target")
    if hand_idx >= len(player.hand):
        return state
    energy_id = player.hand[hand_idx]
    target_id = _resolve_target_id(state, pid, target)
    if target_id is None:
        return state
    return Z.attach_energy_to_pokemon(state, pid, energy_id, target_id)


def _h_evolve(state, action, pid, repo, rng, rules) -> GameState:
    hand_idx = A.get_int(action, "hand_idx")
    target = A.get_str(action, "target")
    player = state.players[pid]
    if hand_idx >= len(player.hand):
        return state
    evo_id = player.hand[hand_idx]
    return evolve_pokemon(state, pid, evo_id, target, repo)


def _h_retreat(state, action, pid, repo, rng, rules) -> GameState:
    player = state.players[pid]
    if player.active is None or not player.bench:
        return state
    active = state.card_instances.get(player.active)
    if active is None or active.has_retreated:
        return state
    card = safe_get(repo, active.card_id)
    cost = getattr(card, "retreat_cost", 0) if isinstance(card, PokemonCard) else 0
    # Apply tool-based retreat cost reduction (Air Balloon, Counter Gain)
    from src.simulator.modifiers import retreat_cost_delta
    cost = max(0, (cost or 0) + retreat_cost_delta(state, active, repo))
    if len(active.attached_energy_ids) < (cost or 0):
        return state
    # Discard `cost` energies from active
    discard_ids = A.get_int_list(action, "discarded")
    energy_ids = list(active.attached_energy_ids)
    if not discard_ids:
        chosen = energy_ids[: cost or 0]
    else:
        chosen = [energy_ids[i] for i in discard_ids if i < len(energy_ids)]
    for eid in chosen:
        state = Z.discard_attached_energy(state, pid, player.active, eid)
    # Swap with bench
    bench_idx = A.get_int(action, "to_bench_idx")
    return Z.swap_active_with_bench(state, pid, bench_idx)


def _apply_attack_effects(state, attack, pid, attacker_card, attacker):
    """Dispatch a parsed Attack's structured effects through the effect engine.

    Wired up by P0.5.  See ``src.simulator.effects.apply_attack_effects``.
    """
    from src.simulator import effects as _eff
    return _eff.apply_attack_effects(
        state, attack=attack, player_id=pid,
        attacker_card=attacker_card, attacker_instance=attacker,
    )


def _h_attack(state, action, pid, repo, rng, rules) -> GameState:
    slot = A.get_int(action, "slot")
    player = state.players[pid]
    if player.active is None:
        return state
    attacker = state.card_instances.get(player.active)
    opp = state.players[1 - pid]
    if attacker is None or opp.active is None:
        return state
    defender = state.card_instances.get(opp.active)
    if defender is None:
        return state

    attacker_card = safe_get(repo, attacker.card_id)
    defender_card = safe_get(repo, defender.card_id)
    if not isinstance(attacker_card, PokemonCard):
        return state
    if slot >= len(attacker_card.attacks):
        return state

    atk = attacker_card.attacks[slot]

    # ── Confusion: flip a coin; on tails the attack fails and the
    #    attacker takes 30 damage to itself ────────────────────────────
    from src.game_state.zones import SpecialCondition
    if SpecialCondition.CONFUSED in attacker.special_conditions:
        if not rng.coin_flip():
            # Self-damage 30; mark attacked; resolve KO; end turn
            state = apply_damage(state, player.active, 30)
            attacker = state.card_instances[player.active]
            state = state.with_instance(
                attacker.model_copy(update={"has_attacked": True})
            )
            state = process_all_knockouts(state, by_player=1 - pid,
                                           attack_name="confusion_self")
            state = apply_victory_check(state)
            if state.is_terminal:
                return state
            return advance_turn(state)

    result = compute_damage(
        attacker_card, attacker, atk, defender_card, defender, rules,
        state=state, repository=repo,
    )
    # Side-effect: any structured effect on the attack is dispatched via
    # the unified effect engine (P0.5 wiring).
    state = apply_damage(state, opp.active, result.final_damage)

    # Mark attacker as having attacked
    attacker = state.card_instances[player.active]
    state = state.with_instance(attacker.model_copy(update={"has_attacked": True}))

    # Apply parsed attack effects (P0.5)
    state = _apply_attack_effects(state, atk, pid, attacker_card, attacker)

    # Resolve KOs
    state = process_all_knockouts(state, by_player=pid, attack_name=atk.name)
    state = apply_victory_check(state)
    if state.is_terminal:
        return state

    # Attacking ends the turn
    return advance_turn(state, randomizer=rng)


def _h_play_item(state, action, pid, repo, rng, rules) -> GameState:
    return _play_trainer(state, action, pid, repo, rng, TrainerType.ITEM)


def _h_play_supporter(state, action, pid, repo, rng, rules) -> GameState:
    return _play_trainer(state, action, pid, repo, rng, TrainerType.SUPPORTER)


def _h_play_stadium(state, action, pid, repo, rng, rules) -> GameState:
    return _play_trainer(state, action, pid, repo, rng, TrainerType.STADIUM)


def _h_attach_tool(state, action, pid, repo, rng, rules) -> GameState:
    hand_idx = A.get_int(action, "hand_idx")
    target = A.get_str(action, "target")
    target_id = _resolve_target_id(state, pid, target)
    player = state.players[pid]
    if hand_idx >= len(player.hand) or target_id is None:
        return state
    tool_id = player.hand[hand_idx]
    target_inst = state.card_instances.get(target_id)
    if target_inst is None or target_inst.attached_tool_id is not None:
        return state
    # Move from hand to "attached" zone
    new_hand = tuple(iid for iid in player.hand if iid != tool_id)
    new_player = player.model_copy(update={
        "hand": new_hand,
        "hand_count": max(0, player.hand_count - 1),
    })
    state = state.with_player(pid, new_player)
    state = state.with_instance(
        target_inst.model_copy(update={"attached_tool_id": tool_id})
    )
    tool_inst = state.card_instances.get(tool_id)
    if tool_inst is not None:
        from src.game_state.zones import Zone
        state = state.with_instance(tool_inst.with_zone(Zone.ATTACHED))
    return state


def _h_use_ability(state, action, pid, repo, rng, rules) -> GameState:
    """Activate a Pokémon's ability and dispatch its parsed effect.

    The ability_used flag is set so the same ability cannot be triggered
    twice in one turn (matching the simulator's invariant; the official
    "once per turn" applies to ability text rather than this flag, but
    this captures the most common case).
    """
    source = A.get_str(action, "source", "active")
    target_id = _resolve_target_id(state, pid, source)
    if target_id is None:
        return state
    inst = state.card_instances.get(target_id)
    if inst is None or inst.ability_used:
        return state

    source_card = safe_get(repo, inst.card_id)
    ability = getattr(source_card, "ability", None)
    if ability is not None:
        # P1.5 — Path to the Peak ability suppression on Rule-Box Pokémon
        from src.cards.enums import RuleBox
        from src.simulator.modifiers import stadium_suppresses_abilities
        is_rule_box = getattr(source_card, "rule_box", RuleBox.NONE) != RuleBox.NONE
        if is_rule_box and stadium_suppresses_abilities(state, repo):
            # Suppressed: do not execute the ability, but mark as 'used'
            # so MCTS doesn't re-trigger this no-op every step.
            new_inst = state.card_instances[target_id].model_copy(
                update={"ability_used": True},
            )
            return state.with_instance(new_inst)
        from src.simulator import effects as _eff
        # Default target: same Pokémon (many abilities self-target).
        state = _eff.apply_ability_effects(
            state, ability=ability, player_id=pid,
            source_instance_id=target_id, target_instance_id=target_id,
            source_card=source_card, repository=repo, randomizer=rng,
        )

    # Mark ability used (re-fetch the instance — state may have changed)
    inst = state.card_instances.get(target_id)
    if inst is None:
        return state
    return state.with_instance(inst.model_copy(update={"ability_used": True}))


# -------------------------------------------------------------------------
# Trainer helper
# -------------------------------------------------------------------------

def _play_trainer(state, action, pid, repo, rng, expected_type):
    hand_idx = A.get_int(action, "hand_idx")
    player = state.players[pid]
    if hand_idx >= len(player.hand):
        return state
    card_id = player.hand[hand_idx]
    inst = state.card_instances.get(card_id)
    if inst is None:
        return state
    card = safe_get(repo, inst.card_id)
    if not isinstance(card, TrainerCard) or card.trainer_type != expected_type:
        return state

    # Resolve target if action specifies one
    target_id = None
    target_str = A.get_str(action, "target")
    if target_str:
        target_id = _resolve_target_id(state, pid, target_str)

    # Execute the trainer's effect via the regex engine (fast path for the
    # common draw/heal/switch keywords) and the structured effect engine
    # (which dispatches typed Effect objects and records unsupported ones
    # on SIM_REPORT).
    state = execute_trainer(state, pid, card, repo, rng, target_pokemon_id=target_id)
    from src.simulator import effects as _eff
    state = _eff.apply_trainer_effects(
        state, trainer=card, player_id=pid,
        source_instance_id=card_id, target_instance_id=target_id,
        repository=repo, randomizer=rng,
    )

    # Discard the trainer card (it was just removed from hand by effect or still there)
    if card_id in state.players[pid].hand:
        state = Z.discard_from_hand(state, pid, card_id)

    # Set supporter / stadium flag
    if expected_type == TrainerType.SUPPORTER:
        p = state.players[pid]
        state = state.with_player(pid, p.model_copy(update={
            "supporter_played_this_turn": True
        }))
    elif expected_type == TrainerType.STADIUM:
        p = state.players[pid]
        state = state.with_player(pid, p.model_copy(update={
            "stadium_played_this_turn": True
        }))
        state = state.model_copy(update={"stadium_instance_id": card_id})

    return state


# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def _resolve_target_id(state: GameState, player_id: int, target_str: str) -> str | None:
    if not target_str:
        return None
    kind, idx = A.parse_target(target_str)
    player = state.players[player_id]
    if kind == "active":
        return player.active
    if kind == "bench":
        return player.bench[idx] if idx < len(player.bench) else None
    return None


# -------------------------------------------------------------------------
# Dispatch tables
# -------------------------------------------------------------------------

_DISPATCH = {
    "end_turn":          _h_end_turn,
    "promote_to_active": _h_promote_to_active,
    "play_pokemon":      _h_play_pokemon,
    "attach_energy":     _h_attach_energy,
    "evolve":            _h_evolve,
    "retreat":           _h_retreat,
    "attack":            _h_attack,
    "play_item":         _h_play_item,
    "play_supporter":    _h_play_supporter,
    "play_stadium":      _h_play_stadium,
    "attach_tool":       _h_attach_tool,
    "use_ability":       _h_use_ability,
}

_ACTION_TYPE_MAP = {
    "end_turn":          ActionType.END_TURN,
    "promote_to_active": ActionType.SWITCH,
    "play_pokemon":      ActionType.PLAY_POKEMON,
    "attach_energy":     ActionType.ATTACH_ENERGY,
    "evolve":            ActionType.EVOLVE,
    "retreat":           ActionType.RETREAT,
    "attack":            ActionType.ATTACK,
    "play_item":         ActionType.PLAY_ITEM,
    "play_supporter":    ActionType.PLAY_SUPPORTER,
    "play_stadium":      ActionType.PLAY_STADIUM,
    "attach_tool":       ActionType.ATTACH_TOOL,
    "use_ability":       ActionType.USE_ABILITY,
}

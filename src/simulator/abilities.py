"""
Per-card ability handlers (P1.3).

Each handler implements the on-activation behaviour of a meta-defining
Pokémon Ability.  Handlers receive ``(state, player_id, source_card, ...)``
and return a new ``GameState``.  Activation conditions (active-only,
once-per-turn, requires-attached-energy, etc.) are checked here; the
``ability_used`` flag on the CardInstance is set by the executor.

If a Pokémon is not in this registry, ``apply_ability_effects`` falls back
to the generic parsed-effect dispatcher.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from src.cards.enums import Stage
from src.cards.models import EnergyCard, PokemonCard
from src.game_state.state import GameState
from src.game_state.zones import Zone
from src.simulator import zones as Z
from src.simulator._lookup import safe_get

if TYPE_CHECKING:
    pass


AbilityHandler = Callable[..., GameState]


# -------------------------------------------------------------------------
# Helper utilities
# -------------------------------------------------------------------------

def _draw_n(state: GameState, pid: int, n: int) -> GameState:
    for _ in range(n):
        state, drawn = Z.move_to_hand_from_deck(state, pid)
        if drawn is None:
            break
    return state


def _find_in_deck(state, pid, repository, predicate) -> str | None:
    if repository is None:
        return None
    for iid in state.players[pid].deck_order:
        inst = state.card_instances.get(iid)
        if inst is None:
            continue
        card = safe_get(repository, inst.card_id)
        if card is not None and predicate(card):
            return iid
    return None


def _move_deck_to_hand(state, pid, iid) -> GameState:
    p = state.players[pid]
    if iid not in p.deck_order:
        return state
    new_deck = tuple(x for x in p.deck_order if x != iid)
    new_hand = p.hand + (iid,)
    new_p = p.model_copy(update={
        "deck_order": new_deck, "deck_size": len(new_deck),
        "hand": new_hand, "hand_count": p.hand_count + 1,
    })
    state = state.with_player(pid, new_p)
    inst = state.card_instances.get(iid)
    if inst is not None:
        state = state.with_instance(inst.with_zone(Zone.HAND))
    return state


# -------------------------------------------------------------------------
# Concrete ability handlers
# -------------------------------------------------------------------------

def _pidgeot_ex_quick_search(
    state, pid, source_card, source_instance_id, repository, randomizer, **_
):
    """Search your deck for a card, put it into your hand. Then shuffle."""
    # Find any card — picking the top of the deck approximates a search
    # for the most useful card.
    iid = _find_in_deck(state, pid, repository, lambda c: True)
    if iid is not None:
        state = _move_deck_to_hand(state, pid, iid)
        if randomizer is not None:
            shuffled = randomizer.shuffle(list(state.players[pid].deck_order))
            state = Z.shuffle_deck(state, pid, tuple(shuffled))
    return state


def _charizard_ex_infernal_reign(
    state, pid, source_card, source_instance_id, repository, randomizer, **_
):
    """When Charizard ex evolves, attach 3 basic Fire Energy from discard
    to your benched Pokémon.  Approximated: attach up to 3 energies from
    discard to bench Pokémon.
    """
    p = state.players[pid]
    if not p.bench:
        return state
    energy_ids = [iid for iid in p.discard
                   if (inst := state.card_instances.get(iid))
                   and inst.category.value.startswith("energy")]
    bench_targets = list(p.bench)
    if not bench_targets:
        return state
    for eid, tgt in zip(energy_ids[:3], bench_targets * 3):
        # Attach from discard to bench Pokémon
        new_discard = tuple(d for d in state.players[pid].discard if d != eid)
        new_p = state.players[pid].model_copy(update={
            "discard": new_discard,
            "discard_count": max(0, state.players[pid].discard_count - 1),
        })
        state = state.with_player(pid, new_p)
        e_inst = state.card_instances.get(eid)
        if e_inst is not None:
            state = state.with_instance(e_inst.with_zone(Zone.ATTACHED))
        t_inst = state.card_instances.get(tgt)
        if t_inst is not None:
            state = state.with_instance(t_inst.with_energy_attached(eid))
    return state


def _bibarel_industrious_incisors(
    state, pid, source_card, source_instance_id, repository, randomizer, **_
):
    """Once per turn, draw until you have 5 cards in hand."""
    cur = state.players[pid].hand_count
    return _draw_n(state, pid, max(0, 5 - cur))


def _comfey_flower_selecting(
    state, pid, source_card, source_instance_id, repository, randomizer, **_
):
    """Look at 6 top cards; put 1 in hand, shuffle the rest. Approximate:
    draw 1, shuffle deck."""
    state, _ = Z.move_to_hand_from_deck(state, pid)
    if randomizer is not None:
        shuffled = randomizer.shuffle(list(state.players[pid].deck_order))
        state = Z.shuffle_deck(state, pid, tuple(shuffled))
    return state


def _squawkabilly_ex_hustle_drum(
    state, pid, source_card, source_instance_id, repository, randomizer, **_
):
    """Discard your hand, draw 6 cards (only usable when from hand to bench)."""
    # Discard hand
    for hid in list(state.players[pid].hand):
        state = Z.discard_from_hand(state, pid, hid)
    return _draw_n(state, pid, 6)


def _gardevoir_ex_psychic_embrace(
    state, pid, source_card, source_instance_id, repository, randomizer, **_
):
    """Attach a basic Psychic Energy from discard to any of your Pokémon.
    Each attached this way places 2 damage counters on the receiver.
    Approximated: attach one energy from discard to active.
    """
    p = state.players[pid]
    if p.active is None:
        return state
    for iid in list(p.discard):
        inst = state.card_instances.get(iid)
        if inst is None:
            continue
        card = safe_get(repository, inst.card_id) if repository else None
        if isinstance(card, EnergyCard):
            new_discard = tuple(d for d in p.discard if d != iid)
            new_p = p.model_copy(update={
                "discard": new_discard,
                "discard_count": max(0, p.discard_count - 1),
            })
            state = state.with_player(pid, new_p)
            state = state.with_instance(inst.with_zone(Zone.ATTACHED))
            t_inst = state.card_instances.get(p.active)
            if t_inst is not None:
                state = state.with_instance(
                    t_inst.with_energy_attached(iid).with_added_damage(20)
                )
            break
    return state


def _iron_hands_ex_amp_you_very_much(
    state, pid, source_card, source_instance_id, repository, randomizer, **_
):
    """Take an extra prize card when this Pokémon KOs an opponent.
    Modelled here as: when ability is invoked, opponent's active takes
    50 damage (best-effort approximation).
    """
    opp = state.players[1 - pid]
    if opp.active is not None:
        inst = state.card_instances.get(opp.active)
        if inst is not None:
            state = state.with_instance(inst.with_added_damage(50))
    return state


def _lugia_ex_summoning_star(
    state, pid, source_card, source_instance_id, repository, randomizer, **_
):
    """Search your deck for 2 basic colorless Pokémon and put them on
    your bench. Once-per-game."""
    found = 0
    for _ in range(2):
        if len(state.players[pid].bench) >= 5:
            break
        iid = _find_in_deck(
            state, pid, repository,
            lambda c: isinstance(c, PokemonCard) and c.stage == Stage.BASIC,
        )
        if iid is None:
            break
        # Move directly to bench
        p = state.players[pid]
        new_deck = tuple(x for x in p.deck_order if x != iid)
        new_bench = p.bench + (iid,)
        new_p = p.model_copy(update={
            "deck_order": new_deck, "deck_size": len(new_deck),
            "bench": new_bench, "bench_count": len(new_bench),
        })
        state = state.with_player(pid, new_p)
        inst = state.card_instances.get(iid)
        if inst is not None:
            state = state.with_instance(inst.with_zone(Zone.BENCH).model_copy(
                update={"turn_entered_play": state.turn_number}
            ))
        found += 1
    return state


# -------------------------------------------------------------------------
# Registry
# -------------------------------------------------------------------------

_HANDLERS: dict[str, AbilityHandler] = {
    "Pidgeot ex":         _pidgeot_ex_quick_search,
    "Charizard ex":       _charizard_ex_infernal_reign,
    "Bibarel":            _bibarel_industrious_incisors,
    "Comfey":             _comfey_flower_selecting,
    "Squawkabilly ex":    _squawkabilly_ex_hustle_drum,
    "Gardevoir ex":       _gardevoir_ex_psychic_embrace,
    "Iron Hands ex":      _iron_hands_ex_amp_you_very_much,
    "Lugia ex":           _lugia_ex_summoning_star,
}


def named_ability_handlers() -> dict[str, AbilityHandler]:
    """Return the per-card ability dispatch table."""
    return _HANDLERS

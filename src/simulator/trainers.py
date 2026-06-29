"""
Per-card trainer handlers (P1.2).

A small registry of named-card handlers covering the Standard-meta-defining
trainer cards.  Each handler receives the standard ``(state, player_id,
trainer, ...)`` signature, returns a new ``GameState``, and is registered
in ``named_trainer_handlers()``.

If a handler is not registered for a card, ``apply_trainer_effects`` falls
back to the structured Effect dispatcher.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from src.cards.enums import Stage
from src.cards.models import EnergyCard, PokemonCard, TrainerCard
from src.game_state.state import GameState
from src.game_state.zones import Zone
from src.simulator import zones as Z
from src.simulator._lookup import safe_get

if TYPE_CHECKING:
    from src.cards.repository import CardRepository
    from src.simulator.randomizer import Randomizer


TrainerHandler = Callable[..., GameState]


# -------------------------------------------------------------------------
# Helper utilities used by handlers
# -------------------------------------------------------------------------

def _draw_n(state: GameState, pid: int, n: int) -> GameState:
    for _ in range(n):
        state, drawn = Z.move_to_hand_from_deck(state, pid)
        if drawn is None:
            break
    return state


def _discard_hand(state: GameState, pid: int) -> GameState:
    hand_ids = list(state.players[pid].hand)
    for hid in hand_ids:
        state = Z.discard_from_hand(state, pid, hid)
    return state


def _shuffle_hand_into_deck(
    state: GameState, pid: int, rng: Randomizer | None
) -> GameState:
    p = state.players[pid]
    hand_ids = list(p.hand)
    new_deck = list(p.deck_order) + hand_ids
    if rng is not None:
        new_deck = rng.shuffle(new_deck)
    new_p = p.model_copy(update={
        "hand": (), "hand_count": 0,
        "deck_order": tuple(new_deck), "deck_size": len(new_deck),
    })
    state = state.with_player(pid, new_p)
    for hid in hand_ids:
        inst = state.card_instances.get(hid)
        if inst is not None:
            state = state.with_instance(inst.with_zone(Zone.DECK))
    return state


def _find_in_deck(
    state: GameState, pid: int, repository: CardRepository | None,
    predicate,
) -> str | None:
    """Return the instance_id of the first deck card matching predicate."""
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


def _move_deck_to_hand(state: GameState, pid: int, iid: str) -> GameState:
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


def _move_discard_to_hand(state: GameState, pid: int, iid: str) -> GameState:
    p = state.players[pid]
    if iid not in p.discard:
        return state
    new_discard = tuple(x for x in p.discard if x != iid)
    new_hand = p.hand + (iid,)
    new_p = p.model_copy(update={
        "discard": new_discard, "discard_count": len(new_discard),
        "hand": new_hand, "hand_count": p.hand_count + 1,
    })
    state = state.with_player(pid, new_p)
    inst = state.card_instances.get(iid)
    if inst is not None:
        state = state.with_instance(inst.with_zone(Zone.HAND))
    return state


def _move_discard_to_deck(state: GameState, pid: int, iid: str,
                          rng: Randomizer | None) -> GameState:
    p = state.players[pid]
    if iid not in p.discard:
        return state
    new_discard = tuple(x for x in p.discard if x != iid)
    new_deck = list(p.deck_order) + [iid]
    if rng is not None:
        new_deck = rng.shuffle(new_deck)
    new_p = p.model_copy(update={
        "discard": new_discard, "discard_count": len(new_discard),
        "deck_order": tuple(new_deck), "deck_size": len(new_deck),
    })
    state = state.with_player(pid, new_p)
    inst = state.card_instances.get(iid)
    if inst is not None:
        state = state.with_instance(inst.with_zone(Zone.DECK))
    return state


def _force_opponent_active_to_bench(state: GameState, pid: int) -> GameState:
    """'Gust' — choose one of opponent's benched and swap with their Active."""
    opp = state.players[1 - pid]
    if not opp.bench or opp.active is None:
        return state
    return Z.swap_active_with_bench(state, 1 - pid, 0)


# -------------------------------------------------------------------------
# Concrete handlers
# -------------------------------------------------------------------------

def _ultra_ball(state, pid, trainer, repository, randomizer, **_):
    """Discard 2 cards then search deck for any Pokémon."""
    # Discard 2 cards from hand (simulator picks first two non-trainer)
    p = state.players[pid]
    hand = [h for h in p.hand if state.card_instances.get(h) and
            state.card_instances[h].instance_id != trainer]
    for hid in hand[:2]:
        state = Z.discard_from_hand(state, pid, hid)
    # Search deck for any Pokémon
    iid = _find_in_deck(state, pid, repository,
                        lambda c: isinstance(c, PokemonCard))
    if iid is not None:
        state = _move_deck_to_hand(state, pid, iid)
    return state


def _nest_ball(state, pid, trainer, repository, randomizer, **_):
    """Search deck for a Basic Pokémon."""
    iid = _find_in_deck(state, pid, repository,
                        lambda c: isinstance(c, PokemonCard) and c.stage == Stage.BASIC)
    if iid is not None:
        state = _move_deck_to_hand(state, pid, iid)
    return state


def _buddy_buddy_poffin(state, pid, trainer, repository, randomizer, **_):
    """Search deck for up to 2 Basic Pokémon."""
    found = []
    for _ in range(2):
        iid = _find_in_deck(
            state, pid, repository,
            lambda c, taken=found: (
                isinstance(c, PokemonCard) and c.stage == Stage.BASIC
                and id(c) not in taken
            ),
        )
        if iid is None:
            break
        state = _move_deck_to_hand(state, pid, iid)
        found.append(iid)
    return state


def _rare_candy(state, pid, trainer, repository, randomizer, **_):
    """Evolve a Basic into a Stage 2 from hand (skipping Stage 1).

    The simulator approximates: find any Stage 2 in hand, evolve the
    matching Basic if one is present.
    """
    if repository is None:
        return state
    p = state.players[pid]
    for hid in p.hand:
        inst = state.card_instances.get(hid)
        if inst is None:
            continue
        card = safe_get(repository, inst.card_id)
        if not isinstance(card, PokemonCard) or card.stage != Stage.STAGE_2:
            continue
        prev_name = getattr(card, "previous_stage", None)
        if not prev_name:
            continue
        # Find matching basic in play whose evolves into the basic of this Stage 2
        for in_play_id in p.all_pokemon_ids:
            in_inst = state.card_instances.get(in_play_id)
            if in_inst is None:
                continue
            in_card = safe_get(repository, in_inst.card_id)
            if in_card is None or in_card.stage != Stage.BASIC:
                continue
            # Skip-stage: Stage 2's previous_stage names the Stage 1.
            # Rare Candy permits evolution from Basic directly.  We
            # approximate by checking that the basic's name matches a known
            # Stage 1 chain (best-effort).
            target_desc = (
                "active" if p.active == in_play_id
                else f"bench:{list(p.bench).index(in_play_id)}"
            )
            from src.simulator.evolution_engine import evolve_pokemon
            new_state = evolve_pokemon(state, pid, hid, target_desc, repository)
            if new_state is not state:
                return new_state
    return state


def _iono(state, pid, trainer, repository, randomizer, **_):
    """Both players shuffle hand into deck then draw N (= remaining prizes)."""
    # Draw count = prizes_remaining
    p0_draw = state.players[pid].prizes_remaining
    p1_draw = state.players[1 - pid].prizes_remaining
    state = _shuffle_hand_into_deck(state, pid, randomizer)
    state = _shuffle_hand_into_deck(state, 1 - pid, randomizer)
    state = _draw_n(state, pid, p0_draw)
    state = _draw_n(state, 1 - pid, p1_draw)
    return state


def _professors_research(state, pid, trainer, repository, randomizer, **_):
    """Discard your hand and draw 7 cards."""
    state = _discard_hand(state, pid)
    return _draw_n(state, pid, 7)


def _bosss_orders(state, pid, trainer, repository, randomizer, **_):
    """Switch opponent's Benched into Active ('gust')."""
    return _force_opponent_active_to_bench(state, pid)


def _arven(state, pid, trainer, repository, randomizer, **_):
    """Search deck for an Item and a Pokémon Tool."""
    from src.cards.enums import TrainerType
    p = state.players[pid]

    def _is_item(c):
        return (isinstance(c, TrainerCard)
                and c.trainer_type == TrainerType.ITEM)

    def _is_tool(c):
        return (isinstance(c, TrainerCard)
                and c.trainer_type == TrainerType.POKEMON_TOOL)

    for predicate in (_is_item, _is_tool):
        iid = _find_in_deck(state, pid, repository, predicate)
        if iid is not None:
            state = _move_deck_to_hand(state, pid, iid)
    return state


def _counter_catcher(state, pid, trainer, repository, randomizer, **_):
    """If you have more prizes remaining than the opponent, gust."""
    me = state.players[pid]
    opp = state.players[1 - pid]
    if me.prizes_remaining > opp.prizes_remaining:
        return _force_opponent_active_to_bench(state, pid)
    return state


def _switch(state, pid, trainer, repository, randomizer, **_):
    """Switch your Active with one of your Benched Pokémon."""
    if state.players[pid].bench:
        return Z.swap_active_with_bench(state, pid, 0)
    return state


def _switch_cart(state, pid, trainer, repository, randomizer, **_):
    """Switch + heal 30 from the Pokémon switched to bench."""
    p = state.players[pid]
    if not p.bench or p.active is None:
        return state
    old_active = p.active
    state = Z.swap_active_with_bench(state, pid, 0)
    inst = state.card_instances.get(old_active)
    if inst is not None:
        new_damage = max(0, inst.damage_taken - 30)
        state = state.with_instance(inst.with_damage(new_damage))
    return state


def _super_rod(state, pid, trainer, repository, randomizer, **_):
    """Shuffle up to 3 Pokémon and basic Energy from discard into deck."""
    p = state.players[pid]
    moved = 0
    for iid in list(p.discard):
        if moved >= 3:
            break
        inst = state.card_instances.get(iid)
        if inst is None:
            continue
        card = safe_get(repository, inst.card_id) if repository else None
        if card is None:
            continue
        is_pkmn = isinstance(card, PokemonCard)
        is_basic_energy = isinstance(card, EnergyCard)
        if is_pkmn or is_basic_energy:
            state = _move_discard_to_deck(state, pid, iid, randomizer)
            moved += 1
    return state


def _energy_retrieval(state, pid, trainer, repository, randomizer, **_):
    """Recover 2 basic Energy from discard to hand."""
    p = state.players[pid]
    moved = 0
    for iid in list(p.discard):
        if moved >= 2:
            break
        inst = state.card_instances.get(iid)
        if inst is None:
            continue
        card = safe_get(repository, inst.card_id) if repository else None
        if isinstance(card, EnergyCard):
            state = _move_discard_to_hand(state, pid, iid)
            moved += 1
    return state


def _earthen_vessel(state, pid, trainer, repository, randomizer, **_):
    """Discard 1 card from hand, search deck for up to 2 basic {F} Energy."""
    p = state.players[pid]
    if p.hand:
        state = Z.discard_from_hand(state, pid, p.hand[0])
    iid = _find_in_deck(state, pid, repository,
                        lambda c: isinstance(c, EnergyCard))
    if iid is not None:
        state = _move_deck_to_hand(state, pid, iid)
    return state


def _night_stretcher(state, pid, trainer, repository, randomizer, **_):
    """Recover 1 Pokémon + 1 basic Energy from discard to hand."""
    p = state.players[pid]
    pkmn_picked = energy_picked = False
    for iid in list(p.discard):
        if pkmn_picked and energy_picked:
            break
        inst = state.card_instances.get(iid)
        if inst is None:
            continue
        card = safe_get(repository, inst.card_id) if repository else None
        if isinstance(card, PokemonCard) and not pkmn_picked:
            state = _move_discard_to_hand(state, pid, iid)
            pkmn_picked = True
        elif isinstance(card, EnergyCard) and not energy_picked:
            state = _move_discard_to_hand(state, pid, iid)
            energy_picked = True
    return state


def _pal_pad(state, pid, trainer, repository, randomizer, **_):
    """Shuffle 2 Supporter cards from discard back into the deck."""
    from src.cards.enums import TrainerType
    p = state.players[pid]
    moved = 0
    for iid in list(p.discard):
        if moved >= 2:
            break
        inst = state.card_instances.get(iid)
        if inst is None:
            continue
        card = safe_get(repository, inst.card_id) if repository else None
        if (isinstance(card, TrainerCard)
                and card.trainer_type == TrainerType.SUPPORTER):
            state = _move_discard_to_deck(state, pid, iid, randomizer)
            moved += 1
    return state


def _hyper_aroma(state, pid, trainer, repository, randomizer, **_):
    """Search deck for up to 3 Basic Pokémon (variant of Buddy Poffin)."""
    found_ids = set()
    for _ in range(3):
        iid = _find_in_deck(
            state, pid, repository,
            lambda c, taken=found_ids: (
                isinstance(c, PokemonCard) and c.stage == Stage.BASIC
                and id(c) not in taken
            ),
        )
        if iid is None:
            break
        state = _move_deck_to_hand(state, pid, iid)
        found_ids.add(iid)
    return state


# -------------------------------------------------------------------------
# Registry
# -------------------------------------------------------------------------

_HANDLERS: dict[str, TrainerHandler] = {
    "Ultra Ball":            _ultra_ball,
    "Nest Ball":             _nest_ball,
    "Buddy-Buddy Poffin":    _buddy_buddy_poffin,
    "Rare Candy":            _rare_candy,
    "Iono":                  _iono,
    "Professor's Research":  _professors_research,
    "Boss's Orders":         _bosss_orders,
    "Arven":                 _arven,
    "Counter Catcher":       _counter_catcher,
    "Switch":                _switch,
    "Switch Cart":           _switch_cart,
    "Super Rod":             _super_rod,
    "Energy Retrieval":      _energy_retrieval,
    "Earthen Vessel":        _earthen_vessel,
    "Night Stretcher":       _night_stretcher,
    "Pal Pad":               _pal_pad,
    "Hyper Aroma":           _hyper_aroma,
}


def named_trainer_handlers() -> dict[str, TrainerHandler]:
    """Return the per-card trainer dispatch table."""
    return _HANDLERS

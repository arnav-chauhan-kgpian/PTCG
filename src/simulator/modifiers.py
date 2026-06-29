"""
Static modifiers from Stadiums, Tools, and Special Energy (P1.5/6/7).

These hooks are consulted by ``attack_engine.compute_damage`` and
``legal_actions`` to apply continuous effects without changing public
APIs.  Each lookup is read-only: no state mutation here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from src.cards.models import EnergyCard, PokemonCard, TrainerCard
from src.game_state.models import CardInstance
from src.game_state.state import GameState
from src.simulator._lookup import safe_get

if TYPE_CHECKING:
    from src.cards.repository import CardRepository


# -------------------------------------------------------------------------
# Stadium effects (registry keyed by card name)
# -------------------------------------------------------------------------

def stadium_card(state: GameState,
                 repository: CardRepository | None) -> TrainerCard | None:
    if state.stadium_instance_id is None or repository is None:
        return None
    inst = state.card_instances.get(state.stadium_instance_id)
    if inst is None:
        return None
    card = safe_get(repository, inst.card_id)
    return card if isinstance(card, TrainerCard) else None


def stadium_active_name(state: GameState,
                        repository: CardRepository | None) -> str:
    card = stadium_card(state, repository)
    return card.name if card is not None else ""


def stadium_suppresses_abilities(state: GameState,
                                  repository: CardRepository | None) -> bool:
    """Path to the Peak — Rule-Box ability suppression."""
    return stadium_active_name(state, repository) == "Path to the Peak"


# -------------------------------------------------------------------------
# Tool effects (registry keyed by card name)
# -------------------------------------------------------------------------

# Each entry: name → callable(target_card, defender_card, base_damage) → int delta
_TOOL_DAMAGE_DELTA: dict[str, int] = {
    # Bravery Charm: pure HP buff, no damage delta
    # Defiance Band: +30 vs ex Pokémon (rule_box-checked at call time)
    "Defiance Band": 30,
    # Hero's Cape: HP buff
    # Counter Gain (in older eras): −1 colorless cost (no damage delta)
}


_TOOL_HP_BONUS: dict[str, int] = {
    "Bravery Charm": 50,
    "Hero's Cape":   100,   # standard 2026 wording
}


_TOOL_RETREAT_DELTA: dict[str, int] = {
    "Counter Gain":  -1,
    "Air Balloon":   -2,
}


def tool_damage_delta(attacker: CardInstance | None,
                       defender: CardInstance | None,
                       defender_card: PokemonCard | None,
                       repository: CardRepository | None) -> int:
    """Bonus damage contributed by the attacker's tool against this defender."""
    if attacker is None or attacker.attached_tool_id is None or repository is None:
        return 0
    tool_inst = None
    # Tool instance is referenced from attacker.attached_tool_id (which is
    # the *card instance id* of the tool)
    if attacker.attached_tool_id:
        # The tool's CardInstance lives in the global card_instances dict —
        # caller passes nothing extra; we look it up via repository name later.
        pass
    return 0


def tool_card_name(state: GameState, pokemon: CardInstance,
                    repository: CardRepository | None) -> str:
    if pokemon.attached_tool_id is None or repository is None:
        return ""
    inst = state.card_instances.get(pokemon.attached_tool_id)
    if inst is None:
        return ""
    card = safe_get(repository, inst.card_id)
    return card.name if isinstance(card, TrainerCard) else ""


def attacker_tool_damage_bonus(
    state: GameState, attacker: CardInstance,
    defender_card: PokemonCard | None,
    repository: CardRepository | None,
) -> int:
    """Damage bonus the attacker's tool grants against this defender."""
    name = tool_card_name(state, attacker, repository)
    if not name:
        return 0
    if name == "Defiance Band":
        # +30 against Pokémon-ex
        if defender_card is not None:
            from src.cards.enums import RuleBox
            if defender_card.rule_box in (RuleBox.POKEMON_EX,
                                            RuleBox.MEGA_POKEMON_EX):
                return 30
    return _TOOL_DAMAGE_DELTA.get(name, 0)


def defender_hp_bonus(state: GameState, defender: CardInstance,
                       repository: CardRepository | None) -> int:
    """HP buff from the defender's attached tool."""
    name = tool_card_name(state, defender, repository)
    return _TOOL_HP_BONUS.get(name, 0)


def retreat_cost_delta(state: GameState, pokemon: CardInstance,
                        repository: CardRepository | None) -> int:
    name = tool_card_name(state, pokemon, repository)
    return _TOOL_RETREAT_DELTA.get(name, 0)


# -------------------------------------------------------------------------
# Special-energy attached-side effects (P1.7)
# -------------------------------------------------------------------------

_SPECIAL_ENERGY_DAMAGE_DELTA: dict[str, int] = {
    # Double Turbo Energy: attacks do −20 damage
    "Double Turbo Energy": -20,
}


def attacker_special_energy_delta(
    state: GameState, attacker: CardInstance,
    repository: CardRepository | None,
) -> int:
    """Aggregate damage delta from special-energy cards attached to attacker."""
    if repository is None:
        return 0
    delta = 0
    seen_names: set[str] = set()
    for eid in attacker.attached_energy_ids:
        e_inst = state.card_instances.get(eid)
        if e_inst is None:
            continue
        card = safe_get(repository, e_inst.card_id)
        if not isinstance(card, EnergyCard):
            continue
        name = card.name
        if name in seen_names:
            continue
        seen_names.add(name)
        delta += _SPECIAL_ENERGY_DAMAGE_DELTA.get(name, 0)
    return delta

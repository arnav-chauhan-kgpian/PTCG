"""
Damage calculation: weakness, resistance, modifiers, knockout detection.
"""

from __future__ import annotations

from dataclasses import dataclass

from src.cards.models import Attack, PokemonCard
from src.game_state.models import CardInstance
from src.game_state.state import GameState
from src.simulator.rules import GameRules


@dataclass(frozen=True)
class DamageResult:
    base_damage: int
    weakness_applied: bool
    resistance_applied: bool
    final_damage: int
    knocked_out: bool


def compute_damage(
    attacker_card: PokemonCard | None,
    attacker_instance: CardInstance,
    attack: Attack,
    defender_card: PokemonCard | None,
    defender_instance: CardInstance,
    rules: GameRules,
    extra_modifier: int = 0,
    *,
    state: GameState | None = None,
    repository=None,
) -> DamageResult:
    """Compute damage dealt by *attack* from attacker → defender.

    Layered modifiers (in evaluation order):
      1. Base printed damage
      2. VariableDamage / DamageModifier from the attack's parsed effect
      3. Attacker's attached-Tool damage bonus (e.g. Defiance Band)
      4. Attacker's attached special-energy delta (e.g. Double Turbo −20)
      5. Weakness × multiplier
      6. Resistance − reduction
      7. ``extra_modifier`` (callers may add custom adjustments)
    """
    base = int(attack.damage.base)

    # ── 2. Parsed-effect variable damage / damage modifier ──
    eff_delta = _parsed_effect_delta(attack, attacker_instance, state, repository)
    base += eff_delta

    # ── 3. Tool damage bonus ──
    if state is not None:
        from src.simulator.modifiers import (
            attacker_special_energy_delta,
            attacker_tool_damage_bonus,
        )
        base += attacker_tool_damage_bonus(
            state, attacker_instance, defender_card, repository,
        )
        base += attacker_special_energy_delta(
            state, attacker_instance, repository,
        )

    base += int(extra_modifier)
    if base < 0:
        base = 0

    # ── 5. Weakness ──
    weakness_applied = False
    if defender_card is not None and attacker_card is not None:
        attacker_type = getattr(attacker_card, "pokemon_type", None)
        w = getattr(defender_card, "weakness", None)
        if w is not None and w.energy_type == attacker_type:
            base = base * (w.multiplier or rules.weakness_multiplier)
            weakness_applied = True

    # ── 6. Resistance ──
    resistance_applied = False
    if defender_card is not None and attacker_card is not None:
        attacker_type = getattr(attacker_card, "pokemon_type", None)
        r = getattr(defender_card, "resistance", None)
        if r is not None and r.energy_type == attacker_type:
            base = max(0, base - (r.reduction or rules.resistance_reduction))
            resistance_applied = True

    final = max(0, base)
    new_damage = defender_instance.damage_taken + final
    # Defender tool HP bonus (Bravery Charm, Hero's Cape, etc.) raises the
    # effective HP.  Since CardInstance.max_hp is structural, we instead
    # cap final damage so the defender survives if the tool would save it.
    effective_max_hp = defender_instance.max_hp
    if state is not None:
        from src.simulator.modifiers import defender_hp_bonus
        effective_max_hp += defender_hp_bonus(state, defender_instance, repository)
    knocked_out = (
        effective_max_hp > 0 and new_damage >= effective_max_hp
    )
    if not knocked_out and effective_max_hp > defender_instance.max_hp:
        # Tool save: cap damage so KO is not triggered by the raw max_hp.
        cap = max(0, defender_instance.max_hp - defender_instance.damage_taken - 1)
        final = min(final, cap)
    return DamageResult(
        base_damage=int(attack.damage.base),
        weakness_applied=weakness_applied,
        resistance_applied=resistance_applied,
        final_damage=final,
        knocked_out=knocked_out,
    )


def _parsed_effect_delta(
    attack: Attack, attacker_instance: CardInstance,
    state: GameState | None, repository,
) -> int:
    """Apply VariableDamage / DamageModifier from the attack's parsed effect."""
    text = (getattr(attack, "effect", "") or "").strip()
    if not text:
        return 0
    try:
        from src.cards.effects import parse_effect
        effect = parse_effect(text)
    except Exception:
        return 0
    delta = 0

    def _scan(eff):
        nonlocal delta
        cls = type(eff).__name__
        if cls == "DamageModifier":
            delta += int(getattr(eff, "delta", 0) or 0)
        elif cls == "VariableDamage":
            base_per_unit = int(getattr(eff, "base_per_unit", 0) or 0)
            scale_by = getattr(eff, "scale_by", "") or ""
            multiplicative = bool(getattr(eff, "multiplicative", True))
            units = _count_units(scale_by, attacker_instance, state)
            if multiplicative and base_per_unit == 0:
                base_per_unit = 10
            delta += base_per_unit * units
        elif cls == "CompositeEffect":
            for child in getattr(eff, "effects", ()) or ():
                _scan(child)

    _scan(effect)
    return delta


def _count_units(scale_by: str, attacker_instance: CardInstance,
                  state: GameState | None) -> int:
    """Count units for VariableDamage's scale_by descriptor."""
    s = (scale_by or "").lower()
    if "energy" in s:
        return len(attacker_instance.attached_energy_ids)
    if "damage_counter" in s or "damage counter" in s:
        return attacker_instance.damage_taken // 10
    if "bench" in s and state is not None:
        # Most bench-based attacks count YOUR bench
        owner = attacker_instance.owner
        return len(state.players[owner].bench)
    if "discard" in s and state is not None:
        owner = attacker_instance.owner
        return len(state.players[owner].discard)
    return 0


def apply_damage(
    state: GameState, defender_id: str, damage: int
) -> GameState:
    """Place *damage* on *defender_id*, returning the new state."""
    inst = state.card_instances.get(defender_id)
    if inst is None or damage <= 0:
        return state
    return state.with_instance(inst.with_added_damage(damage))


def heal(state: GameState, target_id: str, amount: int) -> GameState:
    inst = state.card_instances.get(target_id)
    if inst is None or amount <= 0:
        return state
    new_damage = max(0, inst.damage_taken - amount)
    return state.with_instance(inst.with_damage(new_damage))

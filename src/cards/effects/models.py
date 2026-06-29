"""
Typed, immutable Pydantic v2 models for every recognised card effect.

Design:
  - Every model extends Effect (the base).
  - All models are frozen (immutable).
  - No raw dicts escape these boundaries.
  - The action_type field enables fast discrimination without isinstance checks.
  - Optional 'condition' field carries the parsed guard clause.

Effect taxonomy (flat enumeration intentional — avoids deep inheritance trees
that make pattern-matching awkward):

    Structural:   CompositeEffect, ConditionalEffect, CoinFlip, UnknownEffect
    Draw:         DrawCards
    Discard:      DiscardEffect
    Heal:         HealEffect
    Search:       SearchDeck, SearchDiscard
    Energy:       AttachEnergy, MoveEnergy
    Damage mods:  DamageModifier, BenchDamage, SelfDamage, DamageCounters, VariableDamage
    Status:       StatusConditionEffect
    Board:        SwitchActive, ForceSwitch, ReturnToHand, ShuffleEffect, MillEffect,
                  EvolveEffect, DevolveEffect
    KO / Prize:   KnockOut, PrizeEffect
    Protection:   PreventDamage
    Ongoing:      PassiveEffect, RetreatCostEffect, AbilitySuppression
    Items:        ToolInteraction, StadiumInteraction
    Meta:         CopyAttack
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.cards.effects.actions import ActionTag, Frequency, Target, Zone
from src.cards.enums import PokemonType, StatusCondition

# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------


class Effect(BaseModel):
    """Abstract base for all card effects."""

    model_config = ConfigDict(frozen=True)

    action_type: ActionTag
    is_optional: bool = Field(
        default=False,
        description="True when the player may choose NOT to execute this effect.",
    )
    raw_text: str = Field(
        default="",
        description="The original sentence(s) this effect was parsed from.",
    )


# ---------------------------------------------------------------------------
# Structural / meta
# ---------------------------------------------------------------------------


class CompositeEffect(Effect):
    """An ordered sequence of effects executed in steps."""

    action_type: Literal[ActionTag.COMPOSITE] = ActionTag.COMPOSITE
    steps: tuple[Effect, ...] = Field(
        description="Ordered child effects. Execute step[0] first, then step[1], etc."
    )


class Condition(BaseModel):
    """A guard clause attached to a ConditionalEffect."""

    model_config = ConfigDict(frozen=True)

    raw: str = Field(description="Original guard clause text.")
    keyword: str = Field(
        description="Leading keyword: 'if', 'unless', 'when', 'as long as', etc."
    )
    negated: bool = Field(default=False, description="True when the condition is 'unless'.")


class ConditionalEffect(Effect):
    """An effect that only fires when a condition is satisfied."""

    action_type: Literal[ActionTag.CONDITIONAL] = ActionTag.CONDITIONAL
    condition: Condition
    then_effect: Effect
    else_effect: Effect | None = Field(
        default=None,
        description="Effect executed when the condition is NOT met (from 'If tails...' clauses).",
    )


class CoinFlipOutcome(BaseModel):
    """One branch of a coin flip result."""

    model_config = ConfigDict(frozen=True)

    result: Literal["heads", "tails", "both_heads", "both_tails", "either_heads"]
    effect: Effect


class CoinFlip(Effect):
    """Represents a coin-flip instruction and its consequence branches."""

    action_type: Literal[ActionTag.COIN_FLIP] = ActionTag.COIN_FLIP
    num_coins: int = Field(default=1, ge=1, description="Number of coins flipped.")
    until_tails: bool = Field(
        default=False,
        description="True for 'flip until tails' patterns.",
    )
    outcomes: tuple[CoinFlipOutcome, ...] = Field(
        description="Possible result branches (heads/tails). May be empty if outcome is just 'X for each heads'."
    )
    per_heads_effect: Effect | None = Field(
        default=None,
        description="Effect applied once for every heads result (e.g. 'X damage for each heads').",
    )


class UnknownEffect(Effect):
    """Graceful degradation for effect text that could not be parsed."""

    action_type: Literal[ActionTag.UNKNOWN] = ActionTag.UNKNOWN
    text: str = Field(description="The sentence(s) that could not be recognised.")


# ---------------------------------------------------------------------------
# Draw
# ---------------------------------------------------------------------------


class DrawCards(Effect):
    """Draw N cards from the top of your deck."""

    action_type: Literal[ActionTag.DRAW_CARDS] = ActionTag.DRAW_CARDS
    count: int | None = Field(
        default=None,
        description="Number of cards drawn. None means 'draw a card' with variable count.",
    )
    until_hand_size: int | None = Field(
        default=None,
        description="If set, draw until hand reaches this size.",
    )
    who: Target = Field(default=Target.ACTIVE_SELF)


# ---------------------------------------------------------------------------
# Discard
# ---------------------------------------------------------------------------


class DiscardEffect(Effect):
    """Discard cards from a zone."""

    action_type: Literal[ActionTag.DISCARD_ENERGY] = ActionTag.DISCARD_ENERGY
    source: Target = Field(default=Target.SELF)
    zone: Zone = Field(default=Zone.ACTIVE)
    count: int | None = Field(default=None, description="None means 'all' energy.")
    energy_type: PokemonType | None = Field(
        default=None,
        description="Specific energy type to discard. None means any type.",
    )
    card_type: str = Field(
        default="energy",
        description="What kind of card is discarded: 'energy', 'hand', 'tool', 'stadium', 'random'.",
    )
    # allow override of action_type for non-energy discards
    action_type: ActionTag = ActionTag.DISCARD_ENERGY


# ---------------------------------------------------------------------------
# Heal
# ---------------------------------------------------------------------------


class HealEffect(Effect):
    """Heal damage from a Pokémon."""

    action_type: Literal[ActionTag.HEAL] = ActionTag.HEAL
    amount: int | None = Field(
        default=None, description="Damage healed. None means 'heal all damage'."
    )
    target: Target = Field(default=Target.SELF)
    target_filter: str = Field(
        default="",
        description="Extra filter e.g. 'Benched {P} Pokémon', 'any of your Pokémon'.",
    )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class SearchDeck(Effect):
    """Search the deck for card(s) and put them into hand or onto Bench."""

    action_type: Literal[ActionTag.SEARCH_DECK] = ActionTag.SEARCH_DECK
    card_type: str = Field(
        description="What to search for: 'Basic Pokemon', 'Supporter', 'Energy', 'any', etc."
    )
    count: int | None = Field(
        default=1, description="Maximum cards to find. None means 'any number'."
    )
    destination: Zone = Field(default=Zone.HAND)
    energy_type: PokemonType | None = Field(default=None)
    attach_directly: bool = Field(
        default=False,
        description="True when the card is attached to a Pokémon rather than put into hand.",
    )
    reveal: bool = Field(default=False, description="Whether the found card is revealed.")
    filter_text: str = Field(default="", description="Additional filter from the card text.")


class SearchDiscard(Effect):
    """Retrieve card(s) from the discard pile."""

    action_type: Literal[ActionTag.SEARCH_DISCARD] = ActionTag.SEARCH_DISCARD
    card_type: str = Field(description="What to retrieve: 'Pokemon', 'Energy', 'Trainer', etc.")
    count: int | None = Field(default=1)
    destination: Zone = Field(default=Zone.HAND)
    energy_type: PokemonType | None = Field(default=None)


# ---------------------------------------------------------------------------
# Energy
# ---------------------------------------------------------------------------


class AttachEnergy(Effect):
    """Attach energy cards to a Pokémon."""

    action_type: Literal[ActionTag.ATTACH_ENERGY] = ActionTag.ATTACH_ENERGY
    source: Zone = Field(description="Where the energy comes from: hand, discard, deck.")
    target: Target = Field(default=Target.SELF)
    count: int = Field(default=1, ge=1)
    energy_type: PokemonType | None = Field(
        default=None, description="Specific type. None means any Basic Energy."
    )
    target_filter: str = Field(default="")


class MoveEnergy(Effect):
    """Move energy from one Pokémon to another."""

    action_type: Literal[ActionTag.MOVE_ENERGY] = ActionTag.MOVE_ENERGY
    from_target: Target = Field(default=Target.SELF)
    to_target: Target = Field(default=Target.BENCHED_SELF)
    count: int | None = Field(default=1, description="None means 'all energy'.")
    energy_type: PokemonType | None = Field(default=None)


# ---------------------------------------------------------------------------
# Damage modifiers
# ---------------------------------------------------------------------------


class DamageModifier(Effect):
    """This attack does X more or X less damage."""

    action_type: Literal[ActionTag.DAMAGE_MODIFIER] = ActionTag.DAMAGE_MODIFIER
    delta: int = Field(description="Positive = more damage, negative = less damage.")
    target: Target = Field(default=Target.ACTIVE_OPP)
    ignore_weakness: bool = Field(default=False)
    ignore_resistance: bool = Field(default=False)
    condition_text: str = Field(default="")


class BenchDamage(Effect):
    """This attack also does X damage to Benched Pokémon."""

    action_type: Literal[ActionTag.BENCH_DAMAGE] = ActionTag.BENCH_DAMAGE
    amount: int
    target: Target = Field(default=Target.BENCHED_OPP)
    count: int | None = Field(default=None, description="Number of targets. None means all.")


class SelfDamage(Effect):
    """This Pokémon also does X damage to itself (recoil)."""

    action_type: Literal[ActionTag.SELF_DAMAGE] = ActionTag.SELF_DAMAGE
    amount: int


class DamageCounters(Effect):
    """Place N damage counters on a Pokémon (not modified by Weakness/Resistance)."""

    action_type: Literal[ActionTag.DAMAGE_COUNTERS] = ActionTag.DAMAGE_COUNTERS
    count: int | None = Field(default=None, description="None means 'until HP is X'.")
    target: Target = Field(default=Target.ACTIVE_OPP)
    target_filter: str = Field(default="")
    until_hp: int | None = Field(default=None, description="Place until remaining HP equals this.")


class VariableDamage(Effect):
    """Damage that scales with a countable quantity."""

    action_type: Literal[ActionTag.VARIABLE_DAMAGE] = ActionTag.VARIABLE_DAMAGE
    base_per_unit: int = Field(description="Damage dealt per unit counted.")
    scale_by: str = Field(description="What is counted: 'energy_attached', 'bench_pokemon', etc.")
    target: Target = Field(default=Target.ACTIVE_OPP)
    multiplicative: bool = Field(
        default=True,
        description="False when the base attack damage is fixed and this adds on top.",
    )


# ---------------------------------------------------------------------------
# Status conditions
# ---------------------------------------------------------------------------


class StatusConditionEffect(Effect):
    """Apply a Special Condition to a Pokémon."""

    action_type: Literal[ActionTag.INFLICT_STATUS] = ActionTag.INFLICT_STATUS
    condition: StatusCondition
    target: Target = Field(default=Target.ACTIVE_OPP)
    # allow child to override
    action_type: ActionTag = ActionTag.INFLICT_STATUS


# ---------------------------------------------------------------------------
# Board manipulation
# ---------------------------------------------------------------------------


class SwitchActive(Effect):
    """Switch your Active Pokémon with one of your Benched Pokémon."""

    action_type: Literal[ActionTag.SWITCH_ACTIVE] = ActionTag.SWITCH_ACTIVE
    who: Target = Field(default=Target.ACTIVE_SELF, description="Whose active is switched.")


class ForceSwitch(Effect):
    """Force the opponent to switch their Active Pokémon."""

    action_type: Literal[ActionTag.FORCE_SWITCH] = ActionTag.FORCE_SWITCH
    from_bench: bool = Field(
        default=True,
        description="If True, switch in a specific Benched Pokémon. "
        "If False, opponent retreats to bench.",
    )
    opponent_chooses: bool = Field(
        default=False,
        description="True when opponent chooses which Pokémon replaces the active.",
    )


class ReturnToHand(Effect):
    """Return Pokémon (and attached cards) to a player's hand."""

    action_type: Literal[ActionTag.RETURN_TO_HAND] = ActionTag.RETURN_TO_HAND
    target: Target = Field(default=Target.BENCHED_SELF)
    include_attached: bool = Field(default=True)


class ShuffleEffect(Effect):
    """Shuffle the deck, or shuffle hand into deck."""

    action_type: Literal[ActionTag.SHUFFLE_DECK] = ActionTag.SHUFFLE_DECK
    hand_first: bool = Field(
        default=False, description="True when hand is shuffled into deck before drawing."
    )
    draw_after: int | None = Field(
        default=None, description="Cards drawn after shuffling."
    )
    who: Target = Field(default=Target.ACTIVE_SELF)


class MillEffect(Effect):
    """Discard cards from the top of a player's deck."""

    action_type: Literal[ActionTag.MILL] = ActionTag.MILL
    count: int = Field(ge=1)
    who: Target = Field(default=Target.ACTIVE_OPP)


class EvolveEffect(Effect):
    """Evolve a Pokémon in play."""

    action_type: Literal[ActionTag.EVOLVE] = ActionTag.EVOLVE
    target: Target = Field(default=Target.ANY_SELF)
    from_hand: bool = Field(default=True)
    skip_stage: bool = Field(default=False, description="True for Rare Candy effects.")


class DevolveEffect(Effect):
    """Devolve an evolved Pokémon."""

    action_type: Literal[ActionTag.DEVOLVE] = ActionTag.DEVOLVE
    target: Target = Field(default=Target.ANY_OPP)
    put_in: Zone = Field(default=Zone.HAND, description="Where the evolution card goes.")


# ---------------------------------------------------------------------------
# KO / Prize
# ---------------------------------------------------------------------------


class KnockOut(Effect):
    """Knock Out a Pokémon directly."""

    action_type: Literal[ActionTag.KNOCK_OUT] = ActionTag.KNOCK_OUT
    target: Target = Field(default=Target.ACTIVE_OPP)
    target_filter: str = Field(default="")


class PrizeEffect(Effect):
    """Interact with Prize cards."""

    action_type: Literal[ActionTag.PRIZE] = ActionTag.PRIZE
    take: int = Field(default=1, description="Number of extra Prize cards taken.")
    look: bool = Field(default=False, description="True for 'look at face-down Prize' effects.")
    who: Target = Field(default=Target.ACTIVE_SELF)


# ---------------------------------------------------------------------------
# Prevention
# ---------------------------------------------------------------------------


class PreventDamage(Effect):
    """Prevent damage done to a Pokémon."""

    action_type: Literal[ActionTag.PREVENT_DAMAGE] = ActionTag.PREVENT_DAMAGE
    target: Target = Field(default=Target.SELF)
    all_damage: bool = Field(default=False, description="True for 'prevent all damage'.")
    max_damage: int | None = Field(
        default=None,
        description="Prevent damage only when that damage is at or below this value.",
    )
    from_filter: str = Field(
        default="",
        description="Restrict which attacker is prevented (e.g. 'Basic Pokemon').",
    )
    include_effects: bool = Field(
        default=False, description="True when effects of attacks are also prevented."
    )


# ---------------------------------------------------------------------------
# Ongoing / passive
# ---------------------------------------------------------------------------


class PassiveEffect(Effect):
    """An ongoing effect that is active while the card is in play."""

    action_type: Literal[ActionTag.PASSIVE] = ActionTag.PASSIVE
    frequency: Frequency = Field(default=Frequency.PASSIVE)
    trigger: str = Field(
        default="",
        description="Trigger condition for TRIGGERED / ONCE_PER_TURN abilities.",
    )
    sub_effect: Effect | None = Field(
        default=None,
        description="The effect executed when the ability fires.",
    )
    description: str = Field(
        default="",
        description="Human-readable description of the passive (for explainability).",
    )


class RetreatCostEffect(Effect):
    """Modify the Retreat Cost of a Pokémon."""

    action_type: Literal[ActionTag.RETREAT_COST] = ActionTag.RETREAT_COST
    delta: int = Field(
        description="Negative = cheaper retreat, positive = more expensive."
    )
    target: Target = Field(default=Target.SELF)
    target_filter: str = Field(default="")


class AbilitySuppression(Effect):
    """Suppress Abilities on Pokémon in play."""

    action_type: Literal[ActionTag.ABILITY_SUPPRESSION] = ActionTag.ABILITY_SUPPRESSION
    target: Target = Field(default=Target.ANY_OPP)
    target_filter: str = Field(
        default="",
        description="Narrow which Pokémon are suppressed.",
    )


# ---------------------------------------------------------------------------
# Tool / Stadium
# ---------------------------------------------------------------------------


class ToolInteraction(Effect):
    """Interact with Pokémon Tools."""

    action_type: Literal[ActionTag.TOOL_INTERACTION] = ActionTag.TOOL_INTERACTION
    operation: str = Field(description="'discard', 'attach', 'suppress', etc.")
    target: Target = Field(default=Target.ANY_OPP)


class StadiumInteraction(Effect):
    """Interact with a Stadium card."""

    action_type: Literal[ActionTag.STADIUM_INTERACTION] = ActionTag.STADIUM_INTERACTION
    operation: str = Field(description="'discard', 'prevent_play', 'check_in_play', etc.")


# ---------------------------------------------------------------------------
# Copy
# ---------------------------------------------------------------------------


class CopyAttack(Effect):
    """Copy an attack from another Pokémon and use it."""

    action_type: Literal[ActionTag.COPY_ATTACK] = ActionTag.COPY_ATTACK
    copy_from: str = Field(
        description="'opponent_active', 'benched', 'specific_name', etc."
    )

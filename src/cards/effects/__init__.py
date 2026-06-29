"""
Semantic effect parser — converts raw card text into structured actions.

Public surface::

    from src.cards.effects import EffectParser, parse_effect, CompiledCard

    parser = EffectParser()
    result = parser.parse("Draw 2 cards. Then discard an Energy from this Pokémon.")
    # → CompositeEffect([DrawCards(count=2), DiscardEnergy(source='self', count=1)])

    compiled = parser.compile_card(pokemon_card)
    compiled.attack_effects[0]   # list[Effect] for first attack
    compiled.ability_effect       # Effect | None
"""

from src.cards.effects.compiler import CompiledCard, compile_card
from src.cards.effects.models import (
    AbilitySuppression,
    AttachEnergy,
    BenchDamage,
    CoinFlip,
    CompositeEffect,
    ConditionalEffect,
    DamageCounters,
    DamageModifier,
    DevolveEffect,
    DiscardEffect,
    DrawCards,
    Effect,
    EvolveEffect,
    ForceSwitch,
    HealEffect,
    KnockOut,
    MillEffect,
    MoveEnergy,
    PassiveEffect,
    PreventDamage,
    PrizeEffect,
    RetreatCostEffect,
    ReturnToHand,
    SearchDeck,
    SelfDamage,
    ShuffleEffect,
    StadiumInteraction,
    StatusConditionEffect,
    SwitchActive,
    ToolInteraction,
    UnknownEffect,
    VariableDamage,
)
from src.cards.effects.parser import EffectParser, parse_effect

__all__ = [
    "EffectParser",
    "parse_effect",
    "compile_card",
    "CompiledCard",
    "Effect",
    "CompositeEffect",
    "UnknownEffect",
    "DrawCards",
    "DiscardEffect",
    "HealEffect",
    "SearchDeck",
    "AttachEnergy",
    "MoveEnergy",
    "StatusConditionEffect",
    "CoinFlip",
    "ConditionalEffect",
    "DamageModifier",
    "BenchDamage",
    "SelfDamage",
    "DamageCounters",
    "SwitchActive",
    "ForceSwitch",
    "PreventDamage",
    "PrizeEffect",
    "MillEffect",
    "ReturnToHand",
    "KnockOut",
    "ShuffleEffect",
    "PassiveEffect",
    "VariableDamage",
    "EvolveEffect",
    "DevolveEffect",
    "RetreatCostEffect",
    "AbilitySuppression",
    "ToolInteraction",
    "StadiumInteraction",
]

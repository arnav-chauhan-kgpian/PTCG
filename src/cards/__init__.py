"""
Pokémon TCG card knowledge layer.

Public surface:
    CardRepository  — main entry point for all card lookups
    load_repository — convenience factory that loads and validates the CSV
"""

from src.cards.enums import (
    CardCategory,
    DamageModifier,
    EnergyType,
    ExpansionCode,
    PokemonType,
    RuleBox,
    Stage,
    TrainerType,
)
from src.cards.exceptions import (
    CardNotFoundError,
    DuplicateCardError,
    InvalidCardDataError,
    ParseError,
)
from src.cards.models import Ability, Attack, Card, EnergyCard, PokemonCard, TrainerCard
from src.cards.repository import CardRepository, load_repository

__all__ = [
    "CardRepository",
    "load_repository",
    "Card",
    "PokemonCard",
    "TrainerCard",
    "EnergyCard",
    "Attack",
    "Ability",
    "PokemonType",
    "TrainerType",
    "EnergyType",
    "Stage",
    "CardCategory",
    "ExpansionCode",
    "RuleBox",
    "DamageModifier",
    "CardNotFoundError",
    "DuplicateCardError",
    "InvalidCardDataError",
    "ParseError",
]

"""
Pydantic v2 data models for the Pokémon TCG card knowledge layer.

Design principles:
  - All models are immutable (model_config frozen=True).
  - No raw dicts escape to callers; every field has an explicit type.
  - Union discriminated via card_super_type field for fast isinstance-free dispatch.
  - Attacks and Abilities are separate models; both live on PokemonCard.
  - EnergyCost is a parsed list of tokens, not a raw string.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.cards.enums import (
    CardCategory,
    CardSuperType,
    DamageModifier,
    EnergyType,
    ExpansionCode,
    PokemonType,
    RuleBox,
    Stage,
    TrainerType,
)
from src.cards.types import CardId

# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class EnergyCostModel(BaseModel):
    """Parsed representation of an attack's energy cost."""

    model_config = ConfigDict(frozen=True)

    tokens: tuple[str, ...] = Field(
        default=(),
        description="Ordered energy tokens, e.g. ('{G}', '{C}', '{C}').",
    )
    total_count: int = Field(
        ge=0, description="Total number of energy symbols required."
    )

    @classmethod
    def free(cls) -> EnergyCostModel:
        """Represents 'No cost' attacks."""
        return cls(tokens=(), total_count=0)

    @property
    def colorless_count(self) -> int:
        return sum(1 for t in self.tokens if t == "{C}")

    @property
    def is_free(self) -> bool:
        return self.total_count == 0


class DamageValue(BaseModel):
    """Parsed representation of attack damage."""

    model_config = ConfigDict(frozen=True)

    base: int = Field(
        default=0,
        description="Numeric base damage (0 when n/a or variable-only).",
    )
    modifier: DamageModifier = Field(
        default=DamageModifier.NONE,
        description="Qualifier: exact, variable (×), n/a, or negative.",
    )
    raw: str = Field(description="Original string from the CSV for full fidelity.")

    @property
    def is_variable(self) -> bool:
        return self.modifier == DamageModifier.VARIABLE

    @property
    def has_damage(self) -> bool:
        return self.modifier != DamageModifier.NONE


class WeaknessModel(BaseModel):
    """Pokémon weakness to a specific type (always ×2 in current format)."""

    model_config = ConfigDict(frozen=True)

    energy_type: PokemonType
    multiplier: int = Field(default=2, ge=1)


class ResistanceModel(BaseModel):
    """Pokémon resistance to a specific type (always −30 in current format)."""

    model_config = ConfigDict(frozen=True)

    energy_type: PokemonType
    reduction: int = Field(default=30, ge=0)


# ---------------------------------------------------------------------------
# Attack and Ability
# ---------------------------------------------------------------------------


class Attack(BaseModel):
    """A single attack belonging to a Pokémon card."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Attack name as printed.")
    cost: EnergyCostModel = Field(description="Energy required to use this attack.")
    damage: DamageValue = Field(description="Damage dealt by this attack.")
    effect: str = Field(
        default="",
        description="Full effect text. Empty string when there is no effect.",
    )


class Ability(BaseModel):
    """A Pokémon Ability (identified by [Ability] prefix in the CSV)."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Ability name without the [Ability] prefix.")
    effect: str = Field(description="Full ability effect text.")


class TeraAbility(BaseModel):
    """Tera-type passive rule (identified by [Tera] in Move Name column)."""

    model_config = ConfigDict(frozen=True)

    effect: str = Field(description="Full Tera rule-box text.")


# ---------------------------------------------------------------------------
# Base card
# ---------------------------------------------------------------------------


class Card(BaseModel):
    """Shared fields present on every card type."""

    model_config = ConfigDict(frozen=True)

    card_id: CardId = Field(description="Unique numeric identifier from the CSV.")
    name: str = Field(description="Card name as printed.")
    expansion: ExpansionCode = Field(description="Set code, e.g. SVE, TWM.")
    collection_number: str = Field(
        description="Set-specific collector number (may contain letters)."
    )
    rule_box: RuleBox = Field(default=RuleBox.NONE)
    category: CardCategory = Field(default=CardCategory.NONE)
    card_super_type: CardSuperType


# ---------------------------------------------------------------------------
# Concrete card types
# ---------------------------------------------------------------------------


class PokemonCard(Card):
    """A Pokémon card with full stats and move list."""

    card_super_type: Literal[CardSuperType.POKEMON] = CardSuperType.POKEMON

    stage: Stage
    previous_stage: str | None = Field(
        default=None,
        description="Name of the Pokémon this evolves from, or None for Basic.",
    )
    hp: int = Field(ge=10, description="Hit points printed on the card.")
    pokemon_type: PokemonType = Field(description="Elemental type.")
    weakness: WeaknessModel | None = Field(default=None)
    resistance: ResistanceModel | None = Field(default=None)
    retreat_cost: int = Field(
        ge=0,
        le=5,
        description="Number of Energy cards needed to retreat.",
    )

    ability: Ability | None = Field(default=None)
    tera_ability: TeraAbility | None = Field(
        default=None,
        description="Present only on Tera Pokémon ex cards.",
    )
    attacks: tuple[Attack, ...] = Field(
        default=(),
        description="Ordered tuple of attacks; most cards have 1-2.",
    )

    @property
    def is_ex(self) -> bool:
        return self.rule_box in (RuleBox.POKEMON_EX, RuleBox.MEGA_POKEMON_EX)

    @property
    def is_tera(self) -> bool:
        return self.tera_ability is not None

    @property
    def is_ancient(self) -> bool:
        return self.category == CardCategory.ANCIENT

    @property
    def is_future(self) -> bool:
        return self.category == CardCategory.FUTURE

    @property
    def evolves_from(self) -> str | None:
        return self.previous_stage


class TrainerCard(Card):
    """An Item, Supporter, Stadium, or Pokémon Tool card."""

    card_super_type: Literal[CardSuperType.TRAINER] = CardSuperType.TRAINER

    trainer_type: TrainerType
    effect: str = Field(description="Primary effect text.")

    # Fossil Items and Technical Machine tools can have an embedded ability/attack
    embedded_ability: Ability | None = Field(
        default=None,
        description="Ability granted when played as a Pokémon (Fossil/TM cards).",
    )
    embedded_attack: Attack | None = Field(
        default=None,
        description="Attack granted when played as a Pokémon Tool (TM cards).",
    )

    @property
    def is_fossil(self) -> bool:
        return self.category == CardCategory.FOSSIL

    @property
    def is_technical_machine(self) -> bool:
        return self.category == CardCategory.TECHNICAL_MACHINE

    @property
    def is_ace_spec(self) -> bool:
        return self.rule_box == RuleBox.ACE_SPEC


class EnergyCard(Card):
    """A Basic or Special Energy card."""

    card_super_type: Literal[CardSuperType.ENERGY] = CardSuperType.ENERGY

    energy_type: EnergyType
    provides: tuple[PokemonType, ...] = Field(
        description="Type(s) of energy this card provides. "
        "Basic energies provide exactly one type. "
        "Special energies may provide multiple or conditional types.",
    )
    effect: str = Field(
        default="",
        description="Effect text for Special Energy cards. Empty for Basic.",
    )

    @property
    def is_basic(self) -> bool:
        return self.energy_type == EnergyType.BASIC

    @property
    def is_special(self) -> bool:
        return self.energy_type == EnergyType.SPECIAL

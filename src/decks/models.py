"""
Core deck data models.

A Deck is an ordered collection of DeckSlots (card + count), immutable
and validated externally by validators.py.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.cards.enums import (
    CardSuperType,
    Stage,
)
from src.cards.models import (  # noqa: F401 (forward refs for model_rebuild)
    EnergyCard,
    PokemonCard,
    TrainerCard,
)
from src.cards.types import AnyCard


class DeckSlot(BaseModel):
    """One unique card and how many copies appear in the deck."""

    model_config = ConfigDict(frozen=True)

    card: AnyCard
    count: int = Field(ge=1, le=60)

    @property
    def card_id(self) -> str:
        return str(self.card.card_id)

    @property
    def name(self) -> str:
        return self.card.name


class Deck(BaseModel):
    """A 60-card Pokémon TCG deck represented as unique slots."""

    model_config = ConfigDict(frozen=True)

    name: str = ""
    slots: tuple[DeckSlot, ...]

    # ------------------------------------------------------------------
    # Convenience views
    # ------------------------------------------------------------------

    @property
    def total_count(self) -> int:
        return sum(s.count for s in self.slots)

    def all_cards(self) -> list[AnyCard]:
        """Expand slots → flat list (with repetition)."""
        result: list[AnyCard] = []
        for slot in self.slots:
            result.extend([slot.card] * slot.count)
        return result

    def pokemon_slots(self) -> list[DeckSlot]:
        return [s for s in self.slots if s.card.card_super_type == CardSuperType.POKEMON]

    def trainer_slots(self) -> list[DeckSlot]:
        return [s for s in self.slots if s.card.card_super_type == CardSuperType.TRAINER]

    def energy_slots(self) -> list[DeckSlot]:
        return [s for s in self.slots if s.card.card_super_type == CardSuperType.ENERGY]

    def basic_pokemon_slots(self) -> list[DeckSlot]:
        return [
            s for s in self.slots
            if isinstance(s.card, PokemonCard) and s.card.stage == Stage.BASIC
        ]

    def unique_card_ids(self) -> set[str]:
        return {s.card_id for s in self.slots}


# Rebuild models after all concrete types are imported
DeckSlot.model_rebuild()
Deck.model_rebuild()

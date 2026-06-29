"""
Builder-level validation — thin wrapper over Phase 5 DeckValidator
plus builder-specific checks.
"""

from __future__ import annotations

from src.deck_builder.constraints import (
    ConstraintConfig,
    ConstraintViolation,
)
from src.deck_builder.constraints import (
    check_all as _check_all,
)
from src.decks.models import Deck, DeckSlot
from src.decks.validators import DeckValidator as _Phase5Validator
from src.decks.validators import ValidationReport


def validate_slots(
    slots: dict[str, tuple],
    config: ConstraintConfig | None = None,
) -> list[ConstraintViolation]:
    return _check_all(slots, config or ConstraintConfig())


def slots_to_deck(slots: dict[str, tuple], name: str = "") -> Deck:
    return Deck(
        name=name,
        slots=tuple(DeckSlot(card=c, count=n) for c, n in slots.values() if n > 0),
    )


def validate_deck(deck: Deck) -> ValidationReport:
    return _Phase5Validator().validate(deck)

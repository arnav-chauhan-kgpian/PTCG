"""
Safe card-repository lookup helpers.

The simulator stores ``card_id`` as a string on ``CardInstance`` for
serialization consistency, while the repository indexes by int and raises
on miss.  This module bridges the two.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.cards.models import Card
    from src.cards.repository import CardRepository


def safe_get(repository: CardRepository, card_id) -> Card | None:
    """Look up a card by id (str or int), returning None on miss."""
    if card_id is None:
        return None
    try:
        return repository.get_by_id(int(card_id))
    except Exception:
        return None


def safe_lookup_fn(repository: CardRepository) -> Callable[[object], Card | None]:
    """Return a ``f(card_id) -> Card | None`` closure for use in engines."""
    def _fn(card_id):
        return safe_get(repository, card_id)
    return _fn

"""
Custom exceptions for the card knowledge layer.

All exceptions inherit from PTCGError so callers can catch the
entire domain with a single except clause when desired.
"""


class PTCGError(Exception):
    """Base exception for the PTCG project."""


class ParseError(PTCGError):
    """Raised when a CSV row cannot be parsed into a card model."""

    def __init__(self, row_number: int, card_id: str, message: str) -> None:
        self.row_number = row_number
        self.card_id = card_id
        super().__init__(f"Row {row_number} (Card ID={card_id!r}): {message}")


class NormalizationError(PTCGError):
    """Raised when a field value cannot be normalized."""

    def __init__(self, field: str, value: str, message: str) -> None:
        self.field = field
        self.raw_value = value
        super().__init__(f"Cannot normalize {field}={value!r}: {message}")


class CardNotFoundError(PTCGError):
    """Raised when a card cannot be located in the repository."""

    def __init__(self, query: str) -> None:
        self.query = query
        super().__init__(f"Card not found: {query!r}")


class DuplicateCardError(PTCGError):
    """Raised when two distinct cards share the same ID."""

    def __init__(self, card_id: int) -> None:
        self.card_id = card_id
        super().__init__(f"Duplicate card ID detected: {card_id}")


class InvalidCardDataError(PTCGError):
    """Raised when a card's data is internally inconsistent."""

    def __init__(self, card_id: int, message: str) -> None:
        self.card_id = card_id
        super().__init__(f"Card {card_id}: {message}")


class RepositoryNotLoadedError(PTCGError):
    """Raised when the repository is queried before data has been loaded."""

    def __init__(self) -> None:
        super().__init__(
            "CardRepository has not been loaded. Call load_repository() first."
        )

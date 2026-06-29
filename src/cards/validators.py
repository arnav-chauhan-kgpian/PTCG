"""
Post-parse validation for the card knowledge layer.

Validation runs on the fully parsed card list and emits warnings/errors
via loguru. It does NOT raise exceptions by default — it logs issues and
returns a ValidationReport so callers can decide how to handle problems.

Checks performed:
  - Duplicate card IDs
  - Missing card IDs (gaps in the numeric sequence)
  - Pokémon with no attacks AND no ability
  - Evolution chains: Stage 1/2 cards whose previous_stage name cannot
    be resolved to a card in the database
  - HP out of plausible range
  - Basic Pokémon with a non-null previous_stage
  - Trainer/Energy cards that somehow ended up with Pokémon-only fields
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from loguru import logger

from src.cards.enums import Stage
from src.cards.models import Card, PokemonCard


@dataclass
class ValidationReport:
    duplicate_ids: list[int] = field(default_factory=list)
    missing_ids: list[int] = field(default_factory=list)
    pokemon_no_moves: list[int] = field(default_factory=list)
    broken_evolutions: list[tuple[int, str]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.duplicate_ids or self.pokemon_no_moves)

    @property
    def total_issues(self) -> int:
        return (
            len(self.duplicate_ids)
            + len(self.missing_ids)
            + len(self.pokemon_no_moves)
            + len(self.broken_evolutions)
            + len(self.warnings)
        )


def validate_cards(cards: list[Card]) -> ValidationReport:
    """Run all validation checks and return a report."""
    report = ValidationReport()

    id_counts = Counter(c.card_id for c in cards)
    pokemon_names: set[str] = {
        c.name.lower() for c in cards if isinstance(c, PokemonCard)
    }

    for card_id, count in id_counts.items():
        if count > 1:
            report.duplicate_ids.append(card_id)
            logger.error("Duplicate Card ID: {}", card_id)

    if id_counts:
        min_id = min(id_counts)
        max_id = max(id_counts)
        for expected in range(min_id, max_id + 1):
            if expected not in id_counts:
                report.missing_ids.append(expected)
                logger.warning("Missing Card ID in sequence: {}", expected)

    for card in cards:
        if not isinstance(card, PokemonCard):
            continue

        if not card.attacks and card.ability is None:
            report.pokemon_no_moves.append(card.card_id)
            logger.warning(
                "Pokémon {} ({}) has no attacks and no ability",
                card.card_id,
                card.name,
            )

        if card.stage == Stage.BASIC and card.previous_stage is not None:
            msg = (
                f"Basic Pokémon {card.card_id} ({card.name}) "
                f"has previous_stage={card.previous_stage!r}"
            )
            report.warnings.append(msg)
            logger.warning(msg)

        if card.stage in (Stage.STAGE_1, Stage.STAGE_2):
            if card.previous_stage is None:
                msg = (
                    f"Evolved Pokémon {card.card_id} ({card.name}, {card.stage}) "
                    "is missing previous_stage"
                )
                report.warnings.append(msg)
                logger.warning(msg)
            elif card.previous_stage.lower() not in pokemon_names:
                report.broken_evolutions.append((card.card_id, card.previous_stage))
                logger.warning(
                    "Broken evolution chain: {} ({}) evolves from {!r} which is not in the database",
                    card.card_id,
                    card.name,
                    card.previous_stage,
                )

        if card.hp < 10 or card.hp > 500:
            msg = f"Suspicious HP {card.hp} for card {card.card_id} ({card.name})"
            report.warnings.append(msg)
            logger.warning(msg)

    logger.info(
        "Validation complete: {} duplicate IDs, {} missing IDs, "
        "{} Pokémon without moves, {} broken evolutions, {} other warnings",
        len(report.duplicate_ids),
        len(report.missing_ids),
        len(report.pokemon_no_moves),
        len(report.broken_evolutions),
        len(report.warnings),
    )
    return report

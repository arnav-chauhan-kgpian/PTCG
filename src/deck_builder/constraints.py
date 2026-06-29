"""
Hard constraint definitions and checking for deck construction.

Constraints are evaluated over a mutable slot dict rather than frozen Deck
objects so the builder can check legality during construction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.cards.enums import EnergyType, RuleBox

if TYPE_CHECKING:
    pass


@dataclass(frozen=True)
class ConstraintViolation:
    code: str
    message: str
    severity: str = "error"  # "error" | "warning"


@dataclass
class ConstraintConfig:
    """Configurable constraint parameters."""
    deck_size: int = 60
    max_copies: int = 4
    max_ace_spec: int = 1
    require_basic_pokemon: bool = True
    check_evolution_legality: bool = True
    check_energy_sanity: bool = True
    allowed_expansions: frozenset[str] = field(default_factory=frozenset)  # empty = all


# ---------------------------------------------------------------------------
# Slot dict type alias
# ---------------------------------------------------------------------------
# slots: dict[str, tuple[AnyCard, int]]   card_id -> (card, count)

def check_all(
    slots: dict[str, tuple],
    config: ConstraintConfig,
) -> list[ConstraintViolation]:
    violations: list[ConstraintViolation] = []
    violations.extend(_check_size(slots, config))
    violations.extend(_check_copy_limits(slots, config))
    violations.extend(_check_basics(slots, config))
    violations.extend(_check_ace_spec(slots, config))
    violations.extend(_check_evolution(slots, config))
    violations.extend(_check_expansion(slots, config))
    return violations


def is_legal(slots: dict[str, tuple], config: ConstraintConfig) -> bool:
    return all(v.severity != "error" for v in check_all(slots, config))


def total_count(slots: dict[str, tuple]) -> int:
    return sum(count for _, count in slots.values())


def _check_size(slots, config) -> list[ConstraintViolation]:
    n = total_count(slots)
    if n != config.deck_size:
        return [ConstraintViolation(
            code="DECK_SIZE",
            message=f"Deck has {n} cards, must be exactly {config.deck_size}.",
        )]
    return []


def _check_copy_limits(slots, config) -> list[ConstraintViolation]:
    violations: list[ConstraintViolation] = []
    # Group by name — TCG rules apply copy limits per card name
    name_counts: dict[str, int] = {}
    name_is_basic_energy: dict[str, bool] = {}
    for card, count in slots.values():
        name = card.name
        name_counts[name] = name_counts.get(name, 0) + count
        from src.cards.models import EnergyCard
        if isinstance(card, EnergyCard) and card.energy_type == EnergyType.BASIC:
            name_is_basic_energy[name] = True
    for name, count in name_counts.items():
        if name_is_basic_energy.get(name):
            continue
        if count > config.max_copies:
            violations.append(ConstraintViolation(
                code="COPY_LIMIT",
                message=f"'{name}': {count} copies exceeds limit of {config.max_copies}.",
            ))
    return violations


def _check_basics(slots, config) -> list[ConstraintViolation]:
    if not config.require_basic_pokemon:
        return []
    from src.cards.enums import Stage
    from src.cards.models import PokemonCard
    has_basic = any(
        isinstance(card, PokemonCard) and card.stage == Stage.BASIC
        for card, _ in slots.values()
    )
    if not has_basic:
        return [ConstraintViolation(
            code="NO_BASIC_POKEMON",
            message="Deck has no Basic Pokémon.",
        )]
    return []


def _check_ace_spec(slots, config) -> list[ConstraintViolation]:
    ace_count = sum(
        count for card, count in slots.values()
        if card.rule_box == RuleBox.ACE_SPEC
    )
    if ace_count > config.max_ace_spec:
        return [ConstraintViolation(
            code="ACE_SPEC_LIMIT",
            message=f"Deck has {ace_count} ACE SPEC cards, limit is {config.max_ace_spec}.",
        )]
    return []


def _check_evolution(slots, config) -> list[ConstraintViolation]:
    if not config.check_evolution_legality:
        return []
    from src.cards.models import PokemonCard
    names = {card.name for card, _ in slots.values()}
    violations: list[ConstraintViolation] = []
    for card, _ in slots.values():
        if isinstance(card, PokemonCard) and card.previous_stage:
            if card.previous_stage not in names:
                violations.append(ConstraintViolation(
                    code="MISSING_PRE_EVOLUTION",
                    message=f"'{card.name}' requires '{card.previous_stage}' which is not in deck.",
                    severity="warning",
                ))
    return violations


def _check_expansion(slots, config) -> list[ConstraintViolation]:
    if not config.allowed_expansions:
        return []
    violations: list[ConstraintViolation] = []
    for card, _ in slots.values():
        if card.expansion.value not in config.allowed_expansions:
            violations.append(ConstraintViolation(
                code="EXPANSION_BANNED",
                message=f"'{card.name}' from expansion '{card.expansion.value}' not in allowed set.",
            ))
    return violations

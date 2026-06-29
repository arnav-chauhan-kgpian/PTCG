"""
Post-parse validation for compiled cards.

Validates that parsed effects are semantically consistent with the card
that produced them, and reports any issues without raising.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.cards.effects.compiler import CompiledCard
from src.cards.effects.models import Effect, UnknownEffect


@dataclass
class ValidationIssue:
    card_id: str
    name: str
    location: str       # e.g. "attack:Hydro Pump", "ability", "trainer"
    message: str
    severity: str = "warning"  # "warning" or "error"


@dataclass
class EffectValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def unknown_count(self) -> int:
        return sum(1 for i in self.issues if "UnknownEffect" in i.message)

    def is_clean(self) -> bool:
        return len(self.errors) == 0


def _count_unknowns(effect: Effect) -> int:
    """Recursively count UnknownEffect nodes."""
    from src.cards.effects.models import CoinFlip, CompositeEffect, ConditionalEffect
    if isinstance(effect, UnknownEffect):
        return 1
    total = 0
    if isinstance(effect, CompositeEffect):
        for step in effect.steps:
            total += _count_unknowns(step)
    if isinstance(effect, ConditionalEffect):
        total += _count_unknowns(effect.then_effect)
        if effect.else_effect:
            total += _count_unknowns(effect.else_effect)
    if isinstance(effect, CoinFlip):
        for outcome in effect.outcomes:
            total += _count_unknowns(outcome.effect)
        if effect.per_heads_effect:
            total += _count_unknowns(effect.per_heads_effect)
    return total


def validate_compiled(card: CompiledCard) -> EffectValidationReport:
    """Validate a single CompiledCard and return a report."""
    report = EffectValidationReport()

    def check(effect: Effect | None, location: str) -> None:
        if effect is None:
            return
        n = _count_unknowns(effect)
        if n > 0:
            report.issues.append(ValidationIssue(
                card_id=card.card_id,
                name=card.name,
                location=location,
                message=f"{n} UnknownEffect node(s) — text not parsed",
                severity="warning",
            ))

    for attack_name, eff in card.attack_effects.items():
        check(eff, f"attack:{attack_name}")

    check(card.ability_effect, "ability")
    check(card.trainer_effect, "trainer")
    check(card.energy_effect, "energy")

    return report


def validate_all(
    compiled_cards: list[CompiledCard],
) -> EffectValidationReport:
    """Validate a batch of CompiledCards and aggregate results."""
    aggregate = EffectValidationReport()
    for card in compiled_cards:
        result = validate_compiled(card)
        aggregate.issues.extend(result.issues)
    return aggregate

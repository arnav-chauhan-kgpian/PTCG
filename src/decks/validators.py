"""
Deck legality validation.

Returns structured ValidationReport — never raises.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from src.cards.enums import EnergyType, RuleBox, Stage
from src.cards.models import EnergyCard, PokemonCard
from src.decks.models import Deck


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"  # "error" | "warning"
    card_name: str = ""


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def is_legal(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = [f"Legal: {self.is_legal} ({len(self.errors)} errors, {len(self.warnings)} warnings)"]
        for i in self.issues:
            lines.append(f"  [{i.severity.upper()}] {i.code}: {i.message}")
        return "\n".join(lines)


class DeckValidator:
    """Validates a Deck against standard Pokémon TCG rules."""

    DECK_SIZE = 60
    MAX_COPIES = 4
    MAX_ACE_SPEC = 1

    def validate(self, deck: Deck) -> ValidationReport:
        report = ValidationReport()
        self._check_size(deck, report)
        self._check_copy_limits(deck, report)
        self._check_has_basic(deck, report)
        self._check_ace_spec(deck, report)
        self._check_evolution_legality(deck, report)
        self._check_energy_sanity(deck, report)
        return report

    # ------------------------------------------------------------------

    def _check_size(self, deck: Deck, report: ValidationReport) -> None:
        total = deck.total_count
        if total != self.DECK_SIZE:
            report.issues.append(ValidationIssue(
                code="DECK_SIZE",
                message=f"Deck has {total} cards, must be exactly {self.DECK_SIZE}.",
                severity="error",
            ))

    def _check_copy_limits(self, deck: Deck, report: ValidationReport) -> None:
        for slot in deck.slots:
            card = slot.card
            # Basic Energy: unlimited copies
            if isinstance(card, EnergyCard) and card.energy_type == EnergyType.BASIC:
                continue
            if slot.count > self.MAX_COPIES:
                report.issues.append(ValidationIssue(
                    code="COPY_LIMIT",
                    message=f"{card.name}: {slot.count} copies exceeds limit of {self.MAX_COPIES}.",
                    severity="error",
                    card_name=card.name,
                ))

    def _check_has_basic(self, deck: Deck, report: ValidationReport) -> None:
        basics = deck.basic_pokemon_slots()
        if not basics:
            report.issues.append(ValidationIssue(
                code="NO_BASIC_POKEMON",
                message="Deck contains no Basic Pokémon — cannot start a game.",
                severity="error",
            ))

    def _check_ace_spec(self, deck: Deck, report: ValidationReport) -> None:
        ace_count = sum(
            s.count for s in deck.slots
            if s.card.rule_box == RuleBox.ACE_SPEC
        )
        if ace_count > self.MAX_ACE_SPEC:
            report.issues.append(ValidationIssue(
                code="ACE_SPEC_LIMIT",
                message=f"Deck has {ace_count} ACE SPEC cards, limit is {self.MAX_ACE_SPEC}.",
                severity="error",
            ))

    def _check_evolution_legality(self, deck: Deck, report: ValidationReport) -> None:
        """Warn if an evolution Pokémon has no matching pre-evolution in the deck."""
        names_in_deck: set[str] = {s.card.name for s in deck.slots}
        for slot in deck.pokemon_slots():
            card = slot.card
            if not isinstance(card, PokemonCard):
                continue
            if card.stage in (Stage.STAGE_1, Stage.STAGE_2) and card.previous_stage:
                if card.previous_stage not in names_in_deck:
                    report.issues.append(ValidationIssue(
                        code="MISSING_PRE_EVOLUTION",
                        message=(
                            f"{card.name} (Stage {card.stage.value}) requires "
                            f"'{card.previous_stage}' which is not in the deck."
                        ),
                        severity="warning",
                        card_name=card.name,
                    ))

    def _check_energy_sanity(self, deck: Deck, report: ValidationReport) -> None:
        """Warn if deck has Pokémon with attack costs but zero matching energy."""
        from src.cards.models import PokemonCard
        needed_types: set[str] = set()
        for slot in deck.pokemon_slots():
            card = slot.card
            if not isinstance(card, PokemonCard):
                continue
            for attack in card.attacks:
                for token in attack.cost.tokens:
                    if token not in ("{C}", "{A}"):
                        needed_types.add(token)

        available_types: set[str] = set()
        for slot in deck.energy_slots():
            card = slot.card
            if not isinstance(card, EnergyCard):
                continue
            for pt in card.provides:
                available_types.add(pt.value)

        for t in needed_types:
            if t not in available_types:
                report.issues.append(ValidationIssue(
                    code="MISSING_ENERGY_TYPE",
                    message=f"Attacks require {t} energy but no card provides it.",
                    severity="warning",
                ))

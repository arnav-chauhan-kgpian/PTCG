"""
SimulatorValidator — high-level facade returning a full validation report.

Combines:
  - random-play correctness (P2.2)
  - per-state validation (StateValidator)
  - card coverage (RuleCoverageReport)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.evaluation.simulator_validation import (
    SimulatorValidationReport,
    validate_simulator,
)
from src.validation.rule_coverage import RuleCoverageReport, measure_rule_coverage

if TYPE_CHECKING:
    from src.cards.repository import CardRepository


@dataclass
class FullValidationReport:
    sim_validation: SimulatorValidationReport
    rule_coverage: RuleCoverageReport
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "sim_validation": {
                **self.sim_validation.to_dict(),
                "correctness_rate": round(self.sim_validation.correctness_rate, 4),
            },
            "rule_coverage": self.rule_coverage.to_dict(),
            "notes": list(self.notes),
        }

    def to_markdown(self) -> str:
        sv = self.sim_validation
        rc = self.rule_coverage
        return "\n".join([
            "# Simulator Validation Report",
            "",
            "## Random-play correctness",
            f"- Games: **{sv.games_played}** (terminal {sv.games_terminal})",
            f"- Total actions sampled: **{sv.total_actions}**",
            f"- Illegal-action attempts: {sv.illegal_actions_attempted}",
            f"- State-mutation violations: {sv.state_mutation_violations}",
            f"- Prize-accounting errors: {sv.prize_accounting_errors}",
            f"- Bench overflow / duplicate zone: "
            f"{sv.bench_overflow_observed} / {sv.duplicate_zone_observed}",
            f"- Knockouts observed: {sv.knockouts_total}",
            f"- Correctness rate: **{sv.correctness_rate:.4f}**",
            "",
            "## Rule / card coverage",
            f"- Trainers fully supported: **{rc.trainers_supported}/{rc.trainers_total}** "
            f"({rc.trainer_coverage:.1%})",
            f"- Attacks fully supported: **{rc.attacks_supported}/{rc.attacks_total}** "
            f"({rc.attack_coverage:.1%})",
            f"- Abilities supported: **{rc.abilities_supported}/{rc.abilities_total}** "
            f"({rc.ability_coverage:.1%})",
            f"- Named trainer handlers: {rc.named_trainer_handlers}",
            f"- Named ability handlers: {rc.named_ability_handlers}",
        ])


class SimulatorValidator:
    """One-stop validator for self-tests and CI."""

    def __init__(self, repository: CardRepository) -> None:
        self.repository = repository

    def run(
        self,
        *,
        n_games: int = 10,
        max_actions_per_game: int = 200,
        seed: int = 0,
    ) -> FullValidationReport:
        sim_report = validate_simulator(
            self.repository,
            n_games=n_games,
            max_actions_per_game=max_actions_per_game,
            seed=seed,
        )
        coverage = measure_rule_coverage(self.repository)
        return FullValidationReport(
            sim_validation=sim_report, rule_coverage=coverage,
        )

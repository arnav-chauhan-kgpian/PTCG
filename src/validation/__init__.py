"""
Simulator validation facade.

Thin re-exports of the P2 validation tooling under the explicit
``src.validation`` namespace required by the final-phase contract.
"""

from src.evaluation.simulator_validation import (
    SimulatorValidationReport,
    validate_simulator,
)
from src.validation.replay_validator import ReplayValidator
from src.validation.rule_coverage import RuleCoverageReport, measure_rule_coverage
from src.validation.simulator_validator import SimulatorValidator
from src.validation.state_validator import StateValidator

__all__ = [
    "SimulatorValidator",
    "StateValidator",
    "ReplayValidator",
    "RuleCoverageReport",
    "SimulatorValidationReport",
    "measure_rule_coverage",
    "validate_simulator",
]

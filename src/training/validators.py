"""
Compatibility validators for the training pipeline.

Validate before loading: checkpoints, replay buffers, network configs.
All checks return structured reports so callers can decide whether to
abort, warn, or auto-migrate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.mcts.checkpoints import CheckpointMetadata
    from src.mcts.network import NetworkConfig
    from src.mcts.replay_buffer import ReplayBuffer
    from src.training.config import PipelineConfig


@dataclass(frozen=True)
class CompatIssue:
    code: str
    message: str
    severity: str = "error"


@dataclass
class CompatReport:
    issues: list[CompatIssue] = field(default_factory=list)

    def error(self, code: str, message: str) -> None:
        self.issues.append(CompatIssue(code=code, message=message, severity="error"))

    def warn(self, code: str, message: str) -> None:
        self.issues.append(CompatIssue(code=code, message=message, severity="warning"))

    @property
    def errors(self) -> list[CompatIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[CompatIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def is_compatible(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        return (
            f"{'Compatible' if self.is_compatible else 'Incompatible'}: "
            f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)"
        )


# -------------------------------------------------------------------------
# Validators
# -------------------------------------------------------------------------

def validate_network_config_match(
    expected: NetworkConfig, observed: NetworkConfig
) -> CompatReport:
    report = CompatReport()
    keys_must_match = ("input_size", "action_size")
    keys_soft_match = ("hidden_size", "num_hidden_layers", "activation", "use_layernorm")

    for k in keys_must_match:
        if getattr(expected, k) != getattr(observed, k):
            report.error(
                f"MISMATCH_{k.upper()}",
                f"{k}: expected {getattr(expected, k)} got {getattr(observed, k)}",
            )
    for k in keys_soft_match:
        if getattr(expected, k) != getattr(observed, k):
            report.warn(
                f"DIFFERENT_{k.upper()}",
                f"{k}: expected {getattr(expected, k)} got {getattr(observed, k)}",
            )
    return report


def validate_checkpoint(
    metadata: CheckpointMetadata, expected: NetworkConfig
) -> CompatReport:
    """Inspect a CheckpointMetadata against expected network shape."""
    report = CompatReport()
    if not metadata.network_config:
        report.warn("NO_CONFIG_METADATA", "checkpoint missing network_config")
        return report

    expected_dict = dict(expected.__dict__)
    observed_dict = dict(metadata.network_config)
    for k in ("input_size", "action_size"):
        if k in expected_dict and k in observed_dict and expected_dict[k] != observed_dict[k]:
            report.error(
                f"MISMATCH_{k.upper()}",
                f"{k}: expected {expected_dict[k]} got {observed_dict[k]}",
            )
    return report


def validate_replay_buffer(
    buffer: ReplayBuffer, expected_feature_size: int, expected_policy_size: int
) -> CompatReport:
    report = CompatReport()
    if len(buffer) == 0:
        report.warn("EMPTY_BUFFER", "replay buffer is empty")
        return report
    sample = buffer[0]
    if len(sample.state_features) != expected_feature_size:
        report.error(
            "FEATURE_SIZE_MISMATCH",
            f"feature size: expected {expected_feature_size} got "
            f"{len(sample.state_features)}",
        )
    if len(sample.policy_target) != expected_policy_size:
        report.error(
            "POLICY_SIZE_MISMATCH",
            f"policy size: expected {expected_policy_size} got "
            f"{len(sample.policy_target)}",
        )
    return report


def validate_pipeline_config(config: PipelineConfig) -> CompatReport:
    """Cross-field consistency checks on a PipelineConfig."""
    report = CompatReport()
    if config.network.input_size <= 0:
        report.error("BAD_INPUT_SIZE", f"input_size={config.network.input_size}")
    if config.network.action_size <= 0:
        report.error("BAD_ACTION_SIZE", f"action_size={config.network.action_size}")
    if config.rounds <= 0:
        report.error("BAD_ROUNDS", f"rounds={config.rounds}")
    if config.selfplay.games_per_round <= 0:
        report.error("BAD_GAMES_PER_ROUND", f"games_per_round={config.selfplay.games_per_round}")
    if config.arena.n_games <= 0:
        report.warn("ZERO_ARENA_GAMES", "arena.n_games is 0 — promotion will always fail")
    if config.promotion.win_rate_threshold > 1.0 or config.promotion.win_rate_threshold < 0.0:
        report.error(
            "BAD_THRESHOLD",
            f"promotion.win_rate_threshold={config.promotion.win_rate_threshold}",
        )
    return report

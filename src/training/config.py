"""
Training pipeline configuration — orchestrates the full AlphaZero loop.

Wraps the existing ``mcts.MCTSConfig``, ``mcts.NetworkConfig`` and
``mcts.TrainingConfig`` plus pipeline-specific knobs (self-play counts,
arena settings, promotion threshold, logging).  Nothing here duplicates
the inner configs — it composes them.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from src.mcts.config import MCTSConfig
from src.mcts.network import NetworkConfig
from src.mcts.training_config import TrainingConfig as InnerTrainingConfig


@dataclass(frozen=True)
class ArenaConfig:
    """Match-play settings for evaluating a candidate vs. the current best."""
    n_games: int = 20
    max_moves_per_game: int = 100
    mcts_iterations: int = 50
    seed: int | None = None


@dataclass(frozen=True)
class PromotionConfig:
    """Rules for accepting a candidate as the new best model."""
    win_rate_threshold: float = 0.55
    min_games: int = 10
    require_strict_improvement: bool = False


@dataclass(frozen=True)
class SelfPlayConfig:
    """How many games per training round."""
    games_per_round: int = 20
    max_moves_per_game: int = 100
    mcts_iterations: int = 60
    temperature_early_moves: int = 15
    temperature_high: float = 1.0
    temperature_low: float = 0.0
    seed: int | None = None


@dataclass(frozen=True)
class LoggingConfig:
    """Logging sinks and verbosity."""
    log_dir: str = "logs"
    csv: bool = True
    jsonl: bool = True
    tensorboard: bool = False
    console: bool = True
    log_every: int = 10


@dataclass(frozen=True)
class EarlyStoppingConfig:
    patience: int = 10
    min_improvement: float = 1e-4
    max_wall_clock_s: float | None = None
    max_epochs: int | None = None
    max_training_steps: int | None = None


@dataclass(frozen=True)
class PipelineConfig:
    """Top-level configuration assembled by callers."""

    # Sub-configs
    network: NetworkConfig = field(default_factory=NetworkConfig)
    mcts: MCTSConfig = field(default_factory=MCTSConfig)
    trainer: InnerTrainingConfig = field(default_factory=InnerTrainingConfig)
    selfplay: SelfPlayConfig = field(default_factory=SelfPlayConfig)
    arena: ArenaConfig = field(default_factory=ArenaConfig)
    promotion: PromotionConfig = field(default_factory=PromotionConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)
    early_stopping: EarlyStoppingConfig = field(default_factory=EarlyStoppingConfig)

    # Pipeline-level
    rounds: int = 100                  # outer loop iterations
    replay_capacity: int = 100_000
    checkpoint_dir: str = "checkpoints"
    experiment_dir: str = "experiments"
    experiment_name: str = "default"
    seed: int | None = None
    resume_from: str | None = None  # checkpoint name to resume from

    def with_overrides(self, **kwargs) -> PipelineConfig:
        return replace(self, **kwargs)

    def to_dict(self) -> dict:
        return {
            "network": dict(self.network.__dict__),
            "mcts": dict(self.mcts.__dict__),
            "trainer": dict(self.trainer.__dict__),
            "selfplay": dict(self.selfplay.__dict__),
            "arena": dict(self.arena.__dict__),
            "promotion": dict(self.promotion.__dict__),
            "logging": dict(self.logging.__dict__),
            "early_stopping": dict(self.early_stopping.__dict__),
            "rounds": self.rounds,
            "replay_capacity": self.replay_capacity,
            "checkpoint_dir": self.checkpoint_dir,
            "experiment_dir": self.experiment_dir,
            "experiment_name": self.experiment_name,
            "seed": self.seed,
            "resume_from": self.resume_from,
        }

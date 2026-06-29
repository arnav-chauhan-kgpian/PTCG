"""
Phase 10 — AlphaZero training pipeline.

Public API::

    from src.training import (
        TrainingPipeline, PipelineConfig, Trainer, Arena, PromotionPolicy,
        TrainingMetrics, MetricLogger, ExperimentManager,
        AlphaZeroLoss, LossWeights,
        Curriculum, EarlyStopping, RoundScheduler,
        Callback, CallbackList, LoggingCallback, HistoryCallback,
        PipelineCheckpoint, PipelineCheckpointStore,
        validate_pipeline_config, validate_checkpoint, validate_replay_buffer,
    )
"""

from src.training import exports
from src.training.arena import Arena, ArenaGame, ArenaResult
from src.training.callbacks import (
    BaseCallback,
    Callback,
    CallbackList,
    HistoryCallback,
    LoggingCallback,
)
from src.training.checkpointing import PipelineCheckpoint, PipelineCheckpointStore
from src.training.config import (
    ArenaConfig,
    EarlyStoppingConfig,
    LoggingConfig,
    PipelineConfig,
    PromotionConfig,
    SelfPlayConfig,
)
from src.training.curriculum import Curriculum, CurriculumStage, default_curriculum
from src.training.early_stopping import EarlyStopping
from src.training.evaluator import EvaluationResult, evaluate
from src.training.experiments import ExperimentManager, ExperimentManifest
from src.training.logging import (
    ConsoleSink,
    CSVSink,
    JSONLSink,
    MetricLogger,
    TensorBoardSink,
)
from src.training.losses import (
    AlphaZeroLoss,
    LossOutput,
    LossWeights,
    entropy_bonus,
    has_torch,
    l2_penalty,
    policy_cross_entropy,
    value_bce,
    value_mse,
)
from src.training.metrics import RollingMean, TrainingMetrics
from src.training.monitor import PerfMonitor, Stopwatch
from src.training.pipeline import PipelineResult, TrainingPipeline
from src.training.promotion import PromotionDecision, PromotionPolicy
from src.training.scheduler import RoundScheduler
from src.training.trainer import Trainer, TrainerStepResult
from src.training.validators import (
    CompatIssue,
    CompatReport,
    validate_checkpoint,
    validate_network_config_match,
    validate_pipeline_config,
    validate_replay_buffer,
)

__all__ = [
    # Pipeline
    "TrainingPipeline", "PipelineResult", "PipelineConfig",
    # Sub-configs
    "ArenaConfig", "EarlyStoppingConfig", "LoggingConfig",
    "PromotionConfig", "SelfPlayConfig",
    # Trainer
    "Trainer", "TrainerStepResult",
    # Losses
    "AlphaZeroLoss", "LossOutput", "LossWeights",
    "entropy_bonus", "l2_penalty",
    "policy_cross_entropy", "value_bce", "value_mse",
    "has_torch",
    # Arena & promotion
    "Arena", "ArenaResult", "ArenaGame",
    "PromotionPolicy", "PromotionDecision",
    # Curriculum
    "Curriculum", "CurriculumStage", "default_curriculum",
    # Scheduling
    "RoundScheduler", "EarlyStopping",
    # Metrics & logging
    "TrainingMetrics", "RollingMean",
    "MetricLogger", "CSVSink", "JSONLSink", "ConsoleSink", "TensorBoardSink",
    "PerfMonitor", "Stopwatch",
    # Callbacks
    "BaseCallback", "Callback", "CallbackList",
    "HistoryCallback", "LoggingCallback",
    # Experiments
    "ExperimentManager", "ExperimentManifest",
    # Checkpointing
    "PipelineCheckpoint", "PipelineCheckpointStore",
    # Offline eval
    "EvaluationResult", "evaluate",
    # Validators
    "CompatIssue", "CompatReport",
    "validate_checkpoint", "validate_network_config_match",
    "validate_pipeline_config", "validate_replay_buffer",
    # Exports
    "exports",
]

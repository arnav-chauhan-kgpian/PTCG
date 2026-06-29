"""
Monte Carlo Tree Search engine — Phase 8.

Public API::

    from src.mcts import (
        MCTSSearch, SearchResult, MCTSConfig,
        MCTSNode, MCTSAction, MCTSTree,
        HeuristicEvaluator, UCTSelection, PUCTSelection,
        TranspositionTable, NullSimulator,
        search, exports, validators,
    )
"""

# Configuration
# Exports / validators
from src.mcts import exports, validators

# Backpropagation
from src.mcts.backpropagation import backpropagate, backpropagate_terminal
from src.mcts.checkpoints import CheckpointManager, CheckpointMetadata
from src.mcts.config import (
    ExpansionMode,
    MCTSConfig,
    RolloutPolicy,
    SelectionStrategy,
)

# Determinization
from src.mcts.determinization import (
    DeterminizationSampler,
    IdentityDeterminizer,
    RandomDeterminizer,
)

# Evaluation
from src.mcts.evaluator import (
    EvaluatorProtocol,
    HeuristicEvaluator,
    NeuralEvaluatorPlaceholder,
    UniformEvaluator,
    make_evaluator,
)

# Expansion
from src.mcts.expansion import (
    add_dirichlet_noise,
    expand_all,
    expand_one,
    initialise_node,
)

# ─── Phase 9: Neural inference & self-play ────────────────────────────────
from src.mcts.features import (
    FeatureEncoderProtocol,
    GameStateFeatureEncoder,
    IdentityFeatureEncoder,
    make_feature_encoder,
)
from src.mcts.inference_cache import InferenceCache, InferenceCacheStats
from src.mcts.network import NetworkConfig, NetworkWrapper, has_torch, make_network
from src.mcts.neural_evaluator import NeuralEvaluator
from src.mcts.neural_policy import NeuralPriorPolicy

# Node / tree
from src.mcts.node import MCTSAction, MCTSNode, reset_node_counter

# Priors
from src.mcts.policies import (
    HeuristicPriorPolicy,
    NeuralPriorPlaceholder,
    PriorPolicy,
    UniformPriorPolicy,
    make_prior_policy,
)
from src.mcts.replay_buffer import ReplayBuffer, ReplayBufferStats

# Rollouts
from src.mcts.rollout import (
    DepthLimitedRollout,
    GreedyRollout,
    HeuristicRollout,
    RandomRollout,
    RolloutBase,
    make_rollout,
)
from src.mcts.scheduler import SearchScheduler

# Search engine
from src.mcts.search import MCTSSearch, SearchResult, search

# Selection
from src.mcts.selection import (
    PUCTSelection,
    UCTSelection,
    make_selection_strategy,
    puct_score,
    select_leaf,
    uct_score,
)
from src.mcts.selfplay import SelfPlayEngine, SelfPlayGame, SelfPlayMove

# Simulation interface
from src.mcts.simulation import NullSimulator, SimulatorProtocol

# Statistics / scheduler
from src.mcts.statistics import SearchStatistics, timer
from src.mcts.training_config import (
    TrainingConfig,
    build_optimizer,
    build_scheduler,
)
from src.mcts.training_targets import (
    TemperatureSchedule,
    TrainingSample,
    outcome_to_value_target,
    policy_to_vector,
    visit_counts_to_policy,
)

# Transposition table
from src.mcts.transposition import TranspositionStats, TranspositionTable
from src.mcts.tree import MCTSTree
from src.mcts.validators import (
    MCTSIssue,
    MCTSValidationReport,
    validate_config,
    validate_node,
    validate_result,
    validate_tree,
)

__all__ = [
    # Config
    "MCTSConfig", "SelectionStrategy", "RolloutPolicy", "ExpansionMode",
    # Node / tree
    "MCTSAction", "MCTSNode", "MCTSTree", "reset_node_counter",
    # Selection
    "UCTSelection", "PUCTSelection", "uct_score", "puct_score",
    "select_leaf", "make_selection_strategy",
    # Expansion
    "initialise_node", "expand_one", "expand_all", "add_dirichlet_noise",
    # Evaluation
    "EvaluatorProtocol", "UniformEvaluator", "HeuristicEvaluator",
    "NeuralEvaluatorPlaceholder", "make_evaluator",
    # Rollouts
    "RolloutBase", "HeuristicRollout", "RandomRollout",
    "GreedyRollout", "DepthLimitedRollout", "make_rollout",
    # Backprop
    "backpropagate", "backpropagate_terminal",
    # Priors
    "PriorPolicy", "UniformPriorPolicy", "HeuristicPriorPolicy",
    "NeuralPriorPlaceholder", "make_prior_policy",
    # Determinization
    "DeterminizationSampler", "RandomDeterminizer", "IdentityDeterminizer",
    # TT
    "TranspositionTable", "TranspositionStats",
    # Stats
    "SearchStatistics", "timer", "SearchScheduler",
    # Simulator
    "SimulatorProtocol", "NullSimulator",
    # Search
    "MCTSSearch", "SearchResult", "search",
    # Exports / validators
    "exports", "validators",
    "MCTSValidationReport", "MCTSIssue",
    "validate_config", "validate_node", "validate_tree", "validate_result",
    # Phase 9 — neural
    "FeatureEncoderProtocol", "GameStateFeatureEncoder",
    "IdentityFeatureEncoder", "make_feature_encoder",
    "InferenceCache", "InferenceCacheStats",
    "NetworkConfig", "NetworkWrapper", "make_network", "has_torch",
    "NeuralEvaluator", "NeuralPriorPolicy",
    "TemperatureSchedule", "TrainingSample",
    "visit_counts_to_policy", "policy_to_vector", "outcome_to_value_target",
    "ReplayBuffer", "ReplayBufferStats",
    "SelfPlayEngine", "SelfPlayGame", "SelfPlayMove",
    "CheckpointManager", "CheckpointMetadata",
    "TrainingConfig", "build_optimizer", "build_scheduler",
]

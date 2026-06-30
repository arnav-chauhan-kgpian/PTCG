"""
Top-level AlphaZero training orchestrator.

``TrainingPipeline.run()`` executes the full loop::

    for round in range(rounds):
        self-play games  → samples → ReplayBuffer
        Trainer steps    → optimise network
        Arena evaluation → win rate vs. current best
        Promotion gate   → swap best_network if candidate strong
        checkpoint, log, decide whether to early-stop

All components are injected; the orchestrator owns no business logic.
Restartable via ``PipelineCheckpoint`` snapshots.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.mcts.checkpoints import CheckpointManager, CheckpointMetadata
from src.mcts.config import MCTSConfig
from src.mcts.features import GameStateFeatureEncoder
from src.mcts.inference_cache import InferenceCache
from src.mcts.network import NetworkWrapper
from src.mcts.neural_evaluator import NeuralEvaluator
from src.mcts.neural_policy import NeuralPriorPolicy
from src.mcts.replay_buffer import ReplayBuffer
from src.mcts.search import MCTSSearch
from src.mcts.selfplay import SelfPlayEngine
from src.mcts.training_targets import TemperatureSchedule
from src.training.arena import Arena
from src.training.callbacks import CallbackList
from src.training.checkpointing import PipelineCheckpoint, PipelineCheckpointStore
from src.training.config import PipelineConfig
from src.training.curriculum import Curriculum, default_curriculum
from src.training.early_stopping import EarlyStopping
from src.training.experiments import ExperimentManager
from src.training.metrics import TrainingMetrics
from src.training.promotion import PromotionDecision, PromotionPolicy
from src.training.scheduler import RoundScheduler
from src.training.trainer import Trainer
from src.training.validators import validate_pipeline_config

if TYPE_CHECKING:
    from src.mcts.node import MCTSAction
    from src.mcts.simulation import SimulatorProtocol
    from src.training.callbacks import Callback


# -------------------------------------------------------------------------
# Container
# -------------------------------------------------------------------------

@dataclass
class PipelineResult:
    rounds_completed: int = 0
    best_checkpoint: str | None = None
    promotions: int = 0
    final_metrics: dict = field(default_factory=dict)
    experiment_summary: dict = field(default_factory=dict)
    elapsed_s: float = 0.0


# -------------------------------------------------------------------------
# Orchestrator
# -------------------------------------------------------------------------

class TrainingPipeline:
    """
    Wire together self-play, training, arena, promotion, checkpointing.

    All components are injected; you can override any of:
        simulator, action_map, encoder, curriculum, callbacks
    """

    def __init__(
        self,
        simulator: SimulatorProtocol,
        action_map: list[MCTSAction],
        config: PipelineConfig | None = None,
        curriculum: Curriculum | None = None,
        callbacks: list[Callback] | None = None,
    ) -> None:
        self.config = config or PipelineConfig()
        report = validate_pipeline_config(self.config)
        if not report.is_compatible:
            raise ValueError(f"PipelineConfig invalid: {report.summary()}")

        self.simulator = simulator
        self.action_map = action_map
        self.encoder = GameStateFeatureEncoder()
        self.curriculum = curriculum or default_curriculum()
        self.callbacks = CallbackList(callbacks)

        self._rng = random.Random(self.config.seed)

        # Experiment management
        self.experiment = ExperimentManager(
            root=self.config.experiment_dir,
            name=self.config.experiment_name,
            config_snapshot=self.config.to_dict(),
            seed=self.config.seed,
        )

        # Networks
        self.best_network = NetworkWrapper(self.config.network)
        self.candidate_network = NetworkWrapper(self.config.network)
        self._sync_candidate_from_best()

        # Replay buffer & trainer
        self.replay = ReplayBuffer(
            capacity=self.config.replay_capacity, seed=self.config.seed,
        )
        self.trainer = Trainer(
            self.candidate_network, self.replay, self.config.trainer,
        )

        # Checkpoint managers
        self.checkpoint_mgr = CheckpointManager(
            self.experiment.checkpoints_dir, keep_last=5,
        )
        self.pipeline_ckpt_store = PipelineCheckpointStore(
            self.experiment.pipeline_checkpoints_dir,
        )

        # Round scheduler + early stopping
        self.round_scheduler = RoundScheduler(
            max_rounds=self.config.rounds,
            max_wall_clock_s=self.config.early_stopping.max_wall_clock_s,
        )
        self.early_stopping = EarlyStopping.from_config(self.config.early_stopping)

        # Promotion / arena
        self.promotion_policy = PromotionPolicy(self.config.promotion)
        self.arena = Arena(
            simulator=simulator,
            encoder=self.encoder,
            action_map=action_map,
            mcts_config=MCTSConfig(
                iterations=self.config.arena.mcts_iterations,
                time_budget_s=30.0,
            ),
            seed=self.config.arena.seed,
        )

        # Metrics
        self.metrics = TrainingMetrics()

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #

    def run(self) -> PipelineResult:
        t0 = time.perf_counter()
        result = PipelineResult()

        try:
            self.callbacks.on_training_start(self._base_context())

            if self.config.resume_from:
                self._resume()

            while self.round_scheduler.should_continue():
                self._run_round()
                result.rounds_completed += 1
                self.round_scheduler.tick()

            self.experiment.set_status("completed")
        except Exception as exc:
            self.experiment.set_status("failed", notes=str(exc))
            self.callbacks.on_exception({"error": str(exc)})
            raise
        finally:
            result.elapsed_s = time.perf_counter() - t0
            result.best_checkpoint = self.experiment.manifest.best_checkpoint
            result.promotions = self.metrics.promotions
            result.final_metrics = self.metrics.snapshot()
            result.experiment_summary = self.experiment.summary()
            self.experiment.set_training_duration(result.elapsed_s)
            self.callbacks.on_training_end(self._base_context() | result.final_metrics)

        return result

    # ------------------------------------------------------------------ #
    # Round
    # ------------------------------------------------------------------ #

    def _run_round(self) -> None:
        round_idx = self.metrics.rounds
        self.callbacks.on_round_start({"round": round_idx})

        # Build a starting state for this round
        initial_state = self.curriculum.build_state(round_idx)

        # Fail loudly rather than silently if the curriculum produced a state
        # the simulator can't actually play. Symptom of the old silent failure:
        # every round elapsed_s≈0, replay buffer never fills, trainer no-ops,
        # no promotions. The signal we key on is "the curriculum gave us a
        # state that has no legal actions" — that's strictly broken regardless
        # of whether the simulator is a real one or a test stub.
        _legal = self.simulator.legal_actions(initial_state)
        if not _legal:
            raise RuntimeError(
                f"Curriculum produced an unplayable initial state at round "
                f"{round_idx} (status={initial_state.game_status.name}, "
                f"legal_actions=0). This typically means the curriculum is "
                f"the default empty-state placeholder. Pass a real curriculum "
                f"to TrainingPipeline that builds states via "
                f"simulator.start_game(deck_a, deck_b). See "
                f"src.training.curriculum.make_curriculum for a ready-made "
                f"factory that takes a simulator and two decks."
            )

        # ---- Self-play ----
        self._run_selfplay(initial_state, round_idx)

        # ---- Training ----
        self._run_training(round_idx)

        # ---- Evaluation + promotion ----
        decision = self._run_arena_and_maybe_promote(initial_state, round_idx)

        # ---- Checkpointing ----
        self._save_checkpoint(round_idx, decision)

        # ---- Early stopping check ----
        trigger = self.early_stopping.update(
            metric=self.metrics.last_total_loss,
            epoch=self.trainer.epoch_count,
            step=self.trainer.step_count,
        )
        if trigger:
            self.round_scheduler.trigger_early_stop(
                self.early_stopping.trigger_reason
            )

        self.metrics.record_round()
        self.experiment.record_metrics(self.metrics.snapshot())
        self.callbacks.on_round_end({"round": round_idx,
                                      "metrics": self.metrics.snapshot()})

    # ------------------------------------------------------------------ #
    # Round phases
    # ------------------------------------------------------------------ #

    def _run_selfplay(self, initial_state, round_idx: int) -> None:
        sp_cfg = self.config.selfplay
        # Build an MCTS search backed by the *candidate* network
        cache = InferenceCache()
        evaluator = NeuralEvaluator(
            self.candidate_network, self.encoder, self.action_map, cache,
        )
        policy = NeuralPriorPolicy(
            self.candidate_network, self.encoder, self.action_map, cache,
        )
        search = MCTSSearch(
            self.simulator,
            config=MCTSConfig(
                iterations=sp_cfg.mcts_iterations, time_budget_s=30.0,
                seed=sp_cfg.seed,
            ),
            evaluator=evaluator, prior_policy=policy,
        )
        engine = SelfPlayEngine(
            self.simulator, search, self.encoder,
            temperature_schedule=TemperatureSchedule(
                early_moves=sp_cfg.temperature_early_moves,
                temperature_high=sp_cfg.temperature_high,
                temperature_low=sp_cfg.temperature_low,
            ),
            max_moves=sp_cfg.max_moves_per_game,
            seed=sp_cfg.seed,
        )

        for _ in range(sp_cfg.games_per_round):
            game = engine.play_game(initial_state)
            samples = game.to_training_samples(self.action_map)
            self.replay.extend(samples)
            self.metrics.record_selfplay_game(
                moves=game.move_count,
                cache_hit_rate=cache.stats.hit_rate,
            )
            self.metrics.samples_seen += len(samples)
            self.callbacks.on_selfplay_end({
                "round": round_idx,
                "game_moves": game.move_count,
                "winner": game.winner,
                "samples_added": len(samples),
                "replay_size": len(self.replay),
            })

        self.metrics.replay_size = len(self.replay)

    def _run_training(self, round_idx: int) -> None:
        for _ in range(self.config.trainer.epochs):
            for step_result in self.trainer.train_epoch():
                self.metrics.record_train_step(
                    policy_loss=step_result.loss.policy,
                    value_loss=step_result.loss.value,
                    total_loss=step_result.loss.total,
                    learning_rate=step_result.learning_rate,
                )
                self.callbacks.on_train_step({
                    "round": round_idx,
                    **step_result.to_dict(),
                })
            self.callbacks.on_epoch_end({
                "round": round_idx,
                "epoch": self.trainer.epoch_count,
            })

    def _run_arena_and_maybe_promote(
        self, initial_state, round_idx: int
    ) -> PromotionDecision:
        if self.config.arena.n_games <= 0:
            return PromotionDecision(
                promoted=False, candidate_win_rate=0.0, candidate_score=0.0,
                threshold=self.config.promotion.win_rate_threshold, n_games=0,
                reason="arena disabled",
            )

        arena_result = self.arena.play(
            candidate=self.candidate_network,
            champion=self.best_network,
            initial_state=initial_state,
            n_games=self.config.arena.n_games,
            max_moves=self.config.arena.max_moves_per_game,
        )
        self.metrics.record_arena(arena_result.candidate_win_rate)
        self.callbacks.on_evaluation({
            "round": round_idx, **arena_result.summary(),
        })

        decision = self.promotion_policy.decide(arena_result)
        if decision.promoted:
            self._sync_best_from_candidate()
            self.metrics.record_promotion(decision.to_dict() | {"round": round_idx})
            self.experiment.record_promotion(decision.to_dict() | {"round": round_idx})
            self.callbacks.on_promotion({"round": round_idx, **decision.to_dict()})
        return decision

    def _save_checkpoint(self, round_idx: int, decision: PromotionDecision) -> None:
        meta = CheckpointMetadata(
            training_step=self.trainer.step_count,
            timestamp=str(round_idx),
            notes=f"round={round_idx} promoted={decision.promoted}",
            network_config=dict(self.config.network.__dict__),
        )
        ckpt_path = self.checkpoint_mgr.save(self.candidate_network, meta)
        self.experiment.record_checkpoint(ckpt_path.stem, is_best=decision.promoted)
        self.callbacks.on_checkpoint({
            "round": round_idx,
            "path": str(ckpt_path),
            "promoted": decision.promoted,
        })

        # Pipeline-state checkpoint (for restart)
        pl_ckpt = PipelineCheckpoint(
            round_index=round_idx,
            training_step=self.trainer.step_count,
            best_checkpoint_name=self.experiment.manifest.best_checkpoint,
            candidate_checkpoint_name=ckpt_path.stem,
            metrics_snapshot=self.metrics.snapshot(),
            config_snapshot=self.config.to_dict(),
        )
        self.pipeline_ckpt_store.save(pl_ckpt)

    # ------------------------------------------------------------------ #
    # Resume
    # ------------------------------------------------------------------ #

    def _resume(self) -> None:
        pl_ckpt = self.pipeline_ckpt_store.load_latest()
        if pl_ckpt is None:
            return
        if pl_ckpt.best_checkpoint_name:
            try:
                wrapper, _ = self.checkpoint_mgr.load(pl_ckpt.best_checkpoint_name)
                self.best_network = wrapper
            except FileNotFoundError:
                pass
        if pl_ckpt.candidate_checkpoint_name:
            try:
                wrapper, _ = self.checkpoint_mgr.load(pl_ckpt.candidate_checkpoint_name)
                self.candidate_network = wrapper
                # Rebuild trainer with new network instance
                self.trainer = Trainer(
                    self.candidate_network, self.replay, self.config.trainer,
                )
                self.trainer.step_count = pl_ckpt.training_step
            except FileNotFoundError:
                pass

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #

    def _sync_candidate_from_best(self) -> None:
        self.candidate_network.load_state_dict(self.best_network.state_dict())

    def _sync_best_from_candidate(self) -> None:
        self.best_network.load_state_dict(self.candidate_network.state_dict())

    def _base_context(self) -> dict:
        return {
            "experiment": self.experiment.manifest.name,
            "config": self.config.to_dict(),
        }

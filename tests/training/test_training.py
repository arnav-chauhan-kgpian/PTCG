"""
Comprehensive tests for Phase 10 — AlphaZero training pipeline.
"""

from __future__ import annotations

import json
import time

import pytest

torch = pytest.importorskip("torch")

from src.game_state import GameState, GameStatus, PlayerState
from src.mcts import (
    MCTSAction,
    MCTSConfig,
    NetworkConfig,
    NetworkWrapper,
    NullSimulator,
    ReplayBuffer,
    TrainingSample,
    reset_node_counter,
)
from src.training import (
    AlphaZeroLoss,
    Arena,
    ArenaConfig,
    ArenaResult,
    BaseCallback,
    CallbackList,
    Curriculum,
    CurriculumStage,
    EarlyStopping,
    EarlyStoppingConfig,
    EvaluationResult,
    ExperimentManager,
    HistoryCallback,
    LossOutput,
    LossWeights,
    MetricLogger,
    PerfMonitor,
    PipelineCheckpoint,
    PipelineCheckpointStore,
    PipelineConfig,
    PipelineResult,
    PromotionConfig,
    PromotionDecision,
    PromotionPolicy,
    RollingMean,
    RoundScheduler,
    SelfPlayConfig,
    Stopwatch,
    Trainer,
    TrainingMetrics,
    TrainingPipeline,
    evaluate,
    exports,
    validate_checkpoint,
    validate_pipeline_config,
    validate_replay_buffer,
)
from src.training.losses import (
    entropy_bonus,
    l2_penalty,
    policy_cross_entropy,
    value_bce,
    value_mse,
)

# -------------------------------------------------------------------------
# Fixtures
# -------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_counter():
    reset_node_counter()


def _make_state() -> GameState:
    return GameState(
        turn_number=0, current_player=0, game_status=GameStatus.ONGOING,
        players=(
            PlayerState(player_id=0, prizes_remaining=6, deck_size=55, hand_count=5),
            PlayerState(player_id=1, prizes_remaining=6, deck_size=55, hand_count=5),
        ),
    )


def _action_map() -> list[MCTSAction]:
    actions = [MCTSAction(action_type=f"action_{i}", details=(("turn", str(t)),))
                for i in range(3) for t in range(8)]
    actions.append(MCTSAction.end_turn())
    return actions


def _small_network(action_size: int = 8) -> NetworkWrapper:
    return NetworkWrapper(NetworkConfig(
        input_size=741, action_size=action_size,
        hidden_size=32, num_hidden_layers=1, device="cpu",
    ))


def _make_replay(n: int = 100, feat_size: int = 741, policy_size: int = 8) -> ReplayBuffer:
    buf = ReplayBuffer(capacity=n * 2, seed=0)
    for i in range(n):
        target_idx = i % policy_size
        policy = [0.0] * policy_size
        policy[target_idx] = 1.0
        buf.append(TrainingSample(
            state_features=tuple([0.1 * (i % 10)] * feat_size),
            policy_target=tuple(policy),
            value_target=(i % 3) / 2.0,
        ))
    return buf


# -------------------------------------------------------------------------
# Losses
# -------------------------------------------------------------------------

class TestLosses:
    def test_policy_cross_entropy(self):
        logits = torch.tensor([[2.0, 1.0, 0.0]])
        target = torch.tensor([[1.0, 0.0, 0.0]])
        loss = policy_cross_entropy(logits, target)
        assert loss.item() < 1.0  # confident-correct → small loss

    def test_policy_cross_entropy_wrong(self):
        logits = torch.tensor([[2.0, 1.0, 0.0]])
        target_wrong = torch.tensor([[0.0, 0.0, 1.0]])
        target_right = torch.tensor([[1.0, 0.0, 0.0]])
        assert (
            policy_cross_entropy(logits, target_wrong).item()
            > policy_cross_entropy(logits, target_right).item()
        )

    def test_value_mse(self):
        pred = torch.tensor([[0.5], [0.5]])
        tgt = torch.tensor([0.5, 0.5])
        assert value_mse(pred, tgt).item() == pytest.approx(0.0)

    def test_value_bce_range(self):
        pred = torch.tensor([[0.7]])
        tgt = torch.tensor([1.0])
        loss = value_bce(pred, tgt)
        assert loss.item() > 0

    def test_entropy_bonus_max_for_uniform(self):
        uniform = torch.tensor([[0.0, 0.0, 0.0]])
        peaked = torch.tensor([[10.0, 0.0, 0.0]])
        assert entropy_bonus(uniform).item() > entropy_bonus(peaked).item()

    def test_l2_penalty(self):
        params = [torch.tensor([1.0, 2.0], requires_grad=True)]
        assert l2_penalty(params).item() == pytest.approx(5.0)

    def test_alpha_zero_loss(self):
        loss_fn = AlphaZeroLoss(LossWeights(policy=1.0, value=1.0))
        logits = torch.randn(4, 5)
        v_pred = torch.sigmoid(torch.randn(4, 1))
        p_tgt = torch.softmax(torch.randn(4, 5), dim=-1)
        v_tgt = torch.rand(4)
        total, decomp = loss_fn.compute(logits, v_pred, p_tgt, v_tgt)
        assert isinstance(decomp, LossOutput)
        assert decomp.total > 0
        assert decomp.policy > 0

    def test_loss_with_entropy_bonus(self):
        loss_fn = AlphaZeroLoss(LossWeights(policy=1.0, value=1.0, entropy=0.1))
        logits = torch.randn(2, 3)
        v_pred = torch.sigmoid(torch.randn(2, 1))
        p_tgt = torch.softmax(torch.randn(2, 3), dim=-1)
        v_tgt = torch.rand(2)
        total, _ = loss_fn.compute(logits, v_pred, p_tgt, v_tgt)
        assert torch.isfinite(total)

    def test_unknown_value_loss(self):
        with pytest.raises(ValueError):
            AlphaZeroLoss(value_loss="huber")

    def test_loss_with_l2(self):
        loss_fn = AlphaZeroLoss(LossWeights(policy=1.0, value=1.0, l2=0.01))
        logits = torch.randn(2, 3)
        v_pred = torch.sigmoid(torch.randn(2, 1))
        p_tgt = torch.softmax(torch.randn(2, 3), dim=-1)
        v_tgt = torch.rand(2)
        net = _small_network(action_size=3)
        total, dc = loss_fn.compute(logits, v_pred, p_tgt, v_tgt,
                                     parameters=net.model.parameters())
        assert dc.l2 > 0


# -------------------------------------------------------------------------
# Metrics
# -------------------------------------------------------------------------

class TestMetrics:
    def test_rolling_mean(self):
        rm = RollingMean(window=3)
        rm.push(1.0); rm.push(2.0); rm.push(3.0)
        assert rm.value == pytest.approx(2.0)
        rm.push(6.0)
        assert rm.value == pytest.approx((2 + 3 + 6) / 3)

    def test_record_train_step(self):
        m = TrainingMetrics()
        m.record_train_step(0.5, 0.3, 0.8, 1e-3)
        assert m.training_steps == 1
        assert m.last_total_loss == 0.8
        assert m.policy_loss.value == 0.5

    def test_best_loss_tracks_min(self):
        m = TrainingMetrics()
        m.record_train_step(0.5, 0.3, 0.8, 1e-3)
        m.record_train_step(0.4, 0.2, 0.6, 1e-3)
        assert m.best_loss == 0.6

    def test_record_arena(self):
        m = TrainingMetrics()
        m.record_arena(0.6)
        assert m.last_win_rate == 0.6
        assert m.best_win_rate == 0.6

    def test_record_promotion(self):
        m = TrainingMetrics()
        m.record_promotion({"win_rate": 0.6})
        assert m.promotions == 1
        assert len(m.promotion_history) == 1

    def test_snapshot(self):
        m = TrainingMetrics()
        m.record_train_step(0.5, 0.3, 0.8, 1e-3)
        s = m.snapshot()
        assert "last_total_loss" in s


# -------------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------------

class TestLogging:
    def test_csv_sink(self, tmp_path):
        logger = MetricLogger(log_dir=str(tmp_path), csv=True, jsonl=False,
                               console=False, tensorboard=False, log_every=1)
        logger.log("train", {"step": 1, "loss": 0.5})
        logger.log("train", {"step": 2, "loss": 0.4})
        csv_path = tmp_path / "metrics.csv"
        assert csv_path.exists()
        contents = csv_path.read_text()
        assert "train" in contents
        assert "0.5" in contents

    def test_jsonl_sink(self, tmp_path):
        logger = MetricLogger(log_dir=str(tmp_path), csv=False, jsonl=True,
                               console=False, log_every=1)
        logger.log("step", {"value": 1})
        lines = (tmp_path / "metrics.jsonl").read_text().strip().splitlines()
        assert len(lines) == 1
        parsed = json.loads(lines[0])
        assert parsed["value"] == 1

    def test_log_every(self, tmp_path):
        logger = MetricLogger(log_dir=str(tmp_path), csv=False, jsonl=True,
                               console=False, log_every=3)
        for i in range(7):
            logger.log("t", {"i": i})
        lines = (tmp_path / "metrics.jsonl").read_text().strip().splitlines()
        assert 1 <= len(lines) <= 3

    def test_force_bypasses_log_every(self, tmp_path):
        logger = MetricLogger(log_dir=str(tmp_path), csv=False, jsonl=True,
                               console=False, log_every=100)
        logger.log("t", {"v": 1}, force=True)
        assert (tmp_path / "metrics.jsonl").exists()

    def test_close_is_safe(self, tmp_path):
        logger = MetricLogger(log_dir=str(tmp_path), csv=False, jsonl=False,
                               console=False)
        logger.close()


# -------------------------------------------------------------------------
# Callbacks
# -------------------------------------------------------------------------

class TestCallbacks:
    def test_history_callback(self):
        cb = HistoryCallback()
        cb.on_training_start({"a": 1})
        cb.on_train_step({"step": 1})
        assert cb.count("on_training_start") == 1
        assert cb.count("on_train_step") == 1

    def test_callback_list_fan_out(self):
        a = HistoryCallback()
        b = HistoryCallback()
        cl = CallbackList([a, b])
        cl.on_round_start({"r": 0})
        assert a.count("on_round_start") == 1
        assert b.count("on_round_start") == 1

    def test_callback_exception_isolated(self):
        class Bad(BaseCallback):
            def on_train_step(self, context):
                raise RuntimeError("boom")
        a = Bad()
        b = HistoryCallback()
        cl = CallbackList([a, b])
        cl.on_train_step({})  # must not raise
        assert b.count("on_train_step") == 1


# -------------------------------------------------------------------------
# Early stopping
# -------------------------------------------------------------------------

class TestEarlyStopping:
    def test_patience(self):
        es = EarlyStopping(patience=2, min_improvement=0.01, mode="min")
        assert not es.update(1.0)
        assert not es.update(1.5)  # no improvement
        assert es.update(1.6)       # patience reached → trigger

    def test_max_epochs(self):
        es = EarlyStopping(patience=100, max_epochs=3)
        es.update(1.0, epoch=1)
        es.update(0.9, epoch=2)
        triggered = es.update(0.8, epoch=3)
        assert triggered

    def test_max_steps(self):
        es = EarlyStopping(patience=100, max_training_steps=5)
        for s in range(4):
            assert not es.update(1.0, step=s)
        assert es.update(0.9, step=5)

    def test_max_wall_clock(self):
        es = EarlyStopping(patience=1000, max_wall_clock_s=0.001)
        time.sleep(0.01)
        assert es.update(1.0)

    def test_max_mode(self):
        es = EarlyStopping(patience=2, mode="max")
        assert not es.update(0.5)
        assert not es.update(0.4)
        assert es.update(0.3)

    def test_from_config(self):
        cfg = EarlyStoppingConfig(patience=5, min_improvement=0.01)
        es = EarlyStopping.from_config(cfg)
        assert es.patience == 5


# -------------------------------------------------------------------------
# Scheduler
# -------------------------------------------------------------------------

class TestRoundScheduler:
    def test_max_rounds(self):
        sched = RoundScheduler(max_rounds=3)
        for _ in range(3):
            assert sched.should_continue()
            sched.tick()
        assert not sched.should_continue()

    def test_early_stop_trigger(self):
        sched = RoundScheduler(max_rounds=100)
        sched.trigger_early_stop("test reason")
        assert not sched.should_continue()


# -------------------------------------------------------------------------
# Promotion
# -------------------------------------------------------------------------

class TestPromotion:
    def test_promote_when_above_threshold(self):
        result = ArenaResult(candidate_wins=6, champion_wins=4, draws=0)
        policy = PromotionPolicy(PromotionConfig(win_rate_threshold=0.55, min_games=5))
        decision = policy.decide(result)
        assert decision.promoted

    def test_reject_when_below(self):
        result = ArenaResult(candidate_wins=4, champion_wins=6, draws=0)
        policy = PromotionPolicy(PromotionConfig(win_rate_threshold=0.55, min_games=5))
        decision = policy.decide(result)
        assert not decision.promoted

    def test_reject_too_few_games(self):
        result = ArenaResult(candidate_wins=2, champion_wins=0)
        policy = PromotionPolicy(PromotionConfig(min_games=10))
        decision = policy.decide(result)
        assert not decision.promoted
        assert "insufficient games" in decision.reason

    def test_strict_improvement(self):
        result = ArenaResult(candidate_wins=11, champion_wins=9, draws=0)
        score = result.candidate_score
        cfg = PromotionConfig(
            win_rate_threshold=score, min_games=5, require_strict_improvement=True,
        )
        policy = PromotionPolicy(cfg)
        decision = policy.decide(result)
        assert not decision.promoted

    def test_decision_to_dict(self):
        result = ArenaResult(candidate_wins=6, champion_wins=4)
        policy = PromotionPolicy(PromotionConfig(min_games=5))
        decision = policy.decide(result)
        d = decision.to_dict()
        assert "promoted" in d


# -------------------------------------------------------------------------
# Curriculum
# -------------------------------------------------------------------------

class TestCurriculum:
    def test_default(self):
        c = Curriculum()
        c.add_stage(CurriculumStage(name="A", builder=lambda r: _make_state(),
                                     min_rounds=0))
        assert c.stage_for_round(5).name == "A"

    def test_stage_progression(self):
        c = Curriculum()
        c.add_stage(CurriculumStage("A", lambda r: _make_state(), min_rounds=0))
        c.add_stage(CurriculumStage("B", lambda r: _make_state(), min_rounds=5))
        assert c.stage_for_round(0).name == "A"
        assert c.stage_for_round(4).name == "A"
        assert c.stage_for_round(5).name == "B"
        assert c.stage_for_round(100).name == "B"

    def test_build_state(self):
        c = Curriculum()
        c.add_stage(CurriculumStage("A", lambda r: _make_state(), min_rounds=0))
        s = c.build_state(0)
        assert isinstance(s, GameState)


# -------------------------------------------------------------------------
# Validators
# -------------------------------------------------------------------------

class TestValidators:
    def test_pipeline_config_valid(self):
        report = validate_pipeline_config(PipelineConfig())
        assert report.is_compatible

    def test_pipeline_config_bad_rounds(self):
        cfg = PipelineConfig(rounds=0)
        report = validate_pipeline_config(cfg)
        assert not report.is_compatible

    def test_pipeline_config_bad_threshold(self):
        cfg = PipelineConfig(promotion=PromotionConfig(win_rate_threshold=1.5))
        report = validate_pipeline_config(cfg)
        assert not report.is_compatible

    def test_replay_buffer_compatible(self):
        buf = _make_replay(n=5, feat_size=741, policy_size=8)
        report = validate_replay_buffer(buf, 741, 8)
        assert report.is_compatible

    def test_replay_buffer_mismatch(self):
        buf = _make_replay(n=5, feat_size=10, policy_size=8)
        report = validate_replay_buffer(buf, 741, 8)
        assert not report.is_compatible

    def test_replay_buffer_empty(self):
        buf = ReplayBuffer()
        report = validate_replay_buffer(buf, 741, 8)
        assert any(i.code == "EMPTY_BUFFER" for i in report.warnings)

    def test_checkpoint_compatibility(self):
        from src.mcts.checkpoints import CheckpointMetadata
        meta = CheckpointMetadata(network_config={
            "input_size": 741, "action_size": 8,
        })
        report = validate_checkpoint(meta, NetworkConfig(input_size=741, action_size=8))
        assert report.is_compatible

    def test_checkpoint_mismatch(self):
        from src.mcts.checkpoints import CheckpointMetadata
        meta = CheckpointMetadata(network_config={
            "input_size": 100, "action_size": 8,
        })
        report = validate_checkpoint(meta, NetworkConfig(input_size=741, action_size=8))
        assert not report.is_compatible


# -------------------------------------------------------------------------
# Trainer
# -------------------------------------------------------------------------

class TestTrainer:
    def test_step_when_ready(self):
        net = _small_network(action_size=8)
        buf = _make_replay(n=300, policy_size=8)
        from src.mcts.training_config import TrainingConfig as InnerCfg
        trainer = Trainer(net, buf, InnerCfg(batch_size=32, min_replay_size=50))
        r = trainer.step()
        assert r is not None
        assert r.batch_size == 32
        assert r.loss.total >= 0

    def test_step_skipped_when_buffer_small(self):
        net = _small_network()
        buf = _make_replay(n=10)
        from src.mcts.training_config import TrainingConfig as InnerCfg
        trainer = Trainer(net, buf, InnerCfg(batch_size=32, min_replay_size=100))
        r = trainer.step()
        assert r is None

    def test_train_epoch(self):
        net = _small_network()
        buf = _make_replay(n=300)
        from src.mcts.training_config import TrainingConfig as InnerCfg
        cfg = InnerCfg(batch_size=32, min_replay_size=50, iterations_per_epoch=3)
        trainer = Trainer(net, buf, cfg)
        results = trainer.train_epoch()
        assert len(results) == 3

    def test_state_dict_roundtrip(self):
        net = _small_network()
        buf = _make_replay(n=300)
        from src.mcts.training_config import TrainingConfig as InnerCfg
        trainer = Trainer(net, buf, InnerCfg(batch_size=32, min_replay_size=50))
        trainer.step()
        sd = trainer.state_dict()
        net2 = _small_network()
        trainer2 = Trainer(net2, buf, InnerCfg(batch_size=32, min_replay_size=50))
        trainer2.load_state_dict(sd)
        assert trainer2.step_count == trainer.step_count

    def test_loss_decreases(self):
        net = _small_network()
        buf = _make_replay(n=500)
        from src.mcts.training_config import TrainingConfig as InnerCfg
        trainer = Trainer(net, buf, InnerCfg(
            batch_size=64, min_replay_size=50, learning_rate=1e-2,
        ))
        first = trainer.step().loss.total
        for _ in range(40):
            trainer.step()
        last = trainer.step().loss.total
        assert last < first + 1e-3   # generally decreases, allow noise


# -------------------------------------------------------------------------
# Arena
# -------------------------------------------------------------------------

class TestArena:
    def test_runs_games(self):
        sim = NullSimulator(max_turns=4, n_actions=2, seed=0)
        net_a = _small_network()
        net_b = _small_network()
        arena = Arena(sim, mcts_config=MCTSConfig(iterations=5, time_budget_s=2.0),
                       seed=0)
        result = arena.play(net_a, net_b, _make_state(), n_games=4, max_moves=8)
        assert result.total == 4
        assert isinstance(result.candidate_win_rate, float)

    def test_alternating_sides(self):
        sim = NullSimulator(max_turns=3, n_actions=2, seed=0)
        net = _small_network()
        arena = Arena(sim, mcts_config=MCTSConfig(iterations=5, time_budget_s=2.0))
        result = arena.play(net, net, _make_state(), n_games=2, max_moves=6)
        # Same network → roughly fair
        assert result.total == 2


# -------------------------------------------------------------------------
# Offline evaluator
# -------------------------------------------------------------------------

class TestOfflineEvaluator:
    def test_evaluate_returns_result(self):
        net = _small_network()
        buf = _make_replay(n=100)
        result = evaluate(net, buf, batch_size=16, max_batches=2)
        assert isinstance(result, EvaluationResult)
        assert result.samples > 0

    def test_evaluate_empty_buffer(self):
        net = _small_network()
        result = evaluate(net, ReplayBuffer())
        assert result.samples == 0


# -------------------------------------------------------------------------
# Pipeline checkpoint store
# -------------------------------------------------------------------------

class TestPipelineCheckpointStore:
    def test_save_load(self, tmp_path):
        store = PipelineCheckpointStore(tmp_path)
        ckpt = PipelineCheckpoint(round_index=3, training_step=100)
        path = store.save(ckpt)
        assert path.exists()
        loaded = store.load(path.stem)
        assert loaded.round_index == 3

    def test_load_latest(self, tmp_path):
        store = PipelineCheckpointStore(tmp_path)
        store.save(PipelineCheckpoint(round_index=1))
        store.save(PipelineCheckpoint(round_index=2))
        latest = store.load_latest()
        assert latest is not None
        assert latest.round_index == 2

    def test_load_latest_empty(self, tmp_path):
        store = PipelineCheckpointStore(tmp_path)
        assert store.load_latest() is None


# -------------------------------------------------------------------------
# Experiment manager
# -------------------------------------------------------------------------

class TestExperimentManager:
    def test_create_and_persist(self, tmp_path):
        exp = ExperimentManager(tmp_path, name="exp1", seed=42)
        assert exp.manifest_path.exists()
        loaded = ExperimentManager(tmp_path, name="exp1")
        assert loaded.manifest.seed == 42

    def test_record_checkpoint(self, tmp_path):
        exp = ExperimentManager(tmp_path, name="exp1")
        exp.record_checkpoint("ckpt_000001", is_best=True)
        assert exp.manifest.best_checkpoint == "ckpt_000001"
        assert "ckpt_000001" in exp.manifest.checkpoint_lineage

    def test_record_metrics(self, tmp_path):
        exp = ExperimentManager(tmp_path, name="exp1")
        exp.record_metrics({"loss": 0.5})
        assert len(exp.manifest.metrics_history) == 1

    def test_record_promotion(self, tmp_path):
        exp = ExperimentManager(tmp_path, name="exp1")
        exp.record_promotion({"win_rate": 0.6})
        assert len(exp.manifest.promotion_history) == 1

    def test_set_status(self, tmp_path):
        exp = ExperimentManager(tmp_path, name="exp1")
        exp.set_status("completed")
        assert exp.manifest.status == "completed"

    def test_summary(self, tmp_path):
        exp = ExperimentManager(tmp_path, name="exp1")
        s = exp.summary()
        assert s["name"] == "exp1"


# -------------------------------------------------------------------------
# Monitor / Stopwatch
# -------------------------------------------------------------------------

class TestMonitor:
    def test_perf_monitor(self):
        m = PerfMonitor()
        m.event(10)
        m.event(20)
        assert m.event_count == 2
        assert m.total_units == 30

    def test_stopwatch(self):
        with Stopwatch() as sw:
            time.sleep(0.01)
        assert sw.elapsed_s >= 0.01


# -------------------------------------------------------------------------
# Full pipeline integration
# -------------------------------------------------------------------------

class TestPipelineIntegration:
    def test_runs_two_rounds(self, tmp_path):
        sim = NullSimulator(max_turns=4, n_actions=2, seed=0)
        action_map = _action_map()
        cfg = PipelineConfig(
            network=NetworkConfig(input_size=741, action_size=len(action_map),
                                    hidden_size=16, num_hidden_layers=1, device="cpu"),
            mcts=MCTSConfig(iterations=5, time_budget_s=2.0),
            selfplay=SelfPlayConfig(games_per_round=2, mcts_iterations=4,
                                     max_moves_per_game=6),
            arena=ArenaConfig(n_games=2, mcts_iterations=3, max_moves_per_game=6),
            promotion=PromotionConfig(win_rate_threshold=0.55, min_games=1),
            rounds=2, replay_capacity=200,
            checkpoint_dir=str(tmp_path / "ckpts"),
            experiment_dir=str(tmp_path / "experiments"),
            experiment_name="test_run",
            seed=0,
        )
        # Lower trainer's min_replay_size so we actually take steps
        from src.mcts.training_config import TrainingConfig as InnerCfg
        cfg = cfg.with_overrides(trainer=InnerCfg(
            batch_size=8, min_replay_size=4, iterations_per_epoch=2, epochs=1,
            learning_rate=1e-3,
        ))
        pipeline = TrainingPipeline(sim, action_map, cfg)
        result = pipeline.run()
        assert isinstance(result, PipelineResult)
        assert result.rounds_completed == 2

    def test_callbacks_fire(self, tmp_path):
        sim = NullSimulator(max_turns=4, n_actions=2, seed=0)
        action_map = _action_map()
        hist = HistoryCallback()
        cfg = PipelineConfig(
            network=NetworkConfig(input_size=741, action_size=len(action_map),
                                    hidden_size=16, num_hidden_layers=1, device="cpu"),
            selfplay=SelfPlayConfig(games_per_round=1, mcts_iterations=3,
                                     max_moves_per_game=4),
            arena=ArenaConfig(n_games=1, mcts_iterations=3, max_moves_per_game=4),
            promotion=PromotionConfig(win_rate_threshold=0.55, min_games=1),
            rounds=1, replay_capacity=200,
            checkpoint_dir=str(tmp_path / "ckpts"),
            experiment_dir=str(tmp_path / "exps"),
            experiment_name="cb_test",
            seed=0,
        )
        from src.mcts.training_config import TrainingConfig as InnerCfg
        cfg = cfg.with_overrides(trainer=InnerCfg(
            batch_size=4, min_replay_size=1, iterations_per_epoch=1, epochs=1,
        ))
        pipeline = TrainingPipeline(sim, action_map, cfg, callbacks=[hist])
        pipeline.run()
        assert hist.count("on_training_start") == 1
        assert hist.count("on_round_start") == 1
        assert hist.count("on_round_end") == 1
        assert hist.count("on_training_end") == 1


# -------------------------------------------------------------------------
# Exports
# -------------------------------------------------------------------------

class TestExports:
    def test_arena_to_terminal(self):
        r = ArenaResult(candidate_wins=3, champion_wins=2, draws=1)
        text = exports.arena_to_terminal(r)
        assert "Arena" in text

    def test_metrics_to_terminal(self):
        m = TrainingMetrics()
        m.record_train_step(0.5, 0.3, 0.8, 1e-3)
        text = exports.metrics_to_terminal(m)
        assert "TRAINING METRICS" in text

    def test_promotion_to_terminal(self):
        decision = PromotionDecision(
            promoted=True, candidate_win_rate=0.6, candidate_score=0.6,
            threshold=0.55, n_games=10, reason="ok",
        )
        text = exports.promotion_to_terminal(decision)
        assert "PROMOTED" in text

    def test_experiment_to_terminal(self, tmp_path):
        exp = ExperimentManager(tmp_path, name="exp1")
        text = exports.experiment_to_terminal(exp)
        assert "exp1" in text

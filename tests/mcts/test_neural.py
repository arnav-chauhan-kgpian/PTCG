"""
Comprehensive tests for Phase 9 — Neural Evaluation & Self-Play Infrastructure.
"""

from __future__ import annotations

import pytest

# Skip the whole module if torch missing
torch = pytest.importorskip("torch")

from src.game_state import GameState, GameStatus, PlayerState
from src.mcts import (
    CheckpointManager,
    CheckpointMetadata,
    GameStateFeatureEncoder,
    IdentityFeatureEncoder,
    InferenceCache,
    MCTSAction,
    MCTSConfig,
    MCTSSearch,
    NetworkConfig,
    NetworkWrapper,
    NeuralEvaluator,
    NeuralPriorPolicy,
    NullSimulator,
    ReplayBuffer,
    SelfPlayEngine,
    SelfPlayGame,
    TemperatureSchedule,
    TrainingConfig,
    TrainingSample,
    build_optimizer,
    build_scheduler,
    make_feature_encoder,
    make_network,
    outcome_to_value_target,
    policy_to_vector,
    reset_node_counter,
    visit_counts_to_policy,
)
from src.mcts.features import FeatureEncoderProtocol

# -------------------------------------------------------------------------
# Fixtures / helpers
# -------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _reset_counter():
    reset_node_counter()


def _make_state(turn: int = 0, current: int = 0) -> GameState:
    return GameState(
        turn_number=turn,
        current_player=current,
        game_status=GameStatus.ONGOING,
        players=(
            PlayerState(player_id=0, prizes_remaining=6, deck_size=55, hand_count=5),
            PlayerState(player_id=1, prizes_remaining=6, deck_size=55, hand_count=5),
        ),
    )


def _make_simulator(max_turns: int = 6, n_actions: int = 3) -> NullSimulator:
    return NullSimulator(max_turns=max_turns, n_actions=n_actions, seed=0)


def _small_network() -> NetworkWrapper:
    return NetworkWrapper(NetworkConfig(
        input_size=741, action_size=8, hidden_size=32, num_hidden_layers=1,
        device="cpu",
    ))


def _identity_network(input_size: int = 16, action_size: int = 5) -> NetworkWrapper:
    return NetworkWrapper(NetworkConfig(
        input_size=input_size, action_size=action_size, hidden_size=16,
        num_hidden_layers=1, device="cpu",
    ))


# -------------------------------------------------------------------------
# Feature encoder
# -------------------------------------------------------------------------

class TestFeatureEncoder:
    def test_gamestate_encoder_size(self):
        enc = GameStateFeatureEncoder()
        assert enc.feature_size == 741
        vec = enc.encode(_make_state())
        assert len(vec) == 741

    def test_gamestate_deterministic(self):
        enc = GameStateFeatureEncoder()
        v1 = enc.encode(_make_state())
        v2 = enc.encode(_make_state())
        assert v1 == v2

    def test_identity_encoder(self):
        enc = IdentityFeatureEncoder(size=16)
        v = enc.encode(_make_state())
        assert len(v) == 16
        assert all(0.0 <= x <= 1.0 for x in v)

    def test_identity_deterministic(self):
        enc = IdentityFeatureEncoder()
        v1 = enc.encode(_make_state())
        v2 = enc.encode(_make_state())
        assert v1 == v2

    def test_protocol_compliance(self):
        enc = GameStateFeatureEncoder()
        assert isinstance(enc, FeatureEncoderProtocol)
        enc2 = IdentityFeatureEncoder()
        assert isinstance(enc2, FeatureEncoderProtocol)

    def test_factory(self):
        assert isinstance(make_feature_encoder("gamestate"), GameStateFeatureEncoder)
        assert isinstance(make_feature_encoder("identity"), IdentityFeatureEncoder)
        with pytest.raises(ValueError):
            make_feature_encoder("unknown")

    def test_decode_returns_none(self):
        assert GameStateFeatureEncoder().decode((1.0,)) is None
        assert IdentityFeatureEncoder().decode((1.0,)) is None


# -------------------------------------------------------------------------
# Network wrapper
# -------------------------------------------------------------------------

class TestNetwork:
    def test_construction(self):
        wrapper = _small_network()
        assert wrapper.device == "cpu"
        assert wrapper.num_parameters > 0

    def test_predict_single(self):
        wrapper = _small_network()
        features = tuple([0.5] * 741)
        logits, value = wrapper.predict(features)
        assert len(logits) == 8
        assert 0.0 <= value <= 1.0

    def test_predict_batch(self):
        wrapper = _small_network()
        batch = [tuple([0.1] * 741), tuple([0.9] * 741), tuple([0.5] * 741)]
        logits_batch, value_batch = wrapper.predict_batch(batch)
        assert len(logits_batch) == 3
        assert len(value_batch) == 3
        assert all(len(l) == 8 for l in logits_batch)

    def test_predict_empty_batch(self):
        wrapper = _small_network()
        logits, values = wrapper.predict_batch([])
        assert logits == []
        assert values == []

    def test_eval_mode_no_grad(self):
        wrapper = _small_network()
        assert not wrapper.model.training
        # All parameters should not accumulate grad during predict
        features = tuple([0.0] * 741)
        wrapper.predict(features)
        for p in wrapper.model.parameters():
            assert p.grad is None

    def test_state_dict_round_trip(self):
        w1 = _small_network()
        sd = w1.state_dict()
        w2 = _small_network()
        w2.load_state_dict(sd)
        f = tuple([0.3] * 741)
        l1, v1 = w1.predict(f)
        l2, v2 = w2.predict(f)
        assert l1 == l2
        assert v1 == v2

    def test_save_load(self, tmp_path):
        path = tmp_path / "model.pt"
        w1 = _small_network()
        w1.save(path)
        w2 = NetworkWrapper.load(path)
        f = tuple([0.5] * 741)
        l1, v1 = w1.predict(f)
        l2, v2 = w2.predict(f)
        assert v1 == pytest.approx(v2)
        assert all(a == pytest.approx(b) for a, b in zip(l1, l2))

    def test_to_cpu(self):
        wrapper = _small_network()
        wrapper.to("cpu")
        assert wrapper.device == "cpu"

    def test_make_network(self):
        wrapper = make_network()
        assert wrapper.num_parameters > 0

    def test_torchscript_falls_back_gracefully(self):
        cfg = NetworkConfig(
            input_size=8, action_size=4, hidden_size=8, num_hidden_layers=1,
            torchscript=True, device="cpu",
        )
        wrapper = NetworkWrapper(cfg)
        # Should not raise — either traced or fell back
        logits, value = wrapper.predict(tuple([0.5] * 8))
        assert len(logits) == 4


# -------------------------------------------------------------------------
# Inference cache
# -------------------------------------------------------------------------

class TestInferenceCache:
    def test_miss(self):
        c = InferenceCache(max_size=10)
        assert c.get("xyz") is None
        assert c.stats.misses == 1

    def test_put_get(self):
        c = InferenceCache()
        c.put("k", [0.1, 0.9], 0.7)
        result = c.get("k")
        assert result is not None
        logits, v = result
        assert logits == [0.1, 0.9]
        assert v == 0.7
        assert c.stats.hits == 1

    def test_lru_eviction(self):
        c = InferenceCache(max_size=2)
        c.put("a", [], 0.1)
        c.put("b", [], 0.2)
        c.put("c", [], 0.3)
        assert len(c) == 2
        assert c.stats.evictions == 1

    def test_by_state(self):
        c = InferenceCache()
        s = _make_state()
        c.put_for_state(s, [0.5], 0.6)
        result = c.get_by_state(s)
        assert result is not None
        assert result[1] == 0.6

    def test_clear(self):
        c = InferenceCache()
        c.put("k", [], 0.1)
        c.clear()
        assert len(c) == 0

    def test_summary(self):
        c = InferenceCache()
        c.put("k", [], 0.1)
        s = c.summary()
        assert s["size"] == 1


# -------------------------------------------------------------------------
# Neural evaluator
# -------------------------------------------------------------------------

class TestNeuralEvaluator:
    def test_evaluate_returns_value_in_range(self):
        wrapper = _identity_network()
        enc = IdentityFeatureEncoder(size=16)
        actions = [MCTSAction(action_type=f"a{i}") for i in range(3)]
        ev = NeuralEvaluator(wrapper, enc, action_map=actions)
        v, priors = ev.evaluate(_make_state(), actions)
        assert 0.0 <= v <= 1.0
        assert sum(priors.values()) == pytest.approx(1.0)

    def test_priors_sum_to_one(self):
        wrapper = _identity_network()
        enc = IdentityFeatureEncoder()
        actions = [MCTSAction(action_type=f"a{i}") for i in range(3)]
        ev = NeuralEvaluator(wrapper, enc, action_map=actions)
        _, priors = ev.evaluate(_make_state(), actions)
        assert sum(priors.values()) == pytest.approx(1.0)

    def test_no_actions(self):
        wrapper = _identity_network()
        enc = IdentityFeatureEncoder()
        ev = NeuralEvaluator(wrapper, enc)
        v, priors = ev.evaluate(_make_state(), [])
        assert priors == {}

    def test_cache_avoids_repeat_inference(self):
        wrapper = _identity_network()
        enc = IdentityFeatureEncoder()
        cache = InferenceCache()
        actions = [MCTSAction(action_type="x")]
        ev = NeuralEvaluator(wrapper, enc, action_map=actions, cache=cache)
        ev.evaluate(_make_state(), actions)
        ev.evaluate(_make_state(), actions)
        assert ev.cache_hits == 1
        assert ev.cache_misses == 1

    def test_value_only(self):
        wrapper = _identity_network()
        enc = IdentityFeatureEncoder()
        ev = NeuralEvaluator(wrapper, enc)
        v = ev.value_only(_make_state())
        assert 0.0 <= v <= 1.0

    def test_unknown_action_uses_mean_logit(self):
        wrapper = _identity_network()
        enc = IdentityFeatureEncoder()
        known = [MCTSAction(action_type="a"), MCTSAction(action_type="b")]
        # Legal actions include one not in action_map
        legal = known + [MCTSAction(action_type="z")]
        ev = NeuralEvaluator(wrapper, enc, action_map=known)
        _, priors = ev.evaluate(_make_state(), legal)
        assert len(priors) == 3
        assert sum(priors.values()) == pytest.approx(1.0)

    def test_summary(self):
        ev = NeuralEvaluator(_identity_network(), IdentityFeatureEncoder())
        s = ev.summary()
        assert "call_count" in s


# -------------------------------------------------------------------------
# Neural prior policy
# -------------------------------------------------------------------------

class TestNeuralPriorPolicy:
    def test_priors_sum_to_one(self):
        wrapper = _identity_network()
        enc = IdentityFeatureEncoder()
        actions = [MCTSAction(action_type=f"a{i}") for i in range(4)]
        p = NeuralPriorPolicy(wrapper, enc, action_map=actions)
        priors = p.prior_distribution(_make_state(), actions)
        assert sum(priors.values()) == pytest.approx(1.0)

    def test_empty_actions(self):
        p = NeuralPriorPolicy(_identity_network(), IdentityFeatureEncoder())
        assert p.prior_distribution(_make_state(), []) == {}

    def test_illegal_actions_excluded(self):
        wrapper = _identity_network()
        enc = IdentityFeatureEncoder()
        full = [MCTSAction(action_type=f"a{i}") for i in range(5)]
        legal = full[:2]
        p = NeuralPriorPolicy(wrapper, enc, action_map=full)
        priors = p.prior_distribution(_make_state(), legal)
        assert set(priors.keys()) == set(legal)

    def test_batch_prediction(self):
        wrapper = _identity_network()
        enc = IdentityFeatureEncoder()
        actions = [MCTSAction(action_type=f"a{i}") for i in range(3)]
        p = NeuralPriorPolicy(wrapper, enc, action_map=actions)
        states = [_make_state(turn=i) for i in range(4)]
        results = p.prior_distribution_batch(states, [actions] * 4)
        assert len(results) == 4
        for d in results:
            assert sum(d.values()) == pytest.approx(1.0)

    def test_cache_shared_with_evaluator(self):
        wrapper = _identity_network()
        enc = IdentityFeatureEncoder()
        cache = InferenceCache()
        actions = [MCTSAction(action_type="x"), MCTSAction(action_type="y")]
        ev = NeuralEvaluator(wrapper, enc, action_map=actions, cache=cache)
        pp = NeuralPriorPolicy(wrapper, enc, action_map=actions, cache=cache)
        ev.evaluate(_make_state(), actions)
        pp.prior_distribution(_make_state(), actions)
        # Second call should hit cache
        assert pp.cache_hits == 1


# -------------------------------------------------------------------------
# Training targets
# -------------------------------------------------------------------------

class TestTrainingTargets:
    def test_visit_counts_to_policy_uniform_when_empty(self):
        assert visit_counts_to_policy({}) == {}

    def test_visit_counts_temperature_1(self):
        counts = {MCTSAction(action_type="a"): 3, MCTSAction(action_type="b"): 1}
        policy = visit_counts_to_policy(counts, temperature=1.0)
        assert sum(policy.values()) == pytest.approx(1.0)
        a = next(k for k in policy if k.action_type == "a")
        b = next(k for k in policy if k.action_type == "b")
        assert policy[a] == pytest.approx(0.75)
        assert policy[b] == pytest.approx(0.25)

    def test_visit_counts_temperature_zero_argmax(self):
        counts = {MCTSAction(action_type="a"): 3, MCTSAction(action_type="b"): 1}
        policy = visit_counts_to_policy(counts, temperature=0.0)
        a = next(k for k in policy if k.action_type == "a")
        assert policy[a] == 1.0

    def test_visit_counts_high_temperature_flattens(self):
        counts = {MCTSAction(action_type="a"): 10, MCTSAction(action_type="b"): 1}
        flat = visit_counts_to_policy(counts, temperature=5.0)
        sharp = visit_counts_to_policy(counts, temperature=1.0)
        a = next(k for k in counts if k.action_type == "a")
        # Higher temperature → less peaked
        assert flat[a] < sharp[a]

    def test_policy_to_vector(self):
        action_map = [MCTSAction(action_type=f"a{i}") for i in range(3)]
        policy = {action_map[0]: 0.7, action_map[2]: 0.3}
        vec = policy_to_vector(policy, action_map)
        assert vec == pytest.approx([0.7, 0.0, 0.3])

    def test_policy_to_vector_normalises(self):
        action_map = [MCTSAction(action_type="a"), MCTSAction(action_type="b")]
        policy = {action_map[0]: 1.0, action_map[1]: 1.0}
        vec = policy_to_vector(policy, action_map)
        assert sum(vec) == pytest.approx(1.0)

    def test_outcome_winner_match(self):
        assert outcome_to_value_target(1.0, move_player=0, winner=0) == 1.0
        assert outcome_to_value_target(0.0, move_player=1, winner=1) == 1.0

    def test_outcome_winner_loses(self):
        assert outcome_to_value_target(1.0, move_player=0, winner=1) == 0.0

    def test_outcome_draw(self):
        # winner=None → use terminal value
        assert outcome_to_value_target(0.5, move_player=0, winner=None) == 0.5

    def test_temperature_schedule(self):
        sched = TemperatureSchedule(early_moves=5, temperature_high=1.0, temperature_low=0.0)
        assert sched.temperature_for(0) == 1.0
        assert sched.temperature_for(4) == 1.0
        assert sched.temperature_for(5) == 0.0

    def test_training_sample_roundtrip(self):
        s = TrainingSample(
            state_features=(0.1, 0.2),
            policy_target=(0.5, 0.5),
            value_target=0.7,
            move_player=1,
            move_number=3,
        )
        s2 = TrainingSample.from_dict(s.to_dict())
        assert s == s2


# -------------------------------------------------------------------------
# Replay buffer
# -------------------------------------------------------------------------

def _sample(value=0.5) -> TrainingSample:
    return TrainingSample(
        state_features=(0.1, 0.2, 0.3),
        policy_target=(0.5, 0.5),
        value_target=value,
    )


class TestReplayBuffer:
    def test_append(self):
        buf = ReplayBuffer(capacity=10)
        buf.append(_sample())
        assert len(buf) == 1
        assert buf.stats.appended == 1

    def test_extend(self):
        buf = ReplayBuffer(capacity=10)
        buf.extend([_sample(0.1), _sample(0.2), _sample(0.3)])
        assert len(buf) == 3

    def test_capacity_eviction(self):
        buf = ReplayBuffer(capacity=2)
        for i in range(5):
            buf.append(_sample(value=i / 10))
        assert len(buf) == 2

    def test_sample(self):
        buf = ReplayBuffer(capacity=10, seed=0)
        for i in range(5):
            buf.append(_sample(value=i / 10))
        batch = buf.sample(3)
        assert len(batch) == 3
        assert all(isinstance(s, TrainingSample) for s in batch)

    def test_sample_features_targets(self):
        buf = ReplayBuffer(capacity=10, seed=0)
        for i in range(5):
            buf.append(_sample(value=i / 10))
        features, policies, values = buf.sample_features_targets(3)
        assert len(features) == 3
        assert len(policies) == 3
        assert len(values) == 3

    def test_sample_empty(self):
        assert ReplayBuffer().sample(5) == []

    def test_sample_oversize(self):
        buf = ReplayBuffer(capacity=10, seed=0)
        buf.append(_sample())
        out = buf.sample(5)
        assert len(out) == 5  # with-replacement

    def test_shuffle(self):
        buf = ReplayBuffer(capacity=10, seed=0)
        for i in range(5):
            buf.append(_sample(value=i / 10))
        buf.shuffle()
        assert len(buf) == 5

    def test_clear(self):
        buf = ReplayBuffer()
        buf.append(_sample())
        buf.clear()
        assert len(buf) == 0

    def test_save_load(self, tmp_path):
        path = tmp_path / "buf.json"
        buf = ReplayBuffer(capacity=5)
        buf.append(_sample(0.7))
        buf.save(path)
        buf2 = ReplayBuffer.load(path)
        assert len(buf2) == 1
        assert buf2[0].value_target == 0.7

    def test_is_ready(self):
        buf = ReplayBuffer()
        assert not buf.is_ready(5)
        for _ in range(5):
            buf.append(_sample())
        assert buf.is_ready(5)

    def test_summary(self):
        buf = ReplayBuffer(capacity=10)
        buf.append(_sample())
        s = buf.summary()
        assert s["current_size"] == 1


# -------------------------------------------------------------------------
# Self-play engine
# -------------------------------------------------------------------------

class TestSelfPlay:
    def test_runs_one_game(self):
        sim = _make_simulator(max_turns=4, n_actions=2)
        wrapper = _small_network()
        enc = GameStateFeatureEncoder()
        cfg = MCTSConfig(iterations=10, time_budget_s=2.0)
        search = MCTSSearch(sim, config=cfg)
        engine = SelfPlayEngine(sim, search, enc, max_moves=10, seed=0)
        game = engine.play_game(_make_state())
        assert isinstance(game, SelfPlayGame)
        assert game.move_count > 0

    def test_terminates_naturally(self):
        sim = _make_simulator(max_turns=3, n_actions=2)
        wrapper = _small_network()
        enc = GameStateFeatureEncoder()
        search = MCTSSearch(sim, config=MCTSConfig(iterations=5, time_budget_s=2.0))
        engine = SelfPlayEngine(sim, search, enc, max_moves=20, seed=0)
        game = engine.play_game(_make_state())
        assert game.terminated_by in ("terminal", "max_moves", "no_actions")

    def test_records_features(self):
        sim = _make_simulator(max_turns=3, n_actions=2)
        enc = GameStateFeatureEncoder()
        search = MCTSSearch(sim, config=MCTSConfig(iterations=5, time_budget_s=2.0))
        engine = SelfPlayEngine(sim, search, enc, max_moves=10, seed=0)
        game = engine.play_game(_make_state())
        for m in game.moves:
            assert len(m.state_features) == enc.feature_size

    def test_to_training_samples(self):
        sim = _make_simulator(max_turns=3, n_actions=2)
        enc = GameStateFeatureEncoder()
        search = MCTSSearch(sim, config=MCTSConfig(iterations=5, time_budget_s=2.0))
        engine = SelfPlayEngine(sim, search, enc, max_moves=10, seed=0)
        game = engine.play_game(_make_state())
        action_map = [MCTSAction(action_type=f"action_{i}", details=(("turn", str(t)),))
                       for i in range(2) for t in range(5)]
        action_map.append(MCTSAction.end_turn())
        samples = game.to_training_samples(action_map)
        assert len(samples) == game.move_count
        for s in samples:
            assert len(s.state_features) == enc.feature_size
            assert 0.0 <= s.value_target <= 1.0

    def test_play_n_games(self):
        sim = _make_simulator(max_turns=3, n_actions=2)
        enc = GameStateFeatureEncoder()
        search = MCTSSearch(sim, config=MCTSConfig(iterations=5, time_budget_s=2.0))
        engine = SelfPlayEngine(sim, search, enc, max_moves=10, seed=0)
        games = engine.play_n_games(_make_state(), 2)
        assert len(games) == 2

    def test_summary(self):
        sim = _make_simulator(max_turns=3, n_actions=2)
        enc = GameStateFeatureEncoder()
        search = MCTSSearch(sim, config=MCTSConfig(iterations=5, time_budget_s=2.0))
        engine = SelfPlayEngine(sim, search, enc, max_moves=10, seed=0)
        game = engine.play_game(_make_state())
        s = game.summary()
        assert "move_count" in s


# -------------------------------------------------------------------------
# MCTS integration with neural components
# -------------------------------------------------------------------------

class TestMCTSNeuralIntegration:
    def test_search_with_neural_eval_and_policy(self):
        sim = _make_simulator(max_turns=4, n_actions=3)
        wrapper = _small_network()
        enc = GameStateFeatureEncoder()
        cache = InferenceCache()
        actions = [MCTSAction(action_type=f"action_{i}", details=(("turn", "0"),))
                    for i in range(3)] + [MCTSAction.end_turn()]
        ev = NeuralEvaluator(wrapper, enc, action_map=actions, cache=cache)
        pp = NeuralPriorPolicy(wrapper, enc, action_map=actions, cache=cache)
        cfg = MCTSConfig(iterations=30, time_budget_s=2.0)
        search = MCTSSearch(sim, config=cfg, evaluator=ev, prior_policy=pp)
        result = search.run(_make_state())
        assert result.best_action is not None

    def test_cache_hits_during_search(self):
        sim = _make_simulator(max_turns=4, n_actions=2)
        wrapper = _small_network()
        enc = GameStateFeatureEncoder()
        cache = InferenceCache()
        ev = NeuralEvaluator(wrapper, enc, cache=cache)
        search = MCTSSearch(sim, config=MCTSConfig(iterations=40, time_budget_s=2.0),
                            evaluator=ev)
        search.run(_make_state())
        assert cache.stats.inserts > 0

    def test_heuristic_path_still_works(self):
        sim = _make_simulator()
        search = MCTSSearch(sim, config=MCTSConfig.fast())
        result = search.run(_make_state())
        assert result.best_action is not None


# -------------------------------------------------------------------------
# Training config & builders
# -------------------------------------------------------------------------

class TestTrainingConfig:
    def test_defaults(self):
        cfg = TrainingConfig()
        assert cfg.batch_size > 0
        assert cfg.learning_rate > 0

    def test_overrides(self):
        cfg = TrainingConfig().with_overrides(learning_rate=1e-2)
        assert cfg.learning_rate == 1e-2

    def test_build_adam(self):
        net = _small_network()
        opt = build_optimizer(net.model.parameters(), TrainingConfig(optimizer="adam"))
        assert opt is not None

    def test_build_sgd(self):
        net = _small_network()
        opt = build_optimizer(net.model.parameters(),
                              TrainingConfig(optimizer="sgd"))
        assert opt is not None

    def test_build_adamw(self):
        net = _small_network()
        opt = build_optimizer(net.model.parameters(),
                              TrainingConfig(optimizer="adamw"))
        assert opt is not None

    def test_build_unknown_optimizer(self):
        net = _small_network()
        with pytest.raises(ValueError):
            build_optimizer(net.model.parameters(),
                            TrainingConfig(optimizer="rmsprop"))

    def test_build_scheduler_none(self):
        net = _small_network()
        opt = build_optimizer(net.model.parameters(), TrainingConfig())
        assert build_scheduler(opt, TrainingConfig(scheduler="none")) is None

    def test_build_scheduler_step(self):
        net = _small_network()
        opt = build_optimizer(net.model.parameters(), TrainingConfig())
        sched = build_scheduler(opt, TrainingConfig(scheduler="step"))
        assert sched is not None

    def test_build_scheduler_cosine(self):
        net = _small_network()
        opt = build_optimizer(net.model.parameters(), TrainingConfig())
        sched = build_scheduler(opt, TrainingConfig(scheduler="cosine"))
        assert sched is not None

    def test_resolve_device(self):
        cfg = TrainingConfig(device="cpu")
        assert cfg.resolve_device() == "cpu"


# -------------------------------------------------------------------------
# Checkpoint manager
# -------------------------------------------------------------------------

class TestCheckpoints:
    def test_save_and_load(self, tmp_path):
        mgr = CheckpointManager(tmp_path, keep_last=3)
        wrapper = _small_network()
        meta = CheckpointMetadata(training_step=1, timestamp="2026-01-01T00:00:00")
        path = mgr.save(wrapper, meta)
        assert path.exists()
        wrapper2, meta2 = mgr.load(path.stem)
        assert meta2.training_step == 1

    def test_load_latest(self, tmp_path):
        mgr = CheckpointManager(tmp_path, keep_last=3)
        wrapper = _small_network()
        mgr.save(wrapper, CheckpointMetadata(training_step=1, timestamp="t1"))
        mgr.save(wrapper, CheckpointMetadata(training_step=2, timestamp="t2"))
        _, meta = mgr.load_latest()
        assert meta.training_step == 2

    def test_keep_last_prunes(self, tmp_path):
        mgr = CheckpointManager(tmp_path, keep_last=2)
        wrapper = _small_network()
        for i in range(5):
            mgr.save(wrapper, CheckpointMetadata(training_step=i, timestamp=f"t{i}"))
        ckpts = mgr.list_checkpoints()
        assert len(ckpts) <= 2

    def test_load_nonexistent(self, tmp_path):
        mgr = CheckpointManager(tmp_path)
        with pytest.raises(FileNotFoundError):
            mgr.load_latest()

    def test_metadata_dict_roundtrip(self):
        meta = CheckpointMetadata(training_step=42, timestamp="now", notes="hello")
        d = meta.to_dict()
        meta2 = CheckpointMetadata.from_dict(d)
        assert meta2.training_step == 42
        assert meta2.notes == "hello"

    def test_summary(self, tmp_path):
        mgr = CheckpointManager(tmp_path)
        s = mgr.summary()
        assert "root" in s

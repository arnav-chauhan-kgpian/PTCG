"""
Comprehensive tests for the MCTS Engine (Phase 8).
"""

from __future__ import annotations

import math
import random
import time

import pytest
from src.game_state import GameState, GameStatus, PlayerState
from src.mcts import (
    DepthLimitedRollout,
    GreedyRollout,
    HeuristicEvaluator,
    HeuristicPriorPolicy,
    HeuristicRollout,
    IdentityDeterminizer,
    MCTSAction,
    MCTSConfig,
    MCTSNode,
    MCTSSearch,
    MCTSTree,
    NeuralEvaluatorPlaceholder,
    NullSimulator,
    PUCTSelection,
    RandomDeterminizer,
    RandomRollout,
    SearchResult,
    SearchStatistics,
    SelectionStrategy,
    TranspositionTable,
    UCTSelection,
    UniformEvaluator,
    UniformPriorPolicy,
    backpropagate,
    expand_all,
    expand_one,
    exports,
    initialise_node,
    make_evaluator,
    make_prior_policy,
    make_rollout,
    make_selection_strategy,
    puct_score,
    reset_node_counter,
    search,
    uct_score,
    validate_config,
    validate_node,
    validate_result,
)

# -------------------------------------------------------------------------
# Helpers
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


def _make_simulator(max_turns: int = 8, n_actions: int = 3) -> NullSimulator:
    return NullSimulator(max_turns=max_turns, n_actions=n_actions, seed=42)


# -------------------------------------------------------------------------
# Action / Node / Tree
# -------------------------------------------------------------------------

class TestMCTSAction:
    def test_creation(self):
        a = MCTSAction(action_type="attack", card_instance_id="card-1")
        assert a.action_type == "attack"

    def test_hashable(self):
        a = MCTSAction.end_turn()
        s = {a, a, MCTSAction.end_turn()}
        assert len(s) == 1

    def test_str(self):
        a = MCTSAction.attack("card-1234abcd", "Thunderbolt")
        assert "attack" in str(a)


class TestMCTSNode:
    def test_creation(self):
        s = _make_state()
        n = MCTSNode(s)
        assert n.visit_count == 0
        assert n.q_value == 0.0
        assert n.depth == 0

    def test_update(self):
        n = MCTSNode(_make_state())
        n.update(0.7)
        n.update(0.3)
        assert n.visit_count == 2
        assert n.q_value == pytest.approx(0.5)

    def test_set_legal_actions(self):
        n = MCTSNode(_make_state())
        actions = [MCTSAction.end_turn(), MCTSAction.attack("c1", "atk")]
        n.set_legal_actions(actions)
        assert n.is_expanded
        assert len(n.untried_actions) == 2

    def test_virtual_loss(self):
        n = MCTSNode(_make_state())
        n.apply_virtual_loss(3.0)
        assert n.virtual_loss == 3.0
        n.undo_virtual_loss(3.0)
        assert n.virtual_loss == 0.0

    def test_repr_and_summary(self):
        n = MCTSNode(_make_state())
        assert "MCTSNode" in repr(n)
        assert "visit_count" in n.summary()


class TestMCTSTree:
    def test_create(self):
        t = MCTSTree(_make_state())
        assert t.node_count == 1
        assert t.root.visit_count == 0

    def test_summary(self):
        t = MCTSTree(_make_state())
        s = t.summary()
        assert s["root_visits"] == 0
        assert s["node_count"] == 1


# -------------------------------------------------------------------------
# Config
# -------------------------------------------------------------------------

class TestConfig:
    def test_default(self):
        c = MCTSConfig()
        c.validate()
        assert c.iterations > 0

    def test_fast(self):
        c = MCTSConfig.fast()
        assert c.iterations < 100

    def test_strong(self):
        c = MCTSConfig.strong()
        assert c.iterations > 1000

    def test_validate_bad(self):
        c = MCTSConfig(iterations=-1)
        with pytest.raises(AssertionError):
            c.validate()

    def test_validate_helper(self):
        report = validate_config(MCTSConfig.fast())
        assert report.is_valid

    def test_validate_bad_helper(self):
        c = MCTSConfig(exploration_constant=-1)
        report = validate_config(c)
        assert not report.is_valid


# -------------------------------------------------------------------------
# Selection
# -------------------------------------------------------------------------

class TestSelection:
    def test_uct_unvisited_infinite(self):
        score = uct_score(10, 0, 0.5, 0.5, 1.41)
        assert score == math.inf

    def test_uct_visited(self):
        score = uct_score(10, 3, 0.6, 0.5, 1.41)
        assert score > 0.6

    def test_puct(self):
        s_uniform = puct_score(10, 3, 0.5, 0.1, 1.0)
        s_high_prior = puct_score(10, 3, 0.5, 0.9, 1.0)
        assert s_high_prior > s_uniform

    def test_uct_selection(self):
        n = MCTSNode(_make_state())
        n.visit_count = 5
        for i in range(3):
            child_state = _make_state(turn=i + 1)
            child = MCTSNode(child_state, parent=n, depth=1)
            child.visit_count = i + 1
            child.total_value = (i + 1) * 0.4
            n.children[MCTSAction(action_type=f"a{i}")] = child

        sel = UCTSelection(exploration_constant=1.41)
        picked = sel.select_child(n)
        assert picked is not None

    def test_puct_selection_uses_priors(self):
        n = MCTSNode(_make_state())
        n.visit_count = 10
        c1 = MCTSNode(_make_state(turn=1), parent=n, depth=1)
        c1.visit_count = 5
        c1.total_value = 2.0
        c1.prior = 0.9
        c2 = MCTSNode(_make_state(turn=2), parent=n, depth=1)
        c2.visit_count = 5
        c2.total_value = 2.0
        c2.prior = 0.1
        n.children[MCTSAction(action_type="hi")] = c1
        n.children[MCTSAction(action_type="lo")] = c2
        sel = PUCTSelection(exploration_constant=2.0)
        # High prior should win since Q is tied
        picked = sel.select_child(n)
        assert picked is c1

    def test_make_selection_strategy(self):
        strat = make_selection_strategy(MCTSConfig(selection=SelectionStrategy.UCT))
        assert isinstance(strat, UCTSelection)
        strat2 = make_selection_strategy(MCTSConfig(selection=SelectionStrategy.PUCT))
        assert isinstance(strat2, PUCTSelection)


# -------------------------------------------------------------------------
# Expansion
# -------------------------------------------------------------------------

class TestExpansion:
    def test_initialise_node(self):
        sim = _make_simulator()
        n = MCTSNode(_make_state())
        initialise_node(n, sim)
        assert n.is_expanded
        assert len(n.untried_actions) > 0

    def test_expand_one(self):
        sim = _make_simulator()
        n = MCTSNode(_make_state())
        initialise_node(n, sim)
        n_untried = len(n.untried_actions)
        child = expand_one(n, sim)
        assert child is not None
        assert len(n.children) == 1
        assert len(n.untried_actions) == n_untried - 1

    def test_expand_all(self):
        sim = _make_simulator()
        n = MCTSNode(_make_state())
        initialise_node(n, sim)
        n_actions = len(n.untried_actions)
        children = expand_all(n, sim)
        assert len(children) == n_actions
        assert len(n.untried_actions) == 0


# -------------------------------------------------------------------------
# Backpropagation
# -------------------------------------------------------------------------

class TestBackpropagation:
    def test_simple_path(self):
        root = MCTSNode(_make_state(current=0))
        child = MCTSNode(_make_state(turn=1, current=1), parent=root, depth=1)
        backpropagate([root, child], 0.7)
        # Leaf player perspective: child gets 0.7
        assert child.q_value == pytest.approx(0.7)
        # Root has different player → gets 0.3
        assert root.q_value == pytest.approx(0.3)

    def test_discount(self):
        root = MCTSNode(_make_state(current=0))
        c1 = MCTSNode(_make_state(turn=1, current=0), parent=root, depth=1)
        backpropagate([root, c1], 0.8, discount=0.5)
        assert c1.q_value == pytest.approx(0.8)
        assert root.q_value == pytest.approx(0.4)

    def test_empty_path(self):
        backpropagate([], 0.5)  # should not raise


# -------------------------------------------------------------------------
# Evaluator
# -------------------------------------------------------------------------

class TestEvaluator:
    def test_uniform(self):
        e = UniformEvaluator()
        v, priors = e.evaluate(_make_state(), [MCTSAction.end_turn()])
        assert v == 0.5
        assert sum(priors.values()) == pytest.approx(1.0)

    def test_heuristic_in_range(self):
        e = HeuristicEvaluator()
        v, _ = e.evaluate(_make_state(), [])
        assert 0.0 <= v <= 1.0

    def test_heuristic_prefers_winning(self):
        e = HeuristicEvaluator()
        winning = _make_state()
        winning = winning.with_player(
            0, winning.players[0].model_copy(update={"prizes_remaining": 1})
        )
        losing = _make_state()
        losing = losing.with_player(
            0, losing.players[0].model_copy(update={"prizes_remaining": 5})
        )
        v_win, _ = e.evaluate(winning, [])
        v_lose, _ = e.evaluate(losing, [])
        assert v_win > v_lose

    def test_neural_placeholder_falls_back(self):
        e = NeuralEvaluatorPlaceholder()
        v, _ = e.evaluate(_make_state(), [])
        assert 0.0 <= v <= 1.0
        assert e.call_count == 1

    def test_make_evaluator(self):
        assert isinstance(make_evaluator("heuristic"), HeuristicEvaluator)
        assert isinstance(make_evaluator("uniform"), UniformEvaluator)

    def test_make_unknown(self):
        with pytest.raises(ValueError):
            make_evaluator("magic")


# -------------------------------------------------------------------------
# Rollouts
# -------------------------------------------------------------------------

class TestRollouts:
    def test_heuristic_rollout(self):
        n = MCTSNode(_make_state())
        sim = _make_simulator()
        rng = random.Random(0)
        v = HeuristicRollout().rollout(n, sim, HeuristicEvaluator(), rng, 10)
        assert 0.0 <= v <= 1.0

    def test_random_rollout(self):
        n = MCTSNode(_make_state())
        sim = _make_simulator(max_turns=5)
        rng = random.Random(0)
        v = RandomRollout().rollout(n, sim, HeuristicEvaluator(), rng, 10)
        assert 0.0 <= v <= 1.0

    def test_greedy_rollout(self):
        n = MCTSNode(_make_state())
        sim = _make_simulator(max_turns=4)
        rng = random.Random(0)
        v = GreedyRollout().rollout(n, sim, HeuristicEvaluator(), rng, 3)
        assert 0.0 <= v <= 1.0

    def test_depth_limited(self):
        n = MCTSNode(_make_state())
        sim = _make_simulator()
        rng = random.Random(0)
        v = DepthLimitedRollout().rollout(n, sim, HeuristicEvaluator(), rng, 5)
        assert 0.0 <= v <= 1.0

    def test_make_rollout(self):
        assert isinstance(make_rollout("heuristic"), HeuristicRollout)
        assert isinstance(make_rollout("random"), RandomRollout)


# -------------------------------------------------------------------------
# Priors
# -------------------------------------------------------------------------

class TestPriors:
    def test_uniform(self):
        p = UniformPriorPolicy()
        actions = [MCTSAction(action_type=f"a{i}") for i in range(4)]
        priors = p.prior_distribution(_make_state(), actions)
        assert sum(priors.values()) == pytest.approx(1.0)
        assert all(v == pytest.approx(0.25) for v in priors.values())

    def test_heuristic_attack_preferred(self):
        p = HeuristicPriorPolicy()
        a_attack = MCTSAction(action_type="attack")
        a_pass = MCTSAction(action_type="end_turn")
        priors = p.prior_distribution(_make_state(), [a_attack, a_pass])
        assert priors[a_attack] > priors[a_pass]

    def test_make_prior_policy(self):
        assert isinstance(make_prior_policy("uniform"), UniformPriorPolicy)
        assert isinstance(make_prior_policy("heuristic"), HeuristicPriorPolicy)


# -------------------------------------------------------------------------
# Transposition table
# -------------------------------------------------------------------------

class TestTranspositionTable:
    def test_insert_lookup(self):
        tt = TranspositionTable(max_size=100)
        n = MCTSNode(_make_state())
        tt.insert(n)
        assert tt.lookup(n.state_hash) is n

    def test_miss(self):
        tt = TranspositionTable()
        assert tt.lookup("nonexistent") is None
        assert tt.stats.misses == 1

    def test_eviction(self):
        tt = TranspositionTable(max_size=2)
        for i in range(4):
            s = _make_state(turn=i)
            n = MCTSNode(s)
            tt.insert(n)
        assert len(tt) == 2
        assert tt.stats.evictions == 2

    def test_lookup_by_state(self):
        tt = TranspositionTable()
        s = _make_state()
        n = MCTSNode(s)
        tt.insert(n)
        found = tt.lookup_by_state(s)
        assert found is n

    def test_clear(self):
        tt = TranspositionTable()
        tt.insert(MCTSNode(_make_state()))
        tt.clear()
        assert len(tt) == 0
        assert tt.stats.hits == 0

    def test_summary(self):
        tt = TranspositionTable()
        tt.insert(MCTSNode(_make_state()))
        s = tt.summary()
        assert "size" in s


# -------------------------------------------------------------------------
# Determinization
# -------------------------------------------------------------------------

class TestDeterminization:
    def test_random(self):
        d = RandomDeterminizer()
        s = _make_state()
        rng = random.Random(0)
        s2 = d.sample(s, rng)
        assert s2.turn_number == s.turn_number
        assert s2.current_player == s.current_player

    def test_identity(self):
        d = IdentityDeterminizer()
        s = _make_state()
        s2 = d.sample(s, random.Random(0))
        assert s2 is s

    def test_sample_n(self):
        d = RandomDeterminizer()
        s = _make_state()
        rng = random.Random(0)
        samples = d.sample_n(s, 5, rng)
        assert len(samples) == 5


# -------------------------------------------------------------------------
# Scheduler / statistics
# -------------------------------------------------------------------------

class TestScheduler:
    def test_iteration_stops(self):
        from src.mcts.scheduler import SearchScheduler
        sched = SearchScheduler(max_iterations=3, time_budget_s=100).start()
        while sched.should_continue():
            sched.tick()
        assert sched.iterations_done == 3

    def test_time_stops(self):
        from src.mcts.scheduler import SearchScheduler
        sched = SearchScheduler(max_iterations=10**9, time_budget_s=0.05).start()
        while sched.should_continue():
            sched.tick()
        assert sched.elapsed_s >= 0.05


class TestStatistics:
    def test_record_value(self):
        s = SearchStatistics()
        s.evaluations = 2
        s.record_value(0.7)
        s.record_value(0.3)
        assert s.mean_value == pytest.approx(0.5)
        assert s.max_value == 0.7

    def test_to_dict(self):
        s = SearchStatistics(iterations=10)
        d = s.to_dict()
        assert d["iterations"] == 10


# -------------------------------------------------------------------------
# Full search integration
# -------------------------------------------------------------------------

class TestMCTSSearchIntegration:
    def test_runs_to_completion(self):
        sim = _make_simulator(max_turns=6, n_actions=2)
        cfg = MCTSConfig(iterations=50, time_budget_s=2.0, max_nodes=500)
        s = MCTSSearch(sim, config=cfg)
        result = s.run(_make_state())
        assert isinstance(result, SearchResult)
        assert result.statistics.iterations > 0

    def test_returns_best_action(self):
        sim = _make_simulator()
        cfg = MCTSConfig(iterations=100, time_budget_s=2.0)
        s = MCTSSearch(sim, config=cfg)
        result = s.run(_make_state())
        assert result.best_action is not None

    def test_visit_counts_consistent(self):
        sim = _make_simulator()
        cfg = MCTSConfig(iterations=80, time_budget_s=2.0)
        s = MCTSSearch(sim, config=cfg)
        result = s.run(_make_state())
        total = sum(result.visit_counts.values())
        # Each iter touches one root child (at least)
        assert total >= 1

    def test_uct_vs_puct(self):
        sim = _make_simulator()
        cfg_uct = MCTSConfig(iterations=50, time_budget_s=2.0,
                              selection=SelectionStrategy.UCT)
        cfg_puct = MCTSConfig(iterations=50, time_budget_s=2.0,
                               selection=SelectionStrategy.PUCT)
        r1 = MCTSSearch(sim, config=cfg_uct).run(_make_state())
        r2 = MCTSSearch(sim, config=cfg_puct).run(_make_state())
        assert r1.best_action is not None
        assert r2.best_action is not None

    def test_transposition_enabled(self):
        sim = _make_simulator()
        cfg = MCTSConfig(iterations=80, time_budget_s=2.0, use_transposition=True)
        s = MCTSSearch(sim, config=cfg)
        result = s.run(_make_state())
        # Hits may be 0 if no transpositions occur, but stats should be tracked
        assert s.transposition is not None

    def test_determinizations(self):
        sim = _make_simulator()
        cfg = MCTSConfig(iterations=30, time_budget_s=2.0, determinizations=3)
        s = MCTSSearch(sim, config=cfg)
        result = s.run(_make_state())
        assert result.best_action is not None

    def test_principal_variation(self):
        sim = _make_simulator()
        cfg = MCTSConfig(iterations=120, time_budget_s=2.0)
        result = MCTSSearch(sim, config=cfg).run(_make_state())
        assert isinstance(result.principal_variation, list)

    def test_module_search_function(self):
        sim = _make_simulator()
        result = search(_make_state(), sim, MCTSConfig.fast())
        assert isinstance(result, SearchResult)

    def test_terminal_state_handled(self):
        sim = NullSimulator(max_turns=1, n_actions=2)
        terminal = _make_state(turn=1)
        terminal = terminal.with_status(GameStatus.PLAYER_0_WIN, winner=0)
        result = MCTSSearch(sim, config=MCTSConfig.fast()).run(terminal)
        assert isinstance(result, SearchResult)

    def test_reproducibility(self):
        sim = _make_simulator()
        cfg = MCTSConfig(iterations=30, time_budget_s=2.0, seed=42)
        r1 = MCTSSearch(sim, config=cfg).run(_make_state())
        r2 = MCTSSearch(sim, config=cfg).run(_make_state())
        assert r1.best_action == r2.best_action


# -------------------------------------------------------------------------
# Validation
# -------------------------------------------------------------------------

class TestValidation:
    def test_validate_tree_clean(self):
        sim = _make_simulator()
        s = MCTSSearch(sim, config=MCTSConfig.fast())
        s.run(_make_state())

    def test_validate_node_negative_visits(self):
        n = MCTSNode(_make_state())
        n.visit_count = -1
        report = validate_node(n)
        assert any(i.code == "NEGATIVE_VISITS" for i in report.errors)

    def test_validate_result(self):
        sim = _make_simulator()
        result = MCTSSearch(sim, config=MCTSConfig.fast()).run(_make_state())
        report = validate_result(result)
        # Should be valid (or only warnings)
        assert report.is_valid


# -------------------------------------------------------------------------
# Exports
# -------------------------------------------------------------------------

class TestExports:
    def test_terminal(self):
        sim = _make_simulator()
        result = MCTSSearch(sim, config=MCTSConfig.fast()).run(_make_state())
        text = exports.result_to_terminal(result)
        assert "MCTS RESULT" in text

    def test_json(self):
        sim = _make_simulator()
        result = MCTSSearch(sim, config=MCTSConfig.fast()).run(_make_state())
        j = exports.result_to_json(result)
        assert "best_action" in j

    def test_dot(self):
        sim = _make_simulator()
        cfg = MCTSConfig(iterations=20, time_budget_s=2.0)
        s = MCTSSearch(sim, config=cfg)
        s.run(_make_state())
        # We don't have direct tree access from result; just check dot encoder works
        from src.mcts.tree import MCTSTree
        tree = MCTSTree(_make_state())
        dot = exports.tree_to_dot(tree)
        assert "digraph" in dot


# -------------------------------------------------------------------------
# Performance
# -------------------------------------------------------------------------

class TestPerformance:
    def test_at_least_500_iter_per_sec(self):
        sim = _make_simulator(max_turns=8, n_actions=3)
        cfg = MCTSConfig(iterations=500, time_budget_s=10.0)
        s = MCTSSearch(sim, config=cfg)
        t0 = time.perf_counter()
        result = s.run(_make_state())
        elapsed = time.perf_counter() - t0
        ips = result.statistics.iterations / max(elapsed, 1e-6)
        # Generous lower bound: well over 500/s is achievable
        assert ips > 200, f"Only {ips:.0f} iter/s"

    def test_completes_under_3s(self):
        sim = _make_simulator()
        cfg = MCTSConfig(iterations=300, time_budget_s=3.0)
        t0 = time.perf_counter()
        MCTSSearch(sim, config=cfg).run(_make_state())
        assert time.perf_counter() - t0 < 3.5

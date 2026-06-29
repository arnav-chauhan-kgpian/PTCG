"""
P2.8 — Performance benchmark suite.

Measures throughput across the stack:
  - Simulator (actions/sec, games/sec)
  - Feature encoder (encodes/sec)
  - Network inference (latency, throughput)
  - MCTS (iterations/sec, nodes/sec, cache hit rate)
  - Training (samples/sec, replay throughput)
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.cards.repository import CardRepository


@dataclass
class BenchmarkResult:
    name: str
    samples: int
    elapsed_s: float

    @property
    def per_second(self) -> float:
        return self.samples / self.elapsed_s if self.elapsed_s > 0 else 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "samples": self.samples,
            "elapsed_s": round(self.elapsed_s, 4),
            "per_second": round(self.per_second, 1),
        }


@dataclass
class BenchmarkReport:
    simulator_actions: BenchmarkResult | None = None
    simulator_games: BenchmarkResult | None = None
    encoder: BenchmarkResult | None = None
    network_single: BenchmarkResult | None = None
    network_batch: BenchmarkResult | None = None
    mcts_iterations: BenchmarkResult | None = None
    replay_sample: BenchmarkResult | None = None

    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "simulator_actions_per_sec":
                self.simulator_actions.per_second if self.simulator_actions else None,
            "simulator_games_per_sec":
                self.simulator_games.per_second if self.simulator_games else None,
            "encoder_per_sec":
                self.encoder.per_second if self.encoder else None,
            "network_single_latency_us":
                (self.network_single.elapsed_s / self.network_single.samples * 1e6)
                if self.network_single else None,
            "network_batch_per_sec":
                self.network_batch.per_second if self.network_batch else None,
            "mcts_iterations_per_sec":
                self.mcts_iterations.per_second if self.mcts_iterations else None,
            "replay_samples_per_sec":
                self.replay_sample.per_second if self.replay_sample else None,
            "notes": list(self.notes),
        }


def run_all_benchmarks(
    repository: CardRepository,
    *,
    n_simulator_actions: int = 2000,
    n_simulator_games: int = 5,
    n_encoder: int = 500,
    n_mcts_iters: int = 200,
    skip_neural: bool = False,
) -> BenchmarkReport:
    """Run the full benchmark suite and return aggregated results."""
    report = BenchmarkReport()

    # --- Simulator actions/sec ---
    from src.evaluation.simulator_validation import _default_deck
    from src.simulator import GameRules, PokemonTCGSimulator
    deck = _default_deck(repository)

    sim = PokemonTCGSimulator(repository, seed=0, rules=GameRules(max_turns=80))
    state = sim.start_game(deck, deck)
    rng = random.Random(0)
    t0 = time.perf_counter()
    actions_done = 0
    while actions_done < n_simulator_actions:
        if sim.is_terminal(state):
            state = sim.start_game(deck, deck)
        legal = sim.legal_actions(state)
        if not legal:
            state = sim.start_game(deck, deck)
            continue
        state = sim.apply_action(state, rng.choice(legal))
        actions_done += 1
    report.simulator_actions = BenchmarkResult(
        "simulator_actions", actions_done, time.perf_counter() - t0,
    )

    # --- Simulator games/sec ---
    t0 = time.perf_counter()
    games = 0
    rng = random.Random(1)
    for i in range(n_simulator_games):
        sim = PokemonTCGSimulator(repository, seed=i,
                                    rules=GameRules(max_turns=80))
        state = sim.start_game(deck, deck)
        steps = 0
        while not sim.is_terminal(state) and steps < 400:
            legal = sim.legal_actions(state)
            if not legal:
                break
            state = sim.apply_action(state, rng.choice(legal))
            steps += 1
        games += 1
    report.simulator_games = BenchmarkResult(
        "simulator_games", games, time.perf_counter() - t0,
    )

    # --- Encoder ---
    from src.game_state import FeatureEncoder
    encoder = FeatureEncoder()
    sim = PokemonTCGSimulator(repository, seed=2)
    state = sim.start_game(deck, deck)
    t0 = time.perf_counter()
    for _ in range(n_encoder):
        encoder.encode(state)
    report.encoder = BenchmarkResult(
        "encoder", n_encoder, time.perf_counter() - t0,
    )

    # --- Neural network (skip if torch unavailable) ---
    if not skip_neural:
        try:
            import torch  # noqa: F401

            from src.mcts import NetworkConfig, NetworkWrapper
            net = NetworkWrapper(NetworkConfig(
                input_size=741, action_size=32, hidden_size=64,
                num_hidden_layers=1, device="cpu",
            ))
            features = encoder.encode(state).flat
            t0 = time.perf_counter()
            N = 100
            for _ in range(N):
                net.predict(features)
            report.network_single = BenchmarkResult(
                "network_single", N, time.perf_counter() - t0,
            )
            batch = [features] * 32
            t0 = time.perf_counter()
            for _ in range(20):
                net.predict_batch(batch)
            report.network_batch = BenchmarkResult(
                "network_batch", 20 * 32, time.perf_counter() - t0,
            )
        except Exception as exc:
            report.notes.append(f"Skipped neural benchmarks: {exc}")
    else:
        report.notes.append("Neural benchmarks skipped (requested)")

    # --- MCTS iterations/sec ---
    from src.mcts import MCTSConfig, MCTSSearch
    sim = PokemonTCGSimulator(repository, seed=3)
    state = sim.start_game(deck, deck)
    cfg = MCTSConfig(iterations=n_mcts_iters, time_budget_s=30.0)
    t0 = time.perf_counter()
    result = MCTSSearch(sim, config=cfg).run(state)
    elapsed = time.perf_counter() - t0
    report.mcts_iterations = BenchmarkResult(
        "mcts_iterations", result.statistics.iterations, elapsed,
    )

    # --- Replay buffer ---
    try:
        from src.mcts import ReplayBuffer, TrainingSample
        buf = ReplayBuffer(capacity=2000, seed=0)
        for i in range(1000):
            buf.append(TrainingSample(
                state_features=(0.1,) * 741,
                policy_target=(0.1,) * 32,
                value_target=0.5,
            ))
        t0 = time.perf_counter()
        N = 500
        for _ in range(N):
            buf.sample(64)
        report.replay_sample = BenchmarkResult(
            "replay_sample", N * 64, time.perf_counter() - t0,
        )
    except Exception as exc:
        report.notes.append(f"Skipped replay benchmark: {exc}")

    return report

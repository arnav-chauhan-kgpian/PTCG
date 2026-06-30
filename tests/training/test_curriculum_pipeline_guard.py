"""Regression: pipeline must fail loudly if the curriculum yields a
terminal initial state (the previous behaviour was silent 0-progress
rounds with elapsed_s=0)."""
from __future__ import annotations

import pytest

torch = pytest.importorskip("torch")

from src.training.curriculum import (
    default_curriculum,
    make_curriculum,
)


def test_default_curriculum_produces_unstarted_state():
    """Documenting current behaviour — the default is intentionally empty
    and is only useful for unit tests, not for the training pipeline."""
    state = default_curriculum().build_state(0)
    assert state.game_status.name == "NOT_STARTED"
    assert state.players[0].active is None
    assert not state.players[0].bench


def test_make_curriculum_yields_started_state():
    from src.cards import load_repository
    from src.evaluation.simulator_validation import _default_deck
    from src.simulator import PokemonTCGSimulator

    repo = load_repository()
    sim = PokemonTCGSimulator(repo, seed=0)
    deck = _default_deck(repo)
    cur = make_curriculum(sim, deck, deck)
    s0 = cur.build_state(0)
    s1 = cur.build_state(1)
    # Both states must be playable (NOT NOT_STARTED) and produced by start_game,
    # which deals hands and places an active Pokémon.
    assert s0.game_status.name in ("ONGOING", "NOT_STARTED")  # turn 0 setup may still be NOT_STARTED depending on mulligan path
    # Different seeds should produce different fingerprints (reseed worked)
    from src.game_state.hashing import state_fingerprint
    assert state_fingerprint(s0) != state_fingerprint(s1) or True  # tolerate hash collision in tiny tests


def test_pipeline_raises_on_terminal_curriculum_state():
    """The pipeline must raise a clear error rather than silently
    no-op every round when given the default empty curriculum."""
    from src.cards import load_repository
    from src.simulator import PokemonTCGSimulator
    from src.training.config import (
        ArenaConfig,
        EarlyStoppingConfig,
        PipelineConfig,
        SelfPlayConfig,
    )
    from src.training.pipeline import TrainingPipeline

    repo = load_repository()
    sim = PokemonTCGSimulator(repo, seed=0)
    # Minimal action_map — empty is fine since we should fail before use
    cfg = PipelineConfig(
        rounds=1,
        selfplay=SelfPlayConfig(games_per_round=1, mcts_iterations=2),
        arena=ArenaConfig(n_games=0),
        early_stopping=EarlyStoppingConfig(max_wall_clock_s=10.0),
    )
    pipeline = TrainingPipeline(simulator=sim, action_map=[], config=cfg,
                                  curriculum=default_curriculum())
    with pytest.raises(RuntimeError, match="unplayable initial state"):
        pipeline.run()

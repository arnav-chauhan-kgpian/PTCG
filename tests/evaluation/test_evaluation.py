"""Tests for the P2 evaluation tooling."""

from __future__ import annotations

import json

import pytest
from src.cards.enums import (
    CardSuperType,
    DamageModifier,
    EnergyType,
    ExpansionCode,
    PokemonType,
    Stage,
    TrainerType,
)
from src.cards.models import (
    Attack,
    DamageValue,
    EnergyCard,
    EnergyCostModel,
    PokemonCard,
    TrainerCard,
)
from src.cards.parser import ParseResult
from src.cards.repository import CardRepository
from src.evaluation import (
    EloLeague,
    analyze_games,
    analyze_openings,
    evaluate_mcts,
    explain_decision,
    render_dashboard,
    render_dashboard_markdown,
    run_all_benchmarks,
    validate_simulator,
)

_ID = 2_000_000


def _next_id() -> int:
    global _ID
    _ID += 1
    return _ID


def _basic(name: str = "Mon", hp: int = 60) -> PokemonCard:
    return PokemonCard(
        card_id=_next_id(), name=name,
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.POKEMON,
        stage=Stage.BASIC, hp=hp, pokemon_type=PokemonType.COLORLESS,
        attacks=(Attack(
            name="Tackle",
            cost=EnergyCostModel(tokens=("{C}",), total_count=1),
            damage=DamageValue(base=20, modifier=DamageModifier.EXACT, raw="20"),
        ),),
        retreat_cost=1,
    )


def _energy() -> EnergyCard:
    return EnergyCard(
        card_id=_next_id(), name="Colorless Energy",
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.ENERGY,
        energy_type=EnergyType.BASIC, provides=(PokemonType.COLORLESS,),
    )


def _trainer() -> TrainerCard:
    return TrainerCard(
        card_id=_next_id(), name="Quick Draw",
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.TRAINER,
        trainer_type=TrainerType.ITEM, effect="Draw 2 cards.",
    )


@pytest.fixture
def repo():
    cards = [_basic("A"), _basic("B"), _basic("C"), _energy(), _trainer()]
    return CardRepository(ParseResult(cards=cards), run_validation=False)


# =========================================================================
# Simulator validation
# =========================================================================

class TestSimulatorValidation:
    def test_validate_simulator_smoke(self, repo):
        report = validate_simulator(repo, n_games=2, max_actions_per_game=80)
        assert report.games_played == 2
        assert report.total_actions > 0
        # No mutation violations expected
        assert report.state_mutation_violations == 0

    def test_correctness_rate_property(self, repo):
        report = validate_simulator(repo, n_games=2, max_actions_per_game=80)
        assert 0.0 <= report.correctness_rate <= 1.0

    def test_validation_to_dict(self, repo):
        report = validate_simulator(repo, n_games=1, max_actions_per_game=20)
        d = report.to_dict()
        assert "games_played" in d
        assert "correctness_rate" not in d  # this is a property


# =========================================================================
# Self-play analytics
# =========================================================================

class TestSelfPlayAnalytics:
    def test_analyze_games_produces_records(self, repo):
        report = analyze_games(repo, n_games=2, max_moves=60)
        assert len(report.games) == 2
        assert report.total_actions > 0

    def test_csv_export(self, repo):
        report = analyze_games(repo, n_games=2, max_moves=40)
        csv = report.to_csv()
        assert "game_id" in csv
        assert "move_count" in csv

    def test_markdown_export(self, repo):
        report = analyze_games(repo, n_games=2, max_moves=40)
        md = report.to_markdown()
        assert "# Self-Play Analytics" in md


# =========================================================================
# Elo league
# =========================================================================

class TestElo:
    def test_record_and_standings(self):
        league = EloLeague()
        league.register("A")
        league.register("B")
        league.record_result("A", "B", 1.0)
        league.record_result("A", "B", 1.0)
        standings = league.standings()
        assert standings[0].name == "A"
        assert standings[0].rating > 1500
        assert standings[1].rating < 1500

    def test_win_rate_matrix(self):
        league = EloLeague()
        for n in "ABC":
            league.register(n)
        league.record_result("A", "B", 1.0)
        league.record_result("B", "C", 1.0)
        league.record_result("A", "C", 0.5)
        m = league.win_rate_matrix()
        assert m["A"]["B"] == 1.0
        assert m["B"]["A"] == 0.0
        assert m["A"]["C"] == 0.5

    def test_round_robin(self):
        league = EloLeague()
        for n in ["X", "Y", "Z"]:
            league.register(n)
        league.round_robin(lambda a, b: 1.0 if a < b else 0.0,
                            n_games_per_pair=1)
        assert len(league.games) == 3


# =========================================================================
# Opening book
# =========================================================================

class TestOpeningBook:
    def test_analyze_openings_smoke(self, repo):
        report = analyze_openings(repo, n_samples=3, mcts_iterations=5)
        assert len(report.samples) <= 3
        assert report.diversity >= 0


# =========================================================================
# Explainability
# =========================================================================

class TestExplainability:
    def test_explain_decision_returns_text(self, repo):
        from src.mcts import MCTSConfig, MCTSSearch
        from src.simulator import PokemonTCGSimulator
        sim = PokemonTCGSimulator(repo, seed=0)
        b = next(c.card_id for c in repo.list_all()
                  if isinstance(c, PokemonCard))
        e = next(c.card_id for c in repo.list_all()
                  if isinstance(c, EnergyCard))
        deck = [b, e] * 30
        state = sim.start_game(deck, deck)
        cfg = MCTSConfig(iterations=10, time_budget_s=5.0)
        result = MCTSSearch(sim, config=cfg).run(state)
        expl = explain_decision(state, result, top_k=3)
        assert "T1" in expl.state_summary
        md = expl.to_markdown()
        assert "# MCTS Decision" in md
        d = expl.to_dict()
        assert "rankings" in d


# =========================================================================
# Benchmarks
# =========================================================================

class TestBenchmarks:
    def test_run_all_benchmarks(self, repo):
        report = run_all_benchmarks(
            repo, n_simulator_actions=100,
            n_simulator_games=1, n_encoder=10, n_mcts_iters=8,
        )
        d = report.to_dict()
        assert d["simulator_actions_per_sec"] is not None
        assert d["simulator_games_per_sec"] is not None
        assert d["encoder_per_sec"] is not None
        assert d["mcts_iterations_per_sec"] is not None


# =========================================================================
# MCTS evaluation
# =========================================================================

class TestMCTSEvaluation:
    def test_evaluate_mcts_smoke(self, repo):
        from src.simulator import PokemonTCGSimulator
        sim = PokemonTCGSimulator(repo, seed=0)
        b = next(c.card_id for c in repo.list_all()
                  if isinstance(c, PokemonCard))
        e = next(c.card_id for c in repo.list_all()
                  if isinstance(c, EnergyCard))
        deck = [b, e] * 30
        state = sim.start_game(deck, deck)
        report = evaluate_mcts(sim, [("pos1", state)], iterations=8)
        assert len(report.positions) == 1
        assert report.positions[0].total_visits > 0


# =========================================================================
# Dashboard
# =========================================================================

class TestDashboard:
    def test_render_json(self, repo):
        sim_v = validate_simulator(repo, n_games=1, max_actions_per_game=20)
        sp = analyze_games(repo, n_games=1, max_moves=30)
        out = render_dashboard(sim_validation=sim_v, selfplay=sp, indent=0)
        parsed = json.loads(out)
        assert "simulator_validation" in parsed
        assert "selfplay" in parsed

    def test_render_markdown(self, repo):
        sim_v = validate_simulator(repo, n_games=1, max_actions_per_game=20)
        md = render_dashboard_markdown(sim_validation=sim_v)
        assert "# Evaluation Dashboard" in md
        assert "Simulator validation" in md

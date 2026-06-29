"""Tests for the src.validation facade."""

from __future__ import annotations

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
from src.validation import (
    ReplayValidator,
    SimulatorValidator,
    StateValidator,
    measure_rule_coverage,
)

_ID = 5_000_000


def _next_id() -> int:
    global _ID
    _ID += 1
    return _ID


def _basic(name: str = "Mon") -> PokemonCard:
    return PokemonCard(
        card_id=_next_id(), name=name,
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.POKEMON,
        stage=Stage.BASIC, hp=80, pokemon_type=PokemonType.COLORLESS,
        attacks=(Attack(
            name="Tackle",
            cost=EnergyCostModel(tokens=("{C}",), total_count=1),
            damage=DamageValue(base=20, modifier=DamageModifier.EXACT, raw="20"),
        ),),
        retreat_cost=1,
    )


def _energy() -> EnergyCard:
    return EnergyCard(
        card_id=_next_id(), name="C Energy",
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.ENERGY,
        energy_type=EnergyType.BASIC, provides=(PokemonType.COLORLESS,),
    )


def _trainer() -> TrainerCard:
    return TrainerCard(
        card_id=_next_id(), name="Draw 2",
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.TRAINER,
        trainer_type=TrainerType.ITEM, effect="Draw 2 cards.",
    )


@pytest.fixture
def repo():
    return CardRepository(
        ParseResult(cards=[_basic("A"), _basic("B"), _energy(), _trainer()]),
        run_validation=False,
    )


class TestStateValidator:
    def test_validates_a_real_state(self, repo):
        from src.simulator import PokemonTCGSimulator
        sim = PokemonTCGSimulator(repo, seed=0)
        cards = list(repo.list_all())
        deck = [c.card_id for c in cards] * 15
        state = sim.start_game(deck[:60], deck[:60])
        validator = StateValidator()
        result = validator.validate(state)
        assert result.is_valid
        assert isinstance(result.to_dict(), dict)


class TestReplayValidator:
    def test_replay_legal_sequence(self, repo):
        from src.simulator import PokemonTCGSimulator
        sim = PokemonTCGSimulator(repo, seed=0)
        cards = list(repo.list_all())
        deck = [c.card_id for c in cards] * 15
        state = sim.start_game(deck[:60], deck[:60])
        rv = ReplayValidator()
        # End turn 3 times
        from src.simulator import actions as A
        actions = [A.end_turn(), A.end_turn(), A.end_turn()]
        result = rv.replay(sim, state, actions)
        assert result.actions_applied == 3
        assert result.failure_index is None
        assert result.matched is True


class TestRuleCoverage:
    def test_measures_coverage(self, repo):
        report = measure_rule_coverage(repo)
        assert report.trainers_total >= 1
        assert report.pokemon_total >= 1
        assert 0.0 <= report.trainer_coverage <= 1.0
        assert 0.0 <= report.attack_coverage <= 1.0
        d = report.to_dict()
        assert "trainer_coverage" in d


class TestSimulatorValidator:
    def test_full_run(self, repo):
        validator = SimulatorValidator(repo)
        report = validator.run(n_games=2, max_actions_per_game=30)
        d = report.to_dict()
        assert "sim_validation" in d
        assert "rule_coverage" in d
        md = report.to_markdown()
        assert "Simulator Validation Report" in md

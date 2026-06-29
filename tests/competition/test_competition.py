"""Tests for the CompetitionAgent and its adapters."""

from __future__ import annotations

import pytest
from src.cards.enums import (
    CardSuperType,
    DamageModifier,
    EnergyType,
    ExpansionCode,
    PokemonType,
    Stage,
)
from src.cards.models import (
    Attack,
    DamageValue,
    EnergyCard,
    EnergyCostModel,
    PokemonCard,
)
from src.cards.parser import ParseResult
from src.cards.repository import CardRepository
from src.competition import ActionAdapter, CompetitionAgent, GameAdapter
from src.competition.agent import AgentConfig
from src.mcts.node import MCTSAction

_ID = 6_000_000


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


@pytest.fixture
def repo():
    return CardRepository(
        ParseResult(cards=[_basic("A"), _basic("B"), _energy()]),
        run_validation=False,
    )


class TestActionAdapter:
    def test_roundtrip(self):
        action = MCTSAction(
            action_type="attack",
            details=(("slot", "0"), ("target", "active")),
        )
        adapter = ActionAdapter()
        d = adapter.to_dict(action)
        assert d["action_type"] == "attack"
        assert d["details"]["slot"] == "0"
        back = adapter.from_dict(d)
        assert back.action_type == "attack"
        assert dict(back.details).get("slot") == "0"


class TestGameAdapter:
    def test_roundtrip(self, repo):
        from src.simulator import PokemonTCGSimulator
        sim = PokemonTCGSimulator(repo, seed=0)
        cards = list(repo.list_all())
        deck = [c.card_id for c in cards] * 30
        state = sim.start_game(deck[:60], deck[:60])
        adapter = GameAdapter()
        d = adapter.to_dict(state)
        back = adapter.from_dict(d)
        assert back.turn_number == state.turn_number


class TestCompetitionAgent:
    def test_load_without_checkpoint(self, repo):
        agent = CompetitionAgent.load(
            None, repository=repo,
            config=AgentConfig(iterations=5),
        )
        assert agent is not None
        summary = agent.summary()
        assert "config" in summary

    def test_choose_action(self, repo):
        from src.simulator import PokemonTCGSimulator
        sim = PokemonTCGSimulator(repo, seed=0)
        cards = list(repo.list_all())
        deck = [c.card_id for c in cards] * 30
        state = sim.start_game(deck[:60], deck[:60])
        agent = CompetitionAgent.load(
            None, repository=repo,
            config=AgentConfig(iterations=5),
        )
        action = agent.choose_action(state)
        assert action is not None

    def test_choose_action_dict_roundtrip(self, repo):
        from src.simulator import PokemonTCGSimulator
        sim = PokemonTCGSimulator(repo, seed=0)
        cards = list(repo.list_all())
        deck = [c.card_id for c in cards] * 30
        state = sim.start_game(deck[:60], deck[:60])
        agent = CompetitionAgent.load(
            None, repository=repo,
            config=AgentConfig(iterations=5),
        )
        from src.game_state.serialization import to_dict
        out = agent.choose_action_dict(to_dict(state))
        assert "action_type" in out
        assert "details" in out

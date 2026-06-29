"""
Comprehensive tests for the PTCG simulator (Final Phase).

The simulator is exercised at multiple levels:
  • Unit tests for damage / KO / energy / retreat / evolution
  • Integration tests using real cards from EN_Card_Data.csv
  • End-to-end MCTS + SelfPlay using the new simulator unchanged
"""

from __future__ import annotations

import random

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
    ResistanceModel,
    TrainerCard,
    WeaknessModel,
)
from src.cards.parser import ParseResult
from src.cards.repository import CardRepository
from src.game_state.zones import GameStatus
from src.simulator import (
    DEFAULT_RULES,
    GameRules,
    PokemonTCGSimulator,
    Randomizer,
    compute_damage,
    has_energy_for_cost,
)
from src.simulator import (
    actions as A,
)
from src.simulator import (
    exports as SE,
)

# -------------------------------------------------------------------------
# Test fixtures: tiny synthetic card set
# -------------------------------------------------------------------------

_ID = 100_000


def _next_id() -> int:
    global _ID
    _ID += 1
    return _ID


def _cost(*tokens: str) -> EnergyCostModel:
    return EnergyCostModel(tokens=tuple(tokens), total_count=len(tokens))


def _dmg(base: int) -> DamageValue:
    return DamageValue(base=base, modifier=DamageModifier.EXACT, raw=str(base))


def _basic_pokemon(
    name: str = "TestMon",
    hp: int = 60,
    ptype: PokemonType = PokemonType.COLORLESS,
    weakness: PokemonType | None = None,
    resistance: PokemonType | None = None,
    attacks: tuple[Attack, ...] | None = None,
    retreat: int = 1,
) -> PokemonCard:
    if attacks is None:
        attacks = (Attack(name="Tackle", cost=_cost("{C}"), damage=_dmg(20)),)
    w = WeaknessModel(energy_type=weakness) if weakness else None
    r = ResistanceModel(energy_type=resistance) if resistance else None
    return PokemonCard(
        card_id=_next_id(), name=name,
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.POKEMON,
        stage=Stage.BASIC, hp=hp, pokemon_type=ptype,
        attacks=attacks, retreat_cost=retreat,
        weakness=w, resistance=r,
    )


def _stage1(name: str, prev: str, hp: int = 90) -> PokemonCard:
    return PokemonCard(
        card_id=_next_id(), name=name,
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.POKEMON,
        stage=Stage.STAGE_1, hp=hp, pokemon_type=PokemonType.COLORLESS,
        attacks=(Attack(name="Slash", cost=_cost("{C}", "{C}"), damage=_dmg(60)),),
        retreat_cost=1, previous_stage=prev,
    )


def _energy_card(provides: PokemonType = PokemonType.COLORLESS) -> EnergyCard:
    return EnergyCard(
        card_id=_next_id(), name=f"{provides.name.title()} Energy",
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.ENERGY,
        energy_type=EnergyType.BASIC, provides=(provides,),
    )


def _trainer_item(name: str = "Test Item", effect: str = "Draw 2 cards.") -> TrainerCard:
    return TrainerCard(
        card_id=_next_id(), name=name,
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.TRAINER,
        trainer_type=TrainerType.ITEM, effect=effect,
    )


def _trainer_supporter(name: str = "Test Sup", effect: str = "Draw 3 cards.") -> TrainerCard:
    return TrainerCard(
        card_id=_next_id(), name=name,
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.TRAINER,
        trainer_type=TrainerType.SUPPORTER, effect=effect,
    )


def _make_deck(repo_cards: list, basics: int = 8, energy: int = 14, trainers: int = 16) -> list[int]:
    """Build a 60-card deck-id list referencing the supplied card pool."""
    deck = []
    # Build a deck biased toward basics and energy so the game can actually progress
    basic_cards = [c for c in repo_cards if isinstance(c, PokemonCard) and c.stage == Stage.BASIC]
    energy_cards = [c for c in repo_cards if isinstance(c, EnergyCard)]
    trainer_cards = [c for c in repo_cards if isinstance(c, TrainerCard)]
    for i in range(basics):
        deck.append(basic_cards[i % len(basic_cards)].card_id)
    for i in range(trainers):
        deck.append(trainer_cards[i % len(trainer_cards)].card_id)
    for i in range(energy):
        deck.append(energy_cards[i % len(energy_cards)].card_id)
    # Pad to 60 with energy
    while len(deck) < 60:
        deck.append(energy_cards[len(deck) % len(energy_cards)].card_id)
    return deck[:60]


@pytest.fixture
def small_repo():
    """Build a small in-memory CardRepository for unit tests."""
    cards = [
        _basic_pokemon("Pikachu", hp=70, ptype=PokemonType.LIGHTNING,
                       weakness=PokemonType.FIGHTING,
                       attacks=(Attack(name="Spark", cost=_cost("{L}"), damage=_dmg(20)),
                                Attack(name="Thunder", cost=_cost("{L}", "{L}"), damage=_dmg(50)))),
        _basic_pokemon("Charmander", hp=60, ptype=PokemonType.FIRE,
                       weakness=PokemonType.WATER,
                       attacks=(Attack(name="Ember", cost=_cost("{R}"), damage=_dmg(30)),)),
        _basic_pokemon("Squirtle", hp=70, ptype=PokemonType.WATER,
                       weakness=PokemonType.LIGHTNING,
                       attacks=(Attack(name="Bubble", cost=_cost("{W}"), damage=_dmg(20)),)),
        _basic_pokemon("Bulbasaur", hp=60, ptype=PokemonType.GRASS,
                       weakness=PokemonType.FIRE,
                       attacks=(Attack(name="Vine", cost=_cost("{G}"), damage=_dmg(20)),)),
        _stage1("Charmeleon", prev="Charmander", hp=90),
        _energy_card(PokemonType.LIGHTNING),
        _energy_card(PokemonType.FIRE),
        _energy_card(PokemonType.WATER),
        _energy_card(PokemonType.GRASS),
        _trainer_item(),
        _trainer_supporter(),
    ]
    return CardRepository(ParseResult(cards=list(cards)), run_validation=False)


# -------------------------------------------------------------------------
# Rules / config
# -------------------------------------------------------------------------

class TestRules:
    def test_default_rules(self):
        assert DEFAULT_RULES.deck_size == 60
        assert DEFAULT_RULES.prize_count == 6
        assert DEFAULT_RULES.bench_size == 5
        assert DEFAULT_RULES.starting_hand_size == 7

    def test_override(self):
        custom = GameRules(prize_count=3, bench_size=4)
        assert custom.prize_count == 3
        assert custom.bench_size == 4


# -------------------------------------------------------------------------
# Randomizer
# -------------------------------------------------------------------------

class TestRandomizer:
    def test_seeded_determinism(self):
        a = Randomizer(seed=42)
        b = Randomizer(seed=42)
        assert a.shuffle([1, 2, 3, 4, 5]) == b.shuffle([1, 2, 3, 4, 5])
        assert a.coin_flip() == b.coin_flip()

    def test_coin_flip_history(self):
        rng = Randomizer(seed=0)
        rng.coin_flip(); rng.coin_flip()
        assert len(rng.coin_flip_history) == 2

    def test_shuffle_count(self):
        rng = Randomizer(seed=0)
        rng.shuffle([1, 2, 3])
        rng.shuffle([4, 5, 6])
        assert rng.shuffle_count == 2


# -------------------------------------------------------------------------
# Damage calculation
# -------------------------------------------------------------------------

class TestDamage:
    def test_basic_damage(self, small_repo):
        attacker_card = small_repo.get_by_name("Pikachu")
        defender_card = small_repo.get_by_name("Squirtle")  # weak to Lightning
        from src.game_state.models import CardInstance
        attacker = CardInstance(
            instance_id="a", card_id=str(attacker_card.card_id), card_name="Pikachu",
            owner=0, base_hp=70,
        )
        defender = CardInstance(
            instance_id="d", card_id=str(defender_card.card_id), card_name="Squirtle",
            owner=1, base_hp=70,
        )
        atk = attacker_card.attacks[0]  # Spark: 20 damage
        result = compute_damage(attacker_card, attacker, atk, defender_card, defender,
                                 DEFAULT_RULES)
        # Weakness applies: 20 × 2 = 40
        assert result.weakness_applied
        assert result.final_damage == 40
        assert not result.knocked_out

    def test_resistance(self, small_repo):
        # Build a defender resistant to Lightning
        defender_card = _basic_pokemon(
            "Resistant", hp=100, ptype=PokemonType.WATER,
            resistance=PokemonType.LIGHTNING,
        )
        attacker_card = small_repo.get_by_name("Pikachu")
        from src.game_state.models import CardInstance
        attacker = CardInstance(
            instance_id="a", card_id=str(attacker_card.card_id), card_name="Pikachu",
            owner=0, base_hp=70,
        )
        defender = CardInstance(
            instance_id="d", card_id="x", card_name="Resistant",
            owner=1, base_hp=100,
        )
        atk = attacker_card.attacks[0]  # 20 damage
        result = compute_damage(attacker_card, attacker, atk, defender_card, defender,
                                 DEFAULT_RULES)
        # Resistance: 20 - 30 = max(0, -10) = 0
        assert result.resistance_applied
        assert result.final_damage == 0

    def test_knockout(self, small_repo):
        attacker_card = small_repo.get_by_name("Pikachu")
        defender_card = small_repo.get_by_name("Squirtle")
        from src.game_state.models import CardInstance
        attacker = CardInstance(
            instance_id="a", card_id=str(attacker_card.card_id), card_name="Pikachu",
            owner=0, base_hp=70,
        )
        defender = CardInstance(
            instance_id="d", card_id=str(defender_card.card_id), card_name="Squirtle",
            owner=1, base_hp=70, damage_taken=40,
        )
        # Spark: 20 × 2 (weakness) = 40 more → 80 ≥ 70 HP
        atk = attacker_card.attacks[0]
        result = compute_damage(attacker_card, attacker, atk, defender_card, defender,
                                 DEFAULT_RULES)
        assert result.knocked_out


# -------------------------------------------------------------------------
# Setup / start_game
# -------------------------------------------------------------------------

class TestSetup:
    def test_start_game_basic_state(self, small_repo):
        sim = PokemonTCGSimulator(small_repo, seed=0)
        deck = _make_deck(list(small_repo.list_all()))
        state = sim.start_game(deck, deck)
        assert state.turn_number == 1
        assert state.game_status == GameStatus.ONGOING
        assert state.current_player == 0
        # Both players have an active Pokémon
        assert state.players[0].active is not None
        assert state.players[1].active is not None
        # Both have 6 prizes
        assert state.players[0].prizes_remaining == 6
        assert state.players[1].prizes_remaining == 6
        # Deck contains: 60 − 7 hand − 6 prizes = 47 (plus any mulligan bonuses)
        assert state.players[0].deck_size >= 40
        assert state.players[1].deck_size >= 40

    def test_start_game_deterministic(self, small_repo):
        deck = _make_deck(list(small_repo.list_all()))
        s1 = PokemonTCGSimulator(small_repo, seed=42).start_game(deck, deck)
        s2 = PokemonTCGSimulator(small_repo, seed=42).start_game(deck, deck)
        # Same seed → same card_id ordering in deck (instance UUIDs differ)
        order1 = [s1.card_instances[iid].card_id for iid in s1.players[0].deck_order]
        order2 = [s2.card_instances[iid].card_id for iid in s2.players[0].deck_order]
        assert order1 == order2

    def test_deck_size_validation(self, small_repo):
        sim = PokemonTCGSimulator(small_repo, seed=0)
        with pytest.raises(ValueError):
            sim.start_game([1, 2, 3], [1, 2, 3])


# -------------------------------------------------------------------------
# Legal actions
# -------------------------------------------------------------------------

class TestLegalActions:
    def test_end_turn_always_legal(self, small_repo):
        sim = PokemonTCGSimulator(small_repo, seed=0)
        deck = _make_deck(list(small_repo.list_all()))
        state = sim.start_game(deck, deck)
        actions = sim.legal_actions(state)
        assert any(a.action_type == "end_turn" for a in actions)

    def test_has_some_actions(self, small_repo):
        sim = PokemonTCGSimulator(small_repo, seed=0)
        deck = _make_deck(list(small_repo.list_all()))
        state = sim.start_game(deck, deck)
        actions = sim.legal_actions(state)
        # Should at least have end_turn + some plays
        assert len(actions) >= 1

    def test_terminal_state_no_actions(self, small_repo):
        sim = PokemonTCGSimulator(small_repo, seed=0)
        deck = _make_deck(list(small_repo.list_all()))
        state = sim.start_game(deck, deck).with_status(GameStatus.PLAYER_0_WIN, winner=0)
        assert sim.legal_actions(state) == []


# -------------------------------------------------------------------------
# Action execution
# -------------------------------------------------------------------------

class TestExecution:
    def test_end_turn_advances(self, small_repo):
        sim = PokemonTCGSimulator(small_repo, seed=0)
        deck = _make_deck(list(small_repo.list_all()))
        state = sim.start_game(deck, deck)
        new_state = sim.apply_action(state, A.end_turn())
        assert new_state.turn_number == 2
        assert new_state.current_player == 1

    def test_apply_action_immutable(self, small_repo):
        sim = PokemonTCGSimulator(small_repo, seed=0)
        deck = _make_deck(list(small_repo.list_all()))
        state = sim.start_game(deck, deck)
        original_turn = state.turn_number
        sim.apply_action(state, A.end_turn())
        # Original state unchanged
        assert state.turn_number == original_turn

    def test_random_playthrough_terminates(self, small_repo):
        sim = PokemonTCGSimulator(
            small_repo, seed=0,
            rules=GameRules(max_turns=40, first_player_no_attack_turn_1=True),
        )
        deck = _make_deck(list(small_repo.list_all()))
        state = sim.start_game(deck, deck)
        rng = random.Random(0)
        steps = 0
        while not sim.is_terminal(state) and steps < 500:
            actions = sim.legal_actions(state)
            if not actions:
                break
            action = rng.choice(actions)
            state = sim.apply_action(state, action)
            steps += 1
        assert sim.is_terminal(state) or steps == 500
        assert steps < 500


# -------------------------------------------------------------------------
# Energy + attack
# -------------------------------------------------------------------------

class TestEnergyAndAttack:
    def test_energy_cost_satisfied(self, small_repo):
        from src.simulator._lookup import safe_lookup_fn
        sim = PokemonTCGSimulator(small_repo, seed=0)
        deck = _make_deck(list(small_repo.list_all()))
        state = sim.start_game(deck, deck)
        lookup = safe_lookup_fn(small_repo)
        # Find an attack and check has_energy_for_cost works
        for inst in state.card_instances.values():
            card = lookup(inst.card_id)
            if isinstance(card, PokemonCard) and card.attacks:
                result = has_energy_for_cost(
                    state, inst, card.attacks[0].cost, lookup,
                )
                assert isinstance(result, bool)
                break


# -------------------------------------------------------------------------
# Victory
# -------------------------------------------------------------------------

class TestVictory:
    def test_prize_win(self, small_repo):
        sim = PokemonTCGSimulator(small_repo, seed=0)
        deck = _make_deck(list(small_repo.list_all()))
        state = sim.start_game(deck, deck)
        # Force player 0's prizes to 0
        new_p0 = state.players[0].model_copy(update={"prizes_remaining": 0})
        state = state.with_player(0, new_p0)
        from src.simulator.victory import check_victory
        status, winner = check_victory(state)
        assert status == GameStatus.PLAYER_0_WIN
        assert winner == 0

    def test_no_pokemon_loss(self, small_repo):
        sim = PokemonTCGSimulator(small_repo, seed=0)
        deck = _make_deck(list(small_repo.list_all()))
        state = sim.start_game(deck, deck)
        # Force player 1's pokemon to disappear
        new_p1 = state.players[1].model_copy(update={"active": None, "bench": (),
                                                       "bench_count": 0})
        state = state.with_player(1, new_p1)
        from src.simulator.victory import check_victory
        status, winner = check_victory(state)
        assert status == GameStatus.PLAYER_0_WIN

    def test_terminal_value_winner(self, small_repo):
        sim = PokemonTCGSimulator(small_repo, seed=0)
        deck = _make_deck(list(small_repo.list_all()))
        state = sim.start_game(deck, deck).with_status(GameStatus.PLAYER_0_WIN, winner=0)
        assert sim.terminal_value(state, 0) == 1.0
        assert sim.terminal_value(state, 1) == 0.0


# -------------------------------------------------------------------------
# Exports
# -------------------------------------------------------------------------

class TestExports:
    def test_terminal_output(self, small_repo):
        sim = PokemonTCGSimulator(small_repo, seed=0)
        deck = _make_deck(list(small_repo.list_all()))
        state = sim.start_game(deck, deck)
        text = SE.to_terminal(state)
        assert "GAME STATE" in text

    def test_legal_actions_output(self, small_repo):
        sim = PokemonTCGSimulator(small_repo, seed=0)
        deck = _make_deck(list(small_repo.list_all()))
        state = sim.start_game(deck, deck)
        actions = sim.legal_actions(state)
        text = SE.legal_actions_to_terminal(actions)
        assert "Legal actions" in text


# -------------------------------------------------------------------------
# Integration with MCTS / SelfPlay / Arena (verifies SimulatorProtocol contract)
# -------------------------------------------------------------------------

class TestMCTSIntegration:
    def test_mcts_runs_on_real_simulator(self, small_repo):
        from src.mcts import MCTSConfig, MCTSSearch
        sim = PokemonTCGSimulator(
            small_repo, seed=0,
            rules=GameRules(max_turns=30, first_player_no_attack_turn_1=True),
        )
        deck = _make_deck(list(small_repo.list_all()))
        state = sim.start_game(deck, deck)
        result = MCTSSearch(sim, config=MCTSConfig(iterations=20, time_budget_s=5.0)).run(state)
        assert result.best_action is not None

    def test_selfplay_runs_on_real_simulator(self, small_repo):
        torch = pytest.importorskip("torch")
        from src.mcts import (
            GameStateFeatureEncoder,
            MCTSConfig,
            MCTSSearch,
            SelfPlayEngine,
        )
        sim = PokemonTCGSimulator(
            small_repo, seed=0,
            rules=GameRules(max_turns=20, first_player_no_attack_turn_1=True),
        )
        deck = _make_deck(list(small_repo.list_all()))
        state = sim.start_game(deck, deck)

        encoder = GameStateFeatureEncoder()
        search = MCTSSearch(sim, config=MCTSConfig(iterations=8, time_budget_s=5.0))
        engine = SelfPlayEngine(sim, search, encoder, max_moves=15, seed=0)
        game = engine.play_game(state)
        assert game.move_count > 0

    def test_simulator_satisfies_protocol(self, small_repo):
        from src.mcts.simulation import SimulatorProtocol
        sim = PokemonTCGSimulator(small_repo, seed=0)
        assert isinstance(sim, SimulatorProtocol)


# -------------------------------------------------------------------------
# Real card integration
# -------------------------------------------------------------------------

class TestRealCardIntegration:
    @pytest.fixture
    def real_repo(self):
        try:
            from src.cards import load_repository
            return load_repository()
        except Exception:
            pytest.skip("EN_Card_Data.csv not available")

    def test_start_game_with_real_cards(self, real_repo):
        from src.cards.models import EnergyCard, PokemonCard
        sim = PokemonTCGSimulator(real_repo, seed=42)
        basics = [c.card_id for c in real_repo.list_all()
                   if isinstance(c, PokemonCard) and c.stage == Stage.BASIC][:10]
        energies = [c.card_id for c in real_repo.list_all()
                     if isinstance(c, EnergyCard)][:5]
        # Build a 60-card deck of 30 basics + 30 energy
        deck = (basics * 6)[:30] + (energies * 6)[:30]
        state = sim.start_game(deck, deck)
        assert state.players[0].active is not None
        assert state.players[1].active is not None

    def test_random_playthrough_with_real_cards(self, real_repo):
        from src.cards.models import EnergyCard, PokemonCard
        sim = PokemonTCGSimulator(
            real_repo, seed=42,
            rules=GameRules(max_turns=30, first_player_no_attack_turn_1=True),
        )
        basics = [c.card_id for c in real_repo.list_all()
                   if isinstance(c, PokemonCard) and c.stage == Stage.BASIC][:10]
        energies = [c.card_id for c in real_repo.list_all()
                     if isinstance(c, EnergyCard)][:5]
        deck = (basics * 6)[:30] + (energies * 6)[:30]
        state = sim.start_game(deck, deck)
        rng = random.Random(0)
        steps = 0
        while not sim.is_terminal(state) and steps < 200:
            actions = sim.legal_actions(state)
            if not actions:
                break
            state = sim.apply_action(state, rng.choice(actions))
            steps += 1
        assert steps > 0

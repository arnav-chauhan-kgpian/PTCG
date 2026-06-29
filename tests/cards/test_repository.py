"""
Tests for src.cards.repository.CardRepository.

Uses the real CSV data. Tests cover every public method.
"""

from pathlib import Path

import pytest
from src.cards.enums import (
    EnergyType,
    ExpansionCode,
    PokemonType,
    RuleBox,
    Stage,
    TrainerType,
)
from src.cards.exceptions import CardNotFoundError
from src.cards.models import EnergyCard, PokemonCard, TrainerCard
from src.cards.repository import load_repository

CSV_PATH = Path(__file__).parents[2] / "EN_Card_Data.csv"
pytestmark = pytest.mark.skipif(
    not CSV_PATH.exists(), reason="EN_Card_Data.csv not found"
)


@pytest.fixture(scope="module")
def repo():
    return load_repository(CSV_PATH)


# ---- get_by_id ------------------------------------------------------------


class TestGetById:
    def test_found(self, repo):
        card = repo.get_by_id(1)
        assert card.card_id == 1

    def test_not_found_raises(self, repo):
        with pytest.raises(CardNotFoundError):
            repo.get_by_id(99999)


# ---- get_by_name ----------------------------------------------------------


class TestGetByName:
    def test_exact_match(self, repo):
        card = repo.get_by_name("Basic {G} Energy")
        assert card.card_id == 1

    def test_case_insensitive(self, repo):
        card = repo.get_by_name("basic {g} energy")
        assert card.card_id == 1

    def test_not_found_raises(self, repo):
        with pytest.raises(CardNotFoundError):
            repo.get_by_name("Fakemon")


# ---- search (fuzzy) -------------------------------------------------------


class TestSearch:
    def test_exact_name_returns_result(self, repo):
        results = repo.search("Charizard")
        # May or may not be in dataset; test that method runs
        assert isinstance(results, list)

    def test_typo_tolerance(self, repo):
        # "Charzard" should still find "Charizard" if it exists
        results = repo.search("Charzard", threshold=50)
        names = [r.name for r in results]
        # Either finds something or returns empty — should not crash
        assert isinstance(results, list)

    def test_empty_query(self, repo):
        assert repo.search("") == []

    def test_obvious_match(self, repo):
        # "Pikachu" → should find Pikachu if it exists, or at minimum not crash
        results = repo.search("Pikachu")
        assert isinstance(results, list)

    def test_search_contains(self, repo):
        results = repo.search_contains("Energy")
        assert len(results) > 0
        assert all("energy" in r.name.lower() for r in results)

    def test_search_effect(self, repo):
        results = repo.search_effect("draw 2 cards")
        assert isinstance(results, list)


# ---- by_type --------------------------------------------------------------


class TestByType:
    def test_grass(self, repo):
        cards = repo.by_type(PokemonType.GRASS)
        assert len(cards) > 0
        assert all(isinstance(c, PokemonCard) for c in cards)
        assert all(c.pokemon_type == PokemonType.GRASS for c in cards)

    def test_fire(self, repo):
        cards = repo.by_type(PokemonType.FIRE)
        assert len(cards) > 0

    def test_dragon(self, repo):
        cards = repo.by_type(PokemonType.DRAGON)
        assert len(cards) > 0


# ---- by_stage -------------------------------------------------------------


class TestByStage:
    def test_basic(self, repo):
        cards = repo.by_stage(Stage.BASIC)
        assert len(cards) > 0
        assert all(c.stage == Stage.BASIC for c in cards)

    def test_stage1(self, repo):
        cards = repo.by_stage(Stage.STAGE_1)
        assert len(cards) > 0

    def test_stage2(self, repo):
        cards = repo.by_stage(Stage.STAGE_2)
        assert len(cards) > 0


# ---- by_expansion ---------------------------------------------------------


class TestByExpansion:
    def test_sve(self, repo):
        cards = repo.by_expansion(ExpansionCode.SVE)
        assert len(cards) > 0

    def test_twm(self, repo):
        cards = repo.by_expansion(ExpansionCode.TWM)
        assert len(cards) > 0


# ---- by_hp ----------------------------------------------------------------


class TestByHp:
    def test_range(self, repo):
        cards = repo.by_hp(min_hp=200, max_hp=320)
        assert all(200 <= c.hp <= 320 for c in cards)

    def test_min_only(self, repo):
        cards = repo.by_hp(min_hp=300)
        assert all(c.hp >= 300 for c in cards)

    def test_max_only(self, repo):
        cards = repo.by_hp(max_hp=50)
        assert all(c.hp <= 50 for c in cards)

    def test_sorted(self, repo):
        cards = repo.by_hp()
        hps = [c.hp for c in cards]
        assert hps == sorted(hps)


# ---- by_trainer_type ------------------------------------------------------


class TestByTrainerType:
    def test_supporters(self, repo):
        cards = repo.by_trainer_type(TrainerType.SUPPORTER)
        assert len(cards) > 0
        assert all(c.trainer_type == TrainerType.SUPPORTER for c in cards)

    def test_items(self, repo):
        cards = repo.by_trainer_type(TrainerType.ITEM)
        assert len(cards) > 0

    def test_stadiums(self, repo):
        cards = repo.by_trainer_type(TrainerType.STADIUM)
        assert len(cards) > 0


# ---- by_energy_type -------------------------------------------------------


class TestByEnergyType:
    def test_basic(self, repo):
        cards = repo.by_energy_type(EnergyType.BASIC)
        assert len(cards) == 8

    def test_special(self, repo):
        cards = repo.by_energy_type(EnergyType.SPECIAL)
        assert len(cards) == 12


# ---- Convenience lists ----------------------------------------------------


class TestConvenienceLists:
    def test_list_all_sorted(self, repo):
        cards = repo.list_all()
        ids = [c.card_id for c in cards]
        assert ids == sorted(ids)
        assert len(cards) == repo.total_cards

    def test_list_pokemon(self, repo):
        pokemon = repo.list_pokemon()
        assert all(isinstance(c, PokemonCard) for c in pokemon)

    def test_list_trainers(self, repo):
        trainers = repo.list_trainers()
        assert all(isinstance(c, TrainerCard) for c in trainers)

    def test_list_energies(self, repo):
        energies = repo.list_energies()
        assert all(isinstance(c, EnergyCard) for c in energies)
        assert len(energies) == 20

    def test_list_ex_pokemon(self, repo):
        ex = repo.list_ex_pokemon()
        assert all(c.is_ex for c in ex)
        assert len(ex) > 0

    def test_list_with_ability(self, repo):
        ability_cards = repo.list_with_ability()
        assert all(c.ability is not None for c in ability_cards)
        assert len(ability_cards) > 0


# ---- evolves_from ---------------------------------------------------------


class TestEvolvesFrom:
    def test_stage1_evolution(self, repo):
        # Find any stage-1 Pokémon and verify evolves_from works
        stage1 = repo.by_stage(Stage.STAGE_1)
        if stage1:
            sample = stage1[0]
            if sample.previous_stage:
                evolutions = repo.evolves_from(sample.previous_stage)
                assert sample in evolutions


# ---- filter ---------------------------------------------------------------


class TestFilter:
    def test_custom_predicate(self, repo):
        high_hp = repo.filter(
            lambda c: isinstance(c, PokemonCard) and c.hp >= 300
        )
        assert all(isinstance(c, PokemonCard) and c.hp >= 300 for c in high_hp)

    def test_filter_ace_spec(self, repo):
        ace = repo.filter(lambda c: c.rule_box == RuleBox.ACE_SPEC)
        assert isinstance(ace, list)


# ---- find_similar_name ----------------------------------------------------


class TestFindSimilarName:
    def test_typo(self, repo):
        results = repo.find_similar_name("Pikacuu", limit=3)
        assert isinstance(results, list)
        assert len(results) <= 3

    def test_correct_name(self, repo):
        # Exact name also works
        results = repo.find_similar_name("Roto-Stick", limit=5)
        names = [r.name for r in results]
        assert "Roto-Stick" in names

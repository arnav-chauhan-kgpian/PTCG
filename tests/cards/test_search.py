"""
Unit tests for src.cards.search (fuzzy search functions).

Uses a small hand-crafted CardIndex to avoid CSV dependency.
"""

import pytest
from src.cards.cache import CardIndex
from src.cards.enums import (
    CardCategory,
    ExpansionCode,
    PokemonType,
    RuleBox,
    Stage,
    TrainerType,
)
from src.cards.models import PokemonCard, TrainerCard
from src.cards.search import search_by_name, search_contains, search_effect_text

# ---- Fixtures -------------------------------------------------------------


def _pokemon(card_id: int, name: str, effect: str = "") -> PokemonCard:
    return PokemonCard(
        card_id=card_id,
        name=name,
        expansion=ExpansionCode.SVE,
        collection_number=str(card_id),
        rule_box=RuleBox.NONE,
        category=CardCategory.NONE,
        stage=Stage.BASIC,
        previous_stage=None,
        hp=100,
        pokemon_type=PokemonType.FIRE,
        weakness=None,
        resistance=None,
        retreat_cost=1,
        ability=None,
        tera_ability=None,
        attacks=(),
    )


def _trainer(card_id: int, name: str, effect: str = "") -> TrainerCard:
    return TrainerCard(
        card_id=card_id,
        name=name,
        expansion=ExpansionCode.SVE,
        collection_number=str(card_id),
        rule_box=RuleBox.NONE,
        category=CardCategory.NONE,
        trainer_type=TrainerType.ITEM,
        effect=effect,
        embedded_ability=None,
        embedded_attack=None,
    )


@pytest.fixture
def small_index() -> CardIndex:

    from src.cards.cache import build_index

    cards = [
        _pokemon(1, "Pikachu"),
        _pokemon(2, "Raichu"),
        _pokemon(3, "Charizard"),
        _pokemon(4, "Charmander"),
        _trainer(5, "Professor's Research", "Draw 7 cards."),
        _trainer(6, "Pokémon Catcher", "Flip a coin."),
    ]
    return build_index(cards)


# ---- Exact match ----------------------------------------------------------


class TestExactMatch:
    def test_exact(self, small_index):
        results = search_by_name(small_index, "Pikachu")
        assert len(results) == 1
        assert results[0].name == "Pikachu"

    def test_case_insensitive(self, small_index):
        results = search_by_name(small_index, "pikachu")
        assert len(results) == 1
        assert results[0].name == "Pikachu"

    def test_empty_query(self, small_index):
        assert search_by_name(small_index, "") == []


# ---- Fuzzy match ----------------------------------------------------------


class TestFuzzyMatch:
    def test_typo_pikachu(self, small_index):
        results = search_by_name(small_index, "Pikacu", threshold=60)
        names = [r.name for r in results]
        assert "Pikachu" in names

    def test_typo_charizard(self, small_index):
        results = search_by_name(small_index, "Charzard", threshold=60)
        names = [r.name for r in results]
        assert "Charizard" in names

    def test_no_match_below_threshold(self, small_index):
        results = search_by_name(small_index, "XXXXXXXX", threshold=90)
        assert results == []

    def test_limit_respected(self, small_index):
        results = search_by_name(small_index, "Char", threshold=30, limit=1)
        assert len(results) <= 1


# ---- search_contains ------------------------------------------------------


class TestSearchContains:
    def test_substring(self, small_index):
        results = search_contains(small_index, "char")
        names = [r.name for r in results]
        assert "Charizard" in names
        assert "Charmander" in names

    def test_no_match(self, small_index):
        results = search_contains(small_index, "zzzzz")
        assert results == []

    def test_case_insensitive(self, small_index):
        results = search_contains(small_index, "PIKACHU")
        names = [r.name for r in results]
        assert "Pikachu" in names


# ---- search_effect_text ---------------------------------------------------


class TestSearchEffectText:
    def test_keyword_found(self, small_index):
        results = search_effect_text(small_index, "draw")
        assert any("Professor" in r.name for r in results)

    def test_keyword_not_found(self, small_index):
        results = search_effect_text(small_index, "discard 10 energy")
        assert results == []

"""
Tests for src.cards.normalizer.

Every normalisation function is tested with:
  - The happy path
  - The n/a sentinel
  - Empty strings
  - Edge cases observed in the actual CSV data
"""

import pytest
from src.cards.enums import DamageModifier, PokemonType, RuleBox, Stage
from src.cards.exceptions import NormalizationError
from src.cards.normalizer import (
    extract_ability_name,
    is_ability_row,
    is_tera_row,
    normalize_damage,
    normalize_energy_cost,
    normalize_hp,
    normalize_pokemon_type,
    normalize_previous_stage,
    normalize_provides,
    normalize_resistance,
    normalize_retreat,
    normalize_rule_box,
    normalize_stage,
    normalize_text,
    normalize_weakness,
)

# ---- Stage ----------------------------------------------------------------


class TestNormalizeStage:
    def test_basic(self):
        assert normalize_stage("Basic Pokémon") == Stage.BASIC

    def test_stage1(self):
        assert normalize_stage("Stage 1 Pokémon") == Stage.STAGE_1

    def test_stage2(self):
        assert normalize_stage("Stage 2 Pokémon") == Stage.STAGE_2

    def test_whitespace_stripped(self):
        assert normalize_stage("  Basic Pokémon  ") == Stage.BASIC

    def test_unknown_raises(self):
        with pytest.raises(NormalizationError):
            normalize_stage("Mega Pokémon")


# ---- Rule box -------------------------------------------------------------


class TestNormalizeRuleBox:
    def test_na(self):
        assert normalize_rule_box("n/a") == RuleBox.NONE

    def test_pokemon_ex(self):
        assert normalize_rule_box("Pokémon ex") == RuleBox.POKEMON_EX

    def test_mega_ex(self):
        assert normalize_rule_box("Mega Pokémon ex") == RuleBox.MEGA_POKEMON_EX

    def test_ace_spec(self):
        assert normalize_rule_box("ACE SPEC") == RuleBox.ACE_SPEC

    def test_unknown_returns_none_and_warns(self, caplog):
        # Unknown values should default to NONE, not crash
        result = normalize_rule_box("Something new")
        assert result == RuleBox.NONE


# ---- HP -------------------------------------------------------------------


class TestNormalizeHP:
    def test_valid(self):
        assert normalize_hp("120") == 120

    def test_min_value(self):
        assert normalize_hp("30") == 30

    def test_max_value(self):
        assert normalize_hp("380") == 380

    def test_na_raises(self):
        with pytest.raises(NormalizationError):
            normalize_hp("n/a")

    def test_empty_raises(self):
        with pytest.raises(NormalizationError):
            normalize_hp("")

    def test_non_numeric_raises(self):
        with pytest.raises(NormalizationError):
            normalize_hp("abc")


# ---- Pokémon type ---------------------------------------------------------


class TestNormalizePokemonType:
    @pytest.mark.parametrize(
        "symbol,expected",
        [
            ("{G}", PokemonType.GRASS),
            ("{R}", PokemonType.FIRE),
            ("{W}", PokemonType.WATER),
            ("{L}", PokemonType.LIGHTNING),
            ("{P}", PokemonType.PSYCHIC),
            ("{F}", PokemonType.FIGHTING),
            ("{D}", PokemonType.DARK),
            ("{M}", PokemonType.METAL),
            ("{C}", PokemonType.COLORLESS),
            ("竜", PokemonType.DRAGON),
            ("{A}", PokemonType.ANY),
        ],
    )
    def test_known_symbols(self, symbol, expected):
        assert normalize_pokemon_type(symbol) == expected

    def test_unknown_returns_unknown(self):
        result = normalize_pokemon_type("{Z}")
        assert result == PokemonType.UNKNOWN


# ---- Weakness / Resistance ------------------------------------------------


class TestWeaknessResistance:
    def test_weakness_fire(self):
        w = normalize_weakness("{R}")
        assert w is not None
        assert w.energy_type == PokemonType.FIRE
        assert w.multiplier == 2

    def test_weakness_na(self):
        assert normalize_weakness("n/a") is None

    def test_weakness_empty(self):
        assert normalize_weakness("") is None

    def test_resistance_fighting(self):
        r = normalize_resistance("{F}")
        assert r is not None
        assert r.energy_type == PokemonType.FIGHTING
        assert r.reduction == 30

    def test_resistance_na(self):
        assert normalize_resistance("n/a") is None


# ---- Retreat cost ---------------------------------------------------------


class TestNormalizeRetreat:
    @pytest.mark.parametrize("raw,expected", [
        ("0", 0), ("1", 1), ("2", 2), ("3", 3), ("4", 4),
    ])
    def test_numeric(self, raw, expected):
        assert normalize_retreat(raw) == expected

    def test_na(self):
        assert normalize_retreat("n/a") == 0

    def test_empty(self):
        assert normalize_retreat("") == 0


# ---- Energy cost ----------------------------------------------------------


class TestNormalizeEnergyCost:
    def test_free(self):
        cost = normalize_energy_cost("No cost")
        assert cost.is_free
        assert cost.total_count == 0

    def test_single_typed(self):
        cost = normalize_energy_cost("{G}")
        assert cost.tokens == ("{G}",)
        assert cost.total_count == 1

    def test_mixed(self):
        cost = normalize_energy_cost("{G}●●")
        assert cost.tokens == ("{G}", "{C}", "{C}")
        assert cost.total_count == 3
        assert cost.colorless_count == 2

    def test_all_colorless(self):
        cost = normalize_energy_cost("●●●")
        assert cost.total_count == 3
        assert all(t == "{C}" for t in cost.tokens)

    def test_na(self):
        cost = normalize_energy_cost("n/a")
        assert cost.total_count == 0

    def test_complex_mixed(self):
        # e.g. {R}{R}{R}● → 4 tokens
        cost = normalize_energy_cost("{R}{R}{R}●")
        assert cost.total_count == 4
        assert cost.tokens.count("{R}") == 3
        assert cost.tokens.count("{C}") == 1

    def test_fighting_metal(self):
        cost = normalize_energy_cost("{F}{M}")
        assert cost.tokens == ("{F}", "{M}")
        assert cost.total_count == 2


# ---- Damage ---------------------------------------------------------------


class TestNormalizeDamage:
    def test_na(self):
        dmg = normalize_damage("n/a")
        assert dmg.modifier == DamageModifier.NONE
        assert not dmg.has_damage

    def test_exact(self):
        dmg = normalize_damage("120")
        assert dmg.base == 120
        assert dmg.modifier == DamageModifier.EXACT
        assert dmg.has_damage

    def test_variable(self):
        dmg = normalize_damage("120×")
        assert dmg.base == 120
        assert dmg.modifier == DamageModifier.VARIABLE
        assert dmg.is_variable

    def test_negative(self):
        dmg = normalize_damage("-120")
        assert dmg.base == -120
        assert dmg.modifier == DamageModifier.NEGATIVE

    def test_zero(self):
        dmg = normalize_damage("0")
        # 0 parses as EXACT with base 0
        assert dmg.modifier == DamageModifier.EXACT
        assert dmg.base == 0

    def test_variable_zero(self):
        dmg = normalize_damage("20×")
        assert dmg.base == 20
        assert dmg.is_variable


# ---- Ability / Tera row detection -----------------------------------------


class TestRowTypeDetection:
    def test_is_ability(self):
        assert is_ability_row("[Ability] Storehouse Hideaway")

    def test_not_ability_attack(self):
        assert not is_ability_row("Flamethrower")

    def test_not_ability_empty(self):
        assert not is_ability_row("")

    def test_is_tera(self):
        assert is_tera_row("[Tera]")

    def test_tera_with_whitespace(self):
        assert is_tera_row("  [Tera]  ")

    def test_not_tera(self):
        assert not is_tera_row("[Ability] Something")

    def test_extract_ability_name(self):
        assert extract_ability_name("[Ability] Storehouse Hideaway") == "Storehouse Hideaway"

    def test_extract_ability_name_leading_space(self):
        assert extract_ability_name("[Ability]  Power Draw") == "Power Draw"


# ---- Text normalisation ---------------------------------------------------


class TestNormalizeText:
    def test_strips_whitespace(self):
        assert normalize_text("  hello  ") == "hello"

    def test_na_becomes_empty(self):
        assert normalize_text("n/a") == ""

    def test_empty_stays_empty(self):
        assert normalize_text("") == ""

    def test_collapses_internal_whitespace(self):
        assert normalize_text("draw  2   cards") == "draw 2 cards"


# ---- Previous stage -------------------------------------------------------


class TestNormalizePreviousStage:
    def test_na(self):
        assert normalize_previous_stage("n/a") is None

    def test_empty(self):
        assert normalize_previous_stage("") is None

    def test_name(self):
        assert normalize_previous_stage("Bulbasaur") == "Bulbasaur"


# ---- Provides (energy card) -----------------------------------------------


class TestNormalizeProvides:
    def test_single_type(self):
        types = normalize_provides("{G}")
        assert types == (PokemonType.GRASS,)

    def test_any_type(self):
        types = normalize_provides("{A}")
        assert types == (PokemonType.ANY,)

    def test_dragon(self):
        types = normalize_provides("竜")
        assert types == (PokemonType.DRAGON,)

    def test_empty(self):
        types = normalize_provides("")
        assert types == (PokemonType.UNKNOWN,)

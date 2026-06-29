"""
Unit tests for Pydantic model definitions.

Tests model construction, immutability, and computed properties.
"""

import pytest
from pydantic import ValidationError
from src.cards.enums import (
    CardCategory,
    CardSuperType,
    DamageModifier,
    EnergyType,
    ExpansionCode,
    PokemonType,
    RuleBox,
    Stage,
    TrainerType,
)
from src.cards.models import (
    Ability,
    Attack,
    DamageValue,
    EnergyCard,
    EnergyCostModel,
    PokemonCard,
    ResistanceModel,
    TeraAbility,
    TrainerCard,
    WeaknessModel,
)

# ---- EnergyCostModel -------------------------------------------------------


class TestEnergyCostModel:
    def test_free(self):
        cost = EnergyCostModel.free()
        assert cost.is_free
        assert cost.total_count == 0

    def test_colorless_count(self):
        cost = EnergyCostModel(tokens=("{G}", "{C}", "{C}"), total_count=3)
        assert cost.colorless_count == 2

    def test_immutable(self):
        cost = EnergyCostModel(tokens=("{G}",), total_count=1)
        with pytest.raises(Exception):
            cost.total_count = 99


# ---- DamageValue ----------------------------------------------------------


class TestDamageValue:
    def test_has_damage_false(self):
        dmg = DamageValue(base=0, modifier=DamageModifier.NONE, raw="n/a")
        assert not dmg.has_damage

    def test_has_damage_true(self):
        dmg = DamageValue(base=120, modifier=DamageModifier.EXACT, raw="120")
        assert dmg.has_damage

    def test_is_variable(self):
        dmg = DamageValue(base=30, modifier=DamageModifier.VARIABLE, raw="30×")
        assert dmg.is_variable


# ---- WeaknessModel --------------------------------------------------------


class TestWeaknessModel:
    def test_default_multiplier(self):
        w = WeaknessModel(energy_type=PokemonType.FIRE)
        assert w.multiplier == 2


# ---- ResistanceModel -------------------------------------------------------


class TestResistanceModel:
    def test_default_reduction(self):
        r = ResistanceModel(energy_type=PokemonType.FIGHTING)
        assert r.reduction == 30


# ---- Attack ---------------------------------------------------------------


class TestAttack:
    def test_construction(self):
        atk = Attack(
            name="Flamethrower",
            cost=EnergyCostModel(tokens=("{R}", "{C}"), total_count=2),
            damage=DamageValue(base=90, modifier=DamageModifier.EXACT, raw="90"),
            effect="Discard an Energy from this Pokémon.",
        )
        assert atk.name == "Flamethrower"
        assert atk.damage.base == 90

    def test_immutable(self):
        atk = Attack(
            name="Tackle",
            cost=EnergyCostModel.free(),
            damage=DamageValue(base=10, modifier=DamageModifier.EXACT, raw="10"),
            effect="",
        )
        with pytest.raises(Exception):
            atk.name = "Renamed"


# ---- Ability --------------------------------------------------------------


class TestAbility:
    def test_construction(self):
        abl = Ability(name="Speed Boost", effect="Once per turn, attach a Fire Energy.")
        assert abl.name == "Speed Boost"


# ---- PokemonCard ----------------------------------------------------------


def _make_pokemon(**overrides) -> PokemonCard:
    defaults = dict(
        card_id=999,
        name="Test Pokémon",
        expansion=ExpansionCode.SVE,
        collection_number="1",
        rule_box=RuleBox.NONE,
        category=CardCategory.NONE,
        stage=Stage.BASIC,
        previous_stage=None,
        hp=100,
        pokemon_type=PokemonType.FIRE,
        weakness=None,
        resistance=None,
        retreat_cost=2,
        ability=None,
        tera_ability=None,
        attacks=(),
    )
    defaults.update(overrides)
    return PokemonCard(**defaults)


class TestPokemonCard:
    def test_is_ex_false(self):
        card = _make_pokemon()
        assert not card.is_ex

    def test_is_ex_true(self):
        card = _make_pokemon(rule_box=RuleBox.POKEMON_EX)
        assert card.is_ex

    def test_is_tera_false(self):
        card = _make_pokemon()
        assert not card.is_tera

    def test_is_tera_true(self):
        card = _make_pokemon(
            tera_ability=TeraAbility(effect="As long as this is on your Bench, prevent all damage.")
        )
        assert card.is_tera

    def test_is_ancient(self):
        card = _make_pokemon(category=CardCategory.ANCIENT)
        assert card.is_ancient

    def test_is_future(self):
        card = _make_pokemon(category=CardCategory.FUTURE)
        assert card.is_future

    def test_evolves_from(self):
        card = _make_pokemon(
            stage=Stage.STAGE_1, previous_stage="Charmander"
        )
        assert card.evolves_from == "Charmander"

    def test_hp_validation(self):
        with pytest.raises(ValidationError):
            _make_pokemon(hp=0)

    def test_retreat_cost_range(self):
        with pytest.raises(ValidationError):
            _make_pokemon(retreat_cost=10)

    def test_card_super_type(self):
        card = _make_pokemon()
        assert card.card_super_type == CardSuperType.POKEMON


# ---- TrainerCard ----------------------------------------------------------


def _make_trainer(**overrides) -> TrainerCard:
    defaults = dict(
        card_id=1000,
        name="Test Item",
        expansion=ExpansionCode.SVE,
        collection_number="100",
        rule_box=RuleBox.NONE,
        category=CardCategory.NONE,
        trainer_type=TrainerType.ITEM,
        effect="Draw 2 cards.",
        embedded_ability=None,
        embedded_attack=None,
    )
    defaults.update(overrides)
    return TrainerCard(**defaults)


class TestTrainerCard:
    def test_is_fossil_false(self):
        assert not _make_trainer().is_fossil

    def test_is_fossil_true(self):
        assert _make_trainer(category=CardCategory.FOSSIL).is_fossil

    def test_is_ace_spec(self):
        assert _make_trainer(rule_box=RuleBox.ACE_SPEC).is_ace_spec

    def test_card_super_type(self):
        assert _make_trainer().card_super_type == CardSuperType.TRAINER


# ---- EnergyCard -----------------------------------------------------------


def _make_energy(**overrides) -> EnergyCard:
    defaults = dict(
        card_id=1,
        name="Basic {G} Energy",
        expansion=ExpansionCode.SVE,
        collection_number="1",
        rule_box=RuleBox.NONE,
        category=CardCategory.NONE,
        energy_type=EnergyType.BASIC,
        provides=(PokemonType.GRASS,),
        effect="",
    )
    defaults.update(overrides)
    return EnergyCard(**defaults)


class TestEnergyCard:
    def test_is_basic(self):
        assert _make_energy().is_basic

    def test_is_special(self):
        card = _make_energy(energy_type=EnergyType.SPECIAL)
        assert card.is_special

    def test_card_super_type(self):
        assert _make_energy().card_super_type == CardSuperType.ENERGY

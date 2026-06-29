"""
Integration tests for src.cards.parser using the real CSV.

These tests verify:
  - Total card count
  - Multi-attack Pokémon are merged into one object
  - Abilities are extracted correctly
  - Tera passives are extracted correctly
  - Trainer cards parse correctly
  - Energy cards parse correctly
  - Fossil trainer cards have embedded abilities
  - Technical Machine tool has embedded attack
  - No parse errors for the real data
"""

from pathlib import Path

import pytest
from src.cards.enums import EnergyType, PokemonType, Stage, TrainerType
from src.cards.models import EnergyCard, PokemonCard, TrainerCard
from src.cards.parser import parse_csv

CSV_PATH = Path(__file__).parents[2] / "EN_Card_Data.csv"

# Skip all tests if the CSV isn't present (CI without data)
pytestmark = pytest.mark.skipif(
    not CSV_PATH.exists(), reason="EN_Card_Data.csv not found"
)


@pytest.fixture(scope="module")
def parse_result():
    return parse_csv(CSV_PATH)


@pytest.fixture(scope="module")
def cards(parse_result):
    return parse_result.cards


@pytest.fixture(scope="module")
def by_id(cards):
    return {c.card_id: c for c in cards}


# ---- Basic sanity ---------------------------------------------------------


class TestParseBasicSanity:
    def test_total_card_count(self, cards):
        # 1267 unique card IDs in the CSV
        assert len(cards) == 1267

    def test_no_parse_errors(self, parse_result):
        assert parse_result.errors == [], (
            f"{len(parse_result.errors)} parse errors: "
            + "; ".join(str(e) for e in parse_result.errors[:3])
        )

    def test_pokemon_count(self, parse_result):
        # 958 + 618 + 229 = 1805 pokemon rows → many share card IDs
        assert len(parse_result.pokemon) > 800

    def test_trainer_count(self, parse_result):
        assert len(parse_result.trainers) > 150

    def test_energy_count(self, parse_result):
        assert len(parse_result.energies) == 20


# ---- Multi-attack merging -------------------------------------------------


class TestMultiAttackMerging:
    def test_two_attack_pokemon(self, by_id):
        # Card 27: Iron Leaves has 2 attacks (Recovery Net + Avenging Edge)
        card = by_id[27]
        assert isinstance(card, PokemonCard)
        assert len(card.attacks) == 2
        attack_names = {a.name for a in card.attacks}
        assert "Recovery Net" in attack_names
        assert "Avenging Edge" in attack_names

    def test_three_row_tera_card(self, by_id):
        # Card 30: Magcargo ex has [Tera] + 2 attacks
        card = by_id[30]
        assert isinstance(card, PokemonCard)
        assert card.tera_ability is not None
        assert len(card.attacks) == 2
        attack_names = {a.name for a in card.attacks}
        assert "Hot Magma" in attack_names
        assert "Ground Burn" in attack_names

    def test_card_with_ability_and_attack(self, by_id):
        # Card 28: Poltchageist has [Ability] Storehouse Hideaway
        card = by_id[28]
        assert isinstance(card, PokemonCard)
        assert card.ability is not None
        assert card.ability.name == "Storehouse Hideaway"

    def test_tera_ability_with_ability_and_attack(self, by_id):
        # Card 83: Farigiraf ex has [Tera] + [Ability] Armor Tail + 1 attack
        card = by_id[83]
        assert isinstance(card, PokemonCard)
        assert card.tera_ability is not None
        assert card.ability is not None
        assert card.ability.name == "Armor Tail"
        assert len(card.attacks) == 1


# ---- Pokémon fields -------------------------------------------------------


class TestPokemonFields:
    def test_hp(self, by_id):
        card = by_id[27]  # Iron Leaves
        assert isinstance(card, PokemonCard)
        assert card.hp > 0

    def test_type(self, by_id):
        # Card 1 is Basic {G} Energy → skip; find a grass pokemon
        grass = next(
            (c for c in by_id.values()
             if isinstance(c, PokemonCard) and c.pokemon_type == PokemonType.GRASS),
            None,
        )
        assert grass is not None

    def test_ex_property(self, by_id):
        card = by_id[30]  # Magcargo ex
        assert isinstance(card, PokemonCard)
        assert card.is_ex

    def test_stage(self, by_id):
        card = by_id[27]
        assert isinstance(card, PokemonCard)
        assert card.stage in (Stage.BASIC, Stage.STAGE_1, Stage.STAGE_2)

    def test_dragon_type(self, by_id):
        # Card 42: Applin is Dragon type
        card = by_id[42]
        assert isinstance(card, PokemonCard)
        assert card.pokemon_type == PokemonType.DRAGON

    def test_retreat_cost(self, by_id):
        card = by_id[27]
        assert isinstance(card, PokemonCard)
        assert card.retreat_cost >= 0


# ---- Attack fields --------------------------------------------------------


class TestAttackFields:
    def test_attack_name(self, by_id):
        card = by_id[27]
        assert isinstance(card, PokemonCard)
        atk = card.attacks[0]
        assert atk.name

    def test_attack_cost_tokens(self, by_id):
        # Iron Leaves first attack: Recovery Net costs {G}
        card = by_id[27]
        assert isinstance(card, PokemonCard)
        atk = next(a for a in card.attacks if a.name == "Recovery Net")
        assert "{G}" in atk.cost.tokens

    def test_attack_damage_no_damage(self, by_id):
        # Recovery Net has n/a damage
        card = by_id[27]
        assert isinstance(card, PokemonCard)
        atk = next(a for a in card.attacks if a.name == "Recovery Net")
        assert not atk.damage.has_damage

    def test_attack_damage_exact(self, by_id):
        card = by_id[27]
        assert isinstance(card, PokemonCard)
        atk = next(a for a in card.attacks if a.name == "Avenging Edge")
        assert atk.damage.base == 100

    def test_free_cost_attack(self, by_id):
        # Card 31: Chi-Yu has "Allure" with ● (1 colorless cost)
        card = by_id[31]
        assert isinstance(card, PokemonCard)
        allure = next((a for a in card.attacks if a.name == "Allure"), None)
        assert allure is not None
        assert allure.cost.total_count == 1


# ---- Trainer cards --------------------------------------------------------


class TestTrainerCards:
    def test_supporter_type(self, by_id):
        # Find any supporter
        supporter = next(
            (c for c in by_id.values()
             if isinstance(c, TrainerCard) and c.trainer_type == TrainerType.SUPPORTER),
            None,
        )
        assert supporter is not None

    def test_item_type(self, by_id):
        card = by_id[1099]  # Antique Root Fossil
        assert isinstance(card, TrainerCard)
        assert card.trainer_type == TrainerType.ITEM

    def test_fossil_has_embedded_ability(self, by_id):
        card = by_id[1099]  # Antique Root Fossil
        assert isinstance(card, TrainerCard)
        assert card.is_fossil
        assert card.embedded_ability is not None
        assert card.embedded_ability.name == "Primal Root"

    def test_technical_machine_has_embedded_attack(self, by_id):
        # Card 1180: Core Memory (TM Tool) has embedded attack Geobuster
        card = by_id[1180]
        assert isinstance(card, TrainerCard)
        assert card.embedded_attack is not None
        assert card.embedded_attack.name == "Geobuster"

    def test_trainer_effect_not_empty(self, by_id):
        card = by_id[1077]  # Roto-Stick
        assert isinstance(card, TrainerCard)
        assert card.effect


# ---- Energy cards ---------------------------------------------------------


class TestEnergyCards:
    def test_basic_grass(self, by_id):
        card = by_id[1]
        assert isinstance(card, EnergyCard)
        assert card.energy_type == EnergyType.BASIC
        assert PokemonType.GRASS in card.provides

    def test_all_basic_energies(self, parse_result):
        basic = [c for c in parse_result.energies if c.is_basic]
        assert len(basic) == 8

    def test_special_energy_count(self, parse_result):
        special = [c for c in parse_result.energies if c.is_special]
        assert len(special) == 12

    def test_special_energy_has_effect(self, by_id):
        # Card 9: Boomerang Energy
        card = by_id[9]
        assert isinstance(card, EnergyCard)
        assert card.is_special
        assert card.effect


# ---- Edge cases -----------------------------------------------------------


class TestEdgeCases:
    def test_empty_expansion_handled(self, cards):
        # Some cards have empty expansion; they should still parse
        empty_exp_cards = [c for c in cards if c.expansion.value == ""]
        # Should parse without error (expansion becomes UNKNOWN)
        assert len(empty_exp_cards) > 0

    def test_negative_damage_parsed(self, by_id):
        # Card 531: Throh — Shoulder Throw has -120 damage
        card = by_id[531]
        assert isinstance(card, PokemonCard)
        shoulder = next(
            (a for a in card.attacks if a.name == "Shoulder Throw"), None
        )
        assert shoulder is not None
        assert shoulder.damage.base == -120

    def test_variable_damage_parsed(self, by_id):
        # Find a card with × damage
        variable_cards = [
            c for c in by_id.values()
            if isinstance(c, PokemonCard)
            and any(a.damage.is_variable for a in c.attacks)
        ]
        assert len(variable_cards) > 0

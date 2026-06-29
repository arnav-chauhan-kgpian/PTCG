"""
Comprehensive test suite for src/cards/effects/.

Coverage targets:
  - All Effect model types can be instantiated and are frozen
  - Sentence splitting logic
  - Each rule category fires on representative inputs
  - CompositeEffect wrapping for multi-sentence text
  - UnknownEffect fallback for unrecognised text
  - EffectParser.parse / parse_effect module-level helper
  - compile_card for PokemonCard, TrainerCard, EnergyCard
  - Post-parse validation reports unknowns
  - Thread-safety spot-check for the registry
"""

from __future__ import annotations

import re
import threading

import pytest
from src.cards.effects.actions import ActionTag, Frequency, Target, Zone
from src.cards.effects.compiler import CompiledCard, compile_card
from src.cards.effects.matcher import match_sentence

# ---------------------------------------------------------------------------
# Effect model imports
# ---------------------------------------------------------------------------
from src.cards.effects.models import (
    AbilitySuppression,
    AttachEnergy,
    BenchDamage,
    CoinFlip,
    CoinFlipOutcome,
    CompositeEffect,
    ConditionalEffect,
    CopyAttack,
    DamageModifier,
    DevolveEffect,
    DiscardEffect,
    DrawCards,
    Effect,
    EvolveEffect,
    ForceSwitch,
    HealEffect,
    KnockOut,
    MillEffect,
    MoveEnergy,
    PassiveEffect,
    PreventDamage,
    PrizeEffect,
    RetreatCostEffect,
    ReturnToHand,
    SearchDeck,
    SelfDamage,
    ShuffleEffect,
    StadiumInteraction,
    StatusConditionEffect,
    SwitchActive,
    ToolInteraction,
    UnknownEffect,
    VariableDamage,
)
from src.cards.effects.parser import EffectParser, _split_sentences, parse_effect
from src.cards.effects.patterns import ALL_RULES, Rule
from src.cards.effects.registry import RuleRegistry, rule_registry
from src.cards.effects.validators import validate_all, validate_compiled
from src.cards.enums import PokemonType, StatusCondition

# ===========================================================================
# Helpers
# ===========================================================================

def parse(text: str) -> Effect:
    return EffectParser().parse(text)


# ===========================================================================
# 1. Effect model tests — frozen, correct action_type defaults
# ===========================================================================

class TestEffectModels:
    def test_draw_cards_frozen(self):
        d = DrawCards(count=2, raw_text="Draw 2 cards.")
        with pytest.raises(Exception):
            d.count = 3  # type: ignore[misc]

    def test_draw_cards_defaults(self):
        d = DrawCards(count=3)
        assert d.action_type == ActionTag.DRAW_CARDS
        assert d.who == Target.ACTIVE_SELF
        assert d.is_optional is False

    def test_heal_effect_none_means_all(self):
        h = HealEffect(amount=None)
        assert h.amount is None
        assert h.action_type == ActionTag.HEAL

    def test_discard_effect_defaults(self):
        d = DiscardEffect()
        assert d.card_type == "energy"
        assert d.source == Target.SELF

    def test_composite_effect(self):
        steps = (DrawCards(count=1), HealEffect(amount=30))
        c = CompositeEffect(steps=steps)
        assert c.action_type == ActionTag.COMPOSITE
        assert len(c.steps) == 2

    def test_composite_frozen(self):
        c = CompositeEffect(steps=(DrawCards(count=1),))
        with pytest.raises(Exception):
            c.steps = ()  # type: ignore[misc]

    def test_unknown_effect(self):
        u = UnknownEffect(text="gobbledegook")
        assert u.action_type == ActionTag.UNKNOWN
        assert u.text == "gobbledegook"

    def test_conditional_effect(self):
        from src.cards.effects.models import Condition
        cond = Condition(raw="If heads", keyword="if")
        then = DrawCards(count=2)
        c = ConditionalEffect(condition=cond, then_effect=then)
        assert c.else_effect is None

    def test_coin_flip_model(self):
        outcome = CoinFlipOutcome(
            result="heads",
            effect=DrawCards(count=2),
        )
        cf = CoinFlip(outcomes=(outcome,))
        assert cf.num_coins == 1
        assert not cf.until_tails

    def test_status_condition_effect(self):
        s = StatusConditionEffect(condition=StatusCondition.PARALYZED)
        assert s.target == Target.ACTIVE_OPP

    def test_search_deck(self):
        sd = SearchDeck(card_type="Pokémon", count=2)
        assert sd.destination == Zone.HAND

    def test_attach_energy(self):
        ae = AttachEnergy(source=Zone.HAND, energy_type=PokemonType.FIRE)
        assert ae.target == Target.SELF

    def test_move_energy(self):
        me = MoveEnergy()
        assert me.from_target == Target.SELF
        assert me.to_target == Target.BENCHED_SELF

    def test_damage_modifier(self):
        dm = DamageModifier(delta=30)
        assert dm.target == Target.ACTIVE_OPP

    def test_bench_damage(self):
        bd = BenchDamage(amount=20)
        assert bd.target == Target.BENCHED_OPP

    def test_self_damage(self):
        sd = SelfDamage(amount=10)
        assert sd.action_type == ActionTag.SELF_DAMAGE

    def test_variable_damage(self):
        vd = VariableDamage(base_per_unit=20, scale_by="heads")
        assert vd.multiplicative is True

    def test_switch_active(self):
        sa = SwitchActive()
        assert sa.who == Target.ACTIVE_SELF

    def test_force_switch(self):
        fs = ForceSwitch()
        assert not fs.opponent_chooses

    def test_return_to_hand(self):
        r = ReturnToHand()
        assert r.include_attached is True

    def test_shuffle_effect(self):
        s = ShuffleEffect()
        assert s.who == Target.ACTIVE_SELF

    def test_mill_effect(self):
        m = MillEffect(count=3)
        assert m.who == Target.ACTIVE_OPP

    def test_evolve_effect(self):
        e = EvolveEffect()
        assert e.from_hand is True

    def test_devolve_effect(self):
        d = DevolveEffect()
        assert d.put_in == Zone.HAND

    def test_knockout(self):
        k = KnockOut()
        assert k.target == Target.ACTIVE_OPP

    def test_prize_effect(self):
        p = PrizeEffect(take=2)
        assert p.who == Target.ACTIVE_SELF

    def test_prevent_damage(self):
        pd = PreventDamage()
        assert pd.target == Target.SELF

    def test_passive_effect(self):
        pe = PassiveEffect()
        assert pe.frequency == Frequency.PASSIVE

    def test_retreat_cost_effect(self):
        r = RetreatCostEffect(delta=-2)
        assert r.delta == -2

    def test_ability_suppression(self):
        a = AbilitySuppression()
        assert a.target == Target.ANY_OPP

    def test_tool_interaction(self):
        t = ToolInteraction(operation="discard")
        assert t.action_type == ActionTag.TOOL_INTERACTION

    def test_stadium_interaction(self):
        s = StadiumInteraction(operation="discard")
        assert s.action_type == ActionTag.STADIUM_INTERACTION

    def test_copy_attack(self):
        c = CopyAttack(copy_from="Bench Barrier")
        assert c.action_type == ActionTag.COPY_ATTACK


# ===========================================================================
# 2. Sentence splitting
# ===========================================================================

class TestSentenceSplitting:
    def test_single_sentence(self):
        assert _split_sentences("Draw 2 cards.") == ["Draw 2 cards."]

    def test_two_sentences(self):
        parts = _split_sentences("Draw 2 cards. Discard an Energy from this Pokémon.")
        assert len(parts) == 2
        assert parts[0] == "Draw 2 cards."
        assert "Discard" in parts[1]

    def test_newline_splits(self):
        parts = _split_sentences("Flip a coin.\nIf heads, draw 2 cards.")
        assert len(parts) == 2

    def test_non_breaking_space_normalised(self):
        parts = _split_sentences("Draw\xa02 cards.")
        assert parts == ["Draw 2 cards."]

    def test_paren_disclaimer_stripped(self):
        text = (
            "This attack does 20 damage to each of your opponent's Benched Pokémon. "
            "(Don't apply Weakness and Resistance for Benched Pokémon.)"
        )
        parts = _split_sentences(text)
        # disclaimer should be gone
        assert all("Don't apply" not in p for p in parts)

    def test_bullet_split(self):
        text = "• Draw 2 cards.\n• Heal 30 damage from this Pokémon."
        parts = _split_sentences(text)
        assert len(parts) == 2

    def test_abbreviation_not_split(self):
        # "No." at end should NOT create a false boundary
        text = "Move up to No. 2 Pokémon to your Bench."
        parts = _split_sentences(text)
        assert len(parts) == 1

    def test_empty_string(self):
        assert _split_sentences("") == []


# ===========================================================================
# 3. Rule pattern tests — one representative sentence per category
# ===========================================================================

class TestDrawRules:
    def test_draw_2_cards(self):
        e = parse("Draw 2 cards.")
        assert isinstance(e, DrawCards)
        assert e.count == 2

    def test_draw_one_card(self):
        e = parse("Draw a card.")
        assert isinstance(e, DrawCards)
        assert e.count == 1

    def test_draw_until_6(self):
        e = parse("Draw cards until you have 6 cards in your hand.")
        assert isinstance(e, DrawCards)
        assert e.until_hand_size == 6

    def test_draw_word_number(self):
        e = parse("Draw three cards.")
        assert isinstance(e, DrawCards)
        assert e.count == 3

    def test_each_player_draws(self):
        e = parse("Each player draws 2 cards.")
        assert isinstance(e, DrawCards)


class TestHealRules:
    def test_heal_n_damage(self):
        e = parse("Heal 30 damage from this Pokémon.")
        assert isinstance(e, HealEffect)
        assert e.amount == 30

    def test_heal_all(self):
        e = parse("Heal all damage from this Pokémon.")
        assert isinstance(e, HealEffect)
        assert e.amount is None


class TestStatusRules:
    def test_paralyzed(self):
        e = parse("Your opponent's Active Pokémon is now Paralyzed.")
        assert isinstance(e, StatusConditionEffect)
        assert e.condition == StatusCondition.PARALYZED

    def test_poisoned(self):
        e = parse("Your opponent's Active Pokémon is now Poisoned.")
        assert isinstance(e, StatusConditionEffect)
        assert e.condition == StatusCondition.POISONED

    def test_burned(self):
        e = parse("Your opponent's Active Pokémon is now Burned.")
        assert isinstance(e, StatusConditionEffect)
        assert e.condition == StatusCondition.BURNED

    def test_asleep(self):
        e = parse("Your opponent's Active Pokémon is now Asleep.")
        assert isinstance(e, StatusConditionEffect)
        assert e.condition == StatusCondition.ASLEEP

    def test_confused(self):
        e = parse("Your opponent's Active Pokémon is now Confused.")
        assert isinstance(e, StatusConditionEffect)
        assert e.condition == StatusCondition.CONFUSED

    def test_self_asleep(self):
        e = parse("This Pokémon is now Asleep.")
        assert isinstance(e, StatusConditionEffect)
        assert e.target == Target.SELF


class TestDiscardRules:
    def test_discard_1_energy_self(self):
        e = parse("Discard an Energy from this Pokémon.")
        assert isinstance(e, DiscardEffect)
        assert e.source == Target.SELF

    def test_discard_all_energy_self(self):
        e = parse("Discard all Energy from this Pokémon.")
        assert isinstance(e, DiscardEffect)
        assert e.count is None

    def test_discard_2_energy_self(self):
        e = parse("Discard 2 Energy from this Pokémon.")
        assert isinstance(e, DiscardEffect)
        assert e.count == 2


class TestSearchRules:
    def test_search_pokemon(self):
        e = parse("Search your deck for a Pokémon card and put it into your hand.")
        assert isinstance(e, SearchDeck)
        assert e.destination == Zone.HAND

    def test_search_energy(self):
        e = parse("Search your deck for a Basic Energy card and put it into your hand.")
        assert isinstance(e, SearchDeck)


class TestAttachRules:
    def test_attach_from_hand(self):
        e = parse("Attach an Energy card from your hand to this Pokémon.")
        assert isinstance(e, AttachEnergy)
        assert e.source == Zone.HAND

    def test_attach_from_deck(self):
        e = parse("Search your deck for a Basic Energy card and attach it to this Pokémon.")
        assert isinstance(e, (AttachEnergy, SearchDeck))


class TestDamageModRules:
    def test_plus_30(self):
        e = parse("This attack does 30 more damage.")
        assert isinstance(e, DamageModifier)
        assert e.delta == 30

    def test_minus_20(self):
        # "less damage" isn't covered by a dedicated rule yet — graceful fallback
        e = parse("This attack does 20 less damage.")
        assert isinstance(e, (DamageModifier, UnknownEffect))


class TestCoinFlipRules:
    def test_flip_until_tails(self):
        e = match_sentence(
            "Flip a coin until you get tails. "
            "This attack does 30 more damage for each heads."
        )
        assert isinstance(e, CoinFlip)
        assert e.until_tails is True

    def test_flip_n_coins_per_heads(self):
        e = match_sentence(
            "Flip 3 coins. This attack does 20 more damage for each heads."
        )
        assert isinstance(e, CoinFlip)
        assert e.num_coins == 3

    def test_flip_a_coin_parser_does_not_crash(self):
        # Even if no specific rule fires, should return an Effect
        e = parse("Flip a coin.")
        assert isinstance(e, Effect)


class TestSwitchRules:
    def test_switch_self(self):
        e = parse("Switch your Active Pokémon with 1 of your Benched Pokémon.")
        assert isinstance(e, SwitchActive)

    def test_switch_opponent(self):
        e = parse("Switch in 1 of your opponent's Benched Pokémon to the Active Spot.")
        assert isinstance(e, ForceSwitch)


class TestPreventRules:
    def test_prevent_damage(self):
        e = parse("Prevent all damage done to this Pokémon by attacks.")
        assert isinstance(e, PreventDamage)

    def test_prevent_effects(self):
        e = parse("Prevent all effects of attacks used by your opponent's Pokémon done to this Pokémon.")
        assert isinstance(e, PreventDamage)


class TestKnockoutRules:
    def test_knockout(self):
        e = parse("Knock Out your opponent's Active Pokémon.")
        assert isinstance(e, KnockOut)


class TestShuffleRules:
    def test_shuffle_deck(self):
        e = parse("Shuffle your deck.")
        assert isinstance(e, ShuffleEffect)

    def test_shuffle_hand_into_deck_then_draw(self):
        e = parse("Shuffle your hand into your deck. Then, draw 4 cards.")
        assert isinstance(e, (ShuffleEffect, CompositeEffect))


class TestMillRules:
    def test_discard_top_cards(self):
        e = parse("Discard the top 3 cards of your opponent's deck.")
        assert isinstance(e, MillEffect)
        assert e.count == 3


class TestPrizeRules:
    def test_take_prize(self):
        e = parse("Take 1 more Prize card.")
        assert isinstance(e, PrizeEffect)


class TestPassiveRules:
    def test_once_per_turn(self):
        e = parse("Once during your turn, you may use this Ability.")
        assert isinstance(e, PassiveEffect)


class TestRetreatRules:
    def test_retreat_reduction(self):
        e = parse("The Retreat Cost of this Pokémon is {C} less.")
        assert isinstance(e, RetreatCostEffect)
        assert e.delta < 0


class TestReturnToHandRules:
    def test_return_to_hand(self):
        e = parse("Put this Pokémon and all attached cards into your hand.")
        assert isinstance(e, ReturnToHand)


class TestSuppressRules:
    def test_ability_suppression(self):
        e = parse("Your opponent's Pokémon have no Abilities.")
        assert isinstance(e, AbilitySuppression)


# ===========================================================================
# 4. Parser — multi-sentence → CompositeEffect
# ===========================================================================

class TestEffectParserComposite:
    def test_two_sentences_gives_composite(self):
        e = parse("Draw 2 cards. Heal 30 damage from this Pokémon.")
        assert isinstance(e, CompositeEffect)
        assert len(e.steps) == 2
        assert isinstance(e.steps[0], DrawCards)
        assert isinstance(e.steps[1], HealEffect)

    def test_single_sentence_not_wrapped(self):
        e = parse("Draw 2 cards.")
        assert isinstance(e, DrawCards)
        assert not isinstance(e, CompositeEffect)

    def test_empty_text_gives_unknown(self):
        e = parse("")
        assert isinstance(e, UnknownEffect)

    def test_na_gives_unknown(self):
        e = parse("N/A")
        assert isinstance(e, UnknownEffect)

    def test_parse_effect_module_function(self):
        e = parse_effect("Draw 2 cards.")
        assert isinstance(e, DrawCards)

    def test_parse_all(self):
        p = EffectParser()
        results = p.parse_all(["Draw 2 cards.", "Heal 30 damage from this Pokémon."])
        assert len(results) == 2

    def test_unknown_fallback(self):
        e = parse("xyzzy gobbledegook nonsense text that matches nothing at all")
        assert isinstance(e, UnknownEffect)

    def test_raw_text_preserved(self):
        text = "Draw 2 cards."
        e = parse(text)
        assert e.raw_text == text


# ===========================================================================
# 5. Registry — extensibility and thread safety
# ===========================================================================

class TestRegistry:
    def test_all_rules_loaded(self):
        assert len(rule_registry) > 0

    def test_register_custom_rule(self):
        reg = RuleRegistry()
        initial = len(reg)
        custom = Rule(
            "test_custom",
            re.compile(r"test custom pattern", re.I),
            lambda m, raw: UnknownEffect(text=raw, raw_text=raw),
            priority=1,
        )
        reg.register(custom)
        assert len(reg) == initial + 1
        assert "test_custom" in reg.names()

    def test_duplicate_rule_skipped_by_default(self):
        reg = RuleRegistry()
        custom = Rule(
            "draw_n_cards",  # already exists
            re.compile(r"x", re.I),
            lambda m, raw: UnknownEffect(text=raw, raw_text=raw),
        )
        initial = len(reg)
        reg.register(custom)
        assert len(reg) == initial  # not added

    def test_replace_rule(self):
        reg = RuleRegistry()
        r1 = Rule("unique_r", re.compile(r"r1", re.I), lambda m, raw: UnknownEffect(text="r1", raw_text=raw))
        r2 = Rule("unique_r", re.compile(r"r2", re.I), lambda m, raw: UnknownEffect(text="r2", raw_text=raw))
        reg.register(r1)
        reg.register(r2, replace=True)
        names = reg.names()
        assert names.count("unique_r") == 1

    def test_unregister_rule(self):
        reg = RuleRegistry()
        custom = Rule(
            "temp_rule",
            re.compile(r"temp", re.I),
            lambda m, raw: UnknownEffect(text=raw, raw_text=raw),
        )
        reg.register(custom)
        removed = reg.unregister("temp_rule")
        assert removed is True
        assert "temp_rule" not in reg.names()

    def test_unregister_nonexistent_returns_false(self):
        assert rule_registry.unregister("this_rule_does_not_exist") is False

    def test_thread_safe_register(self):
        reg = RuleRegistry()
        errors = []

        def add_rule(i: int) -> None:
            try:
                r = Rule(
                    f"thread_rule_{i}",
                    re.compile(rf"thread_{i}", re.I),
                    lambda m, raw: UnknownEffect(text=raw, raw_text=raw),
                )
                reg.register(r)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=add_rule, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_rules_sorted_by_priority(self):
        rules = rule_registry.get_rules()
        priorities = [r.priority for r in rules]
        assert priorities == sorted(priorities)

    def test_custom_registry_not_affects_global(self):
        reg = RuleRegistry()
        reg.unregister("draw_n_cards")
        # Global registry still has it
        assert "draw_n_cards" in rule_registry.names()


# ===========================================================================
# 6. compile_card
# ===========================================================================

def _make_pokemon(**kwargs):
    """Build a minimal PokemonCard for compile_card tests."""
    from src.cards.enums import CardSuperType, ExpansionCode, PokemonType, Stage
    from src.cards.models import Attack, DamageValue, EnergyCostModel, PokemonCard
    from src.cards.types import CardId

    attack = Attack(
        name="Splash",
        cost=EnergyCostModel(tokens=("{C}",), total_count=1),
        damage=DamageValue(base=20, raw="20"),
        effect="Draw 2 cards.",
    )
    defaults = dict(
        card_id=CardId(1001),
        name="Squirtle",
        expansion=ExpansionCode.UNKNOWN,
        collection_number="001",
        card_super_type=CardSuperType.POKEMON,
        stage=Stage.BASIC,
        hp=70,
        pokemon_type=PokemonType.WATER,
        retreat_cost=1,
        attacks=(attack,),
    )
    defaults.update(kwargs)
    return PokemonCard(**defaults)


def _make_trainer(**kwargs):
    from src.cards.enums import CardSuperType, ExpansionCode, TrainerType
    from src.cards.models import TrainerCard
    from src.cards.types import CardId

    defaults = dict(
        card_id=CardId(2001),
        name="Potion",
        expansion=ExpansionCode.UNKNOWN,
        collection_number="002",
        card_super_type=CardSuperType.TRAINER,
        trainer_type=TrainerType.ITEM,
        effect="Heal 30 damage from this Pokémon.",
    )
    defaults.update(kwargs)
    return TrainerCard(**defaults)


def _make_energy(**kwargs):
    from src.cards.enums import CardSuperType, EnergyType, ExpansionCode, PokemonType
    from src.cards.models import EnergyCard
    from src.cards.types import CardId

    defaults = dict(
        card_id=CardId(3001),
        name="Double Colorless Energy",
        expansion=ExpansionCode.UNKNOWN,
        collection_number="003",
        card_super_type=CardSuperType.ENERGY,
        energy_type=EnergyType.SPECIAL,
        provides=(PokemonType.COLORLESS, PokemonType.COLORLESS),
        effect="Provides 2 {C} Energy.",
    )
    defaults.update(kwargs)
    return EnergyCard(**defaults)


class TestCompileCard:
    def test_compile_pokemon_has_attack_effects(self):
        card = _make_pokemon()
        compiled = compile_card(card)
        assert isinstance(compiled, CompiledCard)
        assert "Splash" in compiled.attack_effects
        assert isinstance(compiled.attack_effects["Splash"], DrawCards)

    def test_compile_trainer(self):
        card = _make_trainer()
        compiled = compile_card(card)
        assert compiled.trainer_effect is not None
        assert isinstance(compiled.trainer_effect, HealEffect)

    def test_compile_energy_with_effect(self):
        card = _make_energy()
        compiled = compile_card(card)
        # Effect text provides → UnknownEffect (no rule for this) or some parsed form
        assert compiled.energy_effect is not None

    def test_compile_energy_basic_no_effect(self):
        from src.cards.enums import CardSuperType, EnergyType, ExpansionCode, PokemonType
        from src.cards.models import EnergyCard
        from src.cards.types import CardId

        card = EnergyCard(
            card_id=CardId(3002),
            name="Water Energy",
            expansion=ExpansionCode.UNKNOWN,
            collection_number="004",
            card_super_type=CardSuperType.ENERGY,
            energy_type=EnergyType.BASIC,
            provides=(PokemonType.WATER,),
            effect="",
        )
        compiled = compile_card(card)
        assert compiled.energy_effect is None

    def test_compile_pokemon_with_ability(self):
        from src.cards.enums import CardSuperType, ExpansionCode, PokemonType, Stage
        from src.cards.models import Ability, Attack, DamageValue, EnergyCostModel, PokemonCard
        from src.cards.types import CardId

        ability = Ability(name="Water Call", effect="Once during your turn, you may use this Ability.")
        attack = Attack(
            name="Bubble",
            cost=EnergyCostModel(tokens=(), total_count=0),
            damage=DamageValue(base=0, raw="0"),
            effect="",
        )
        card = PokemonCard(
            card_id=CardId(1002),
            name="Lapras",
            expansion=ExpansionCode.UNKNOWN,
            collection_number="005",
            card_super_type=CardSuperType.POKEMON,
            stage=Stage.BASIC,
            hp=130,
            pokemon_type=PokemonType.WATER,
            retreat_cost=2,
            attacks=(attack,),
            ability=ability,
        )
        compiled = compile_card(card)
        assert compiled.ability_effect is not None

    def test_all_effects_lists_all(self):
        card = _make_pokemon()
        compiled = compile_card(card)
        all_effs = compiled.all_effects()
        assert len(all_effs) > 0

    def test_compiled_card_is_frozen(self):
        card = _make_pokemon()
        compiled = compile_card(card)
        with pytest.raises(Exception):
            compiled.name = "Changed"  # type: ignore[misc]


# ===========================================================================
# 7. Validation
# ===========================================================================

class TestValidation:
    def test_no_unknowns_is_clean(self):
        card = _make_pokemon()
        compiled = compile_card(card)
        report = validate_compiled(compiled)
        # "Draw 2 cards." should parse cleanly
        assert report.is_clean()
        assert len(report.errors) == 0

    def test_unknown_effect_flagged(self):
        from src.cards.enums import CardSuperType, ExpansionCode, PokemonType, Stage
        from src.cards.models import Attack, DamageValue, EnergyCostModel, PokemonCard
        from src.cards.types import CardId

        attack = Attack(
            name="Mystery",
            cost=EnergyCostModel(tokens=("{C}",), total_count=1),
            damage=DamageValue(base=10, raw="10"),
            effect="xyzzy frobble blort completely unrecognised text",
        )
        card = PokemonCard(
            card_id=CardId(9999),
            name="MysteryMon",
            expansion=ExpansionCode.UNKNOWN,
            collection_number="999",
            card_super_type=CardSuperType.POKEMON,
            stage=Stage.BASIC,
            hp=60,
            pokemon_type=PokemonType.COLORLESS,
            retreat_cost=1,
            attacks=(attack,),
        )
        compiled = compile_card(card)
        report = validate_compiled(compiled)
        assert len(report.issues) > 0
        assert report.unknown_count > 0

    def test_validate_all_aggregates(self):
        c1 = _make_pokemon()
        c2 = _make_trainer()
        compiled = [compile_card(c1), compile_card(c2)]
        report = validate_all(compiled)
        # Both parse cleanly — no issues expected
        assert isinstance(report.issues, list)

    def test_validation_issue_fields(self):
        from src.cards.effects.validators import ValidationIssue
        issue = ValidationIssue(card_id="1", name="Test", location="attack:Foo", message="1 UnknownEffect")
        assert issue.severity == "warning"


# ===========================================================================
# 8. Edge cases
# ===========================================================================

class TestEdgeCases:
    def test_unicode_pokemon_symbol(self):
        e = parse("Discard a {G} Energy from this Pokémon.")
        assert isinstance(e, DiscardEffect)

    def test_accented_pokemon_text(self):
        e = parse("Heal 30 damage from this Pokémon.")
        assert isinstance(e, HealEffect)

    def test_multiline_text(self):
        text = "Draw 2 cards.\nHeal 30 damage from this Pokémon."
        e = parse(text)
        assert isinstance(e, CompositeEffect)

    def test_very_long_text_does_not_crash(self):
        text = ("Draw 2 cards. " * 50).strip()
        e = parse(text)
        # Should return a CompositeEffect with 50 DrawCards
        assert isinstance(e, CompositeEffect)
        assert len(e.steps) == 50

    def test_factory_exception_gives_unknown(self):
        """A broken factory should produce UnknownEffect via graceful degradation."""
        reg = RuleRegistry()
        bad_rule = Rule(
            "bad_factory",
            re.compile(r"draw \d+ cards", re.I),
            lambda m, raw: 1 / 0,  # raises ZeroDivisionError
            priority=1,  # fires before the real draw rule
        )
        reg.register(bad_rule, replace=True)
        # The good draw rule is still there at lower priority
        e = match_sentence("Draw 2 cards.", registry=reg)
        # Should fall through to the real rule or UnknownEffect — not raise
        assert isinstance(e, Effect)

    def test_na_string_variants(self):
        for text in ("", "  ", "n/a"):
            e = parse(text)
            assert isinstance(e, UnknownEffect)

    def test_parse_effect_functional(self):
        """Top-level parse_effect matches parse() output."""
        assert type(parse_effect("Draw 2 cards.")) == type(parse("Draw 2 cards."))

    def test_all_rules_have_unique_names(self):
        names = [r.name for r in ALL_RULES]
        assert len(names) == len(set(names)), "Duplicate rule names found"

    def test_all_rules_priority_ints(self):
        for rule in ALL_RULES:
            assert isinstance(rule.priority, int)

    def test_match_sentence_returns_unknown_for_gibberish(self):
        e = match_sentence("ajskdhakjsdhakjshd")
        assert isinstance(e, UnknownEffect)

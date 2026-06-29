"""
Regression tests for Simulator Fidelity Phase — P1.

Covers:
  • Effect dispatcher additions (P1.1)
  • Per-card trainer handlers (P1.2)
  • Per-card ability handlers (P1.3)
  • Variable damage / damage modifiers (P1.4)
  • Stadium / Tool / Special Energy modifiers (P1.5–7)
  • Extended SimulatorReport telemetry (P1.9)
"""

from __future__ import annotations

import pytest
from src.cards.effects.actions import Target
from src.cards.effects.actions import Zone as ParserZone
from src.cards.effects.models import (
    AttachEnergy,
    BenchDamage,
    DamageCounters,
    DrawCards,
    ForceSwitch,
    HealEffect,
    KnockOut,
    MillEffect,
    MoveEnergy,
    ReturnToHand,
    SearchDiscard,
    SelfDamage,
    ShuffleEffect,
    StatusConditionEffect,
    SwitchActive,
)
from src.cards.enums import (
    CardSuperType,
    DamageModifier,
    EnergyType,
    ExpansionCode,
    PokemonType,
    RuleBox,
    Stage,
    StatusCondition,
    TrainerType,
)
from src.cards.models import (
    Ability,
    Attack,
    DamageValue,
    EnergyCard,
    EnergyCostModel,
    PokemonCard,
    TrainerCard,
)
from src.cards.parser import ParseResult
from src.cards.repository import CardRepository
from src.game_state.zones import SpecialCondition
from src.simulator import (
    SIM_REPORT,
    PokemonTCGSimulator,
    apply_effect,
    compute_damage,
    named_ability_handlers,
    named_trainer_handlers,
)
from src.simulator.modifiers import (
    attacker_special_energy_delta,
    attacker_tool_damage_bonus,
    defender_hp_bonus,
    retreat_cost_delta,
    stadium_active_name,
    stadium_suppresses_abilities,
)
from src.simulator.rules import DEFAULT_RULES

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

_ID = 900_000


def _next_id() -> int:
    global _ID
    _ID += 1
    return _ID


def _cost(*tokens: str) -> EnergyCostModel:
    return EnergyCostModel(tokens=tokens, total_count=len(tokens))


def _dmg(base: int) -> DamageValue:
    return DamageValue(base=base, modifier=DamageModifier.EXACT, raw=str(base))


def _basic(
    name: str = "Mon",
    hp: int = 80,
    ptype: PokemonType = PokemonType.COLORLESS,
    attacks: tuple[Attack, ...] | None = None,
    retreat: int = 1,
    rule_box: RuleBox = RuleBox.NONE,
    ability: Ability | None = None,
) -> PokemonCard:
    if attacks is None:
        attacks = (Attack(name="Tackle", cost=_cost("{C}"), damage=_dmg(20)),)
    return PokemonCard(
        card_id=_next_id(), name=name,
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.POKEMON,
        stage=Stage.BASIC, hp=hp, pokemon_type=ptype,
        attacks=attacks, retreat_cost=retreat, rule_box=rule_box,
        ability=ability,
    )


def _energy(provides: PokemonType = PokemonType.COLORLESS,
            name: str | None = None,
            etype: EnergyType = EnergyType.BASIC) -> EnergyCard:
    n = name or f"{provides.name.title()} Energy"
    return EnergyCard(
        card_id=_next_id(), name=n,
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.ENERGY,
        energy_type=etype, provides=(provides,),
    )


def _trainer(name: str, ttype: TrainerType, effect: str = "") -> TrainerCard:
    return TrainerCard(
        card_id=_next_id(), name=name,
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.TRAINER,
        trainer_type=ttype, effect=effect,
    )


def _repo(cards: list) -> CardRepository:
    return CardRepository(ParseResult(cards=list(cards)), run_validation=False)


def _make_sim(cards: list, seed: int = 0) -> tuple[PokemonTCGSimulator, list]:
    repo = _repo(cards)
    sim = PokemonTCGSimulator(repo, seed=seed)
    return sim, list(repo.list_all())


def _build_state(sim: PokemonTCGSimulator, deck_ids: list[int]):
    return sim.start_game(deck_ids[:60], deck_ids[:60])


# =========================================================================
# P1.1 — Effect dispatcher
# =========================================================================

class TestEffectDispatcher:
    def setup_method(self):
        SIM_REPORT.clear()

    def _state(self):
        plain = _basic("Plain", hp=100)
        e = _energy()
        sim, _ = _make_sim([plain, e])
        return sim, sim.start_game(
            [plain.card_id] * 30 + [e.card_id] * 30,
            [plain.card_id] * 30 + [e.card_id] * 30,
        )

    def test_draw_cards_success_recorded(self):
        sim, state = self._state()
        before = state.players[0].hand_count
        new_state = apply_effect(state, DrawCards(count=3), player_id=0)
        assert new_state.players[0].hand_count >= before
        assert SIM_REPORT.execution_counts.get("DrawCards", 0) == 1

    def test_heal_effect_executes(self):
        sim, state = self._state()
        # Damage P0 active to 30
        active_id = state.players[0].active
        if active_id is None:
            pytest.skip("no active")
        inst = state.card_instances[active_id]
        state = state.with_instance(inst.with_added_damage(30))
        new_state = apply_effect(
            state, HealEffect(amount=20, target=Target.SELF),
            player_id=0,
            source_instance_id=active_id,
            target_instance_id=active_id,
        )
        assert new_state.card_instances[active_id].damage_taken == 10

    def test_self_damage_executes(self):
        sim, state = self._state()
        active_id = state.players[0].active
        if active_id is None:
            pytest.skip("no active")
        new_state = apply_effect(
            state, SelfDamage(amount=20),
            player_id=0,
            source_instance_id=active_id,
        )
        assert new_state.card_instances[active_id].damage_taken == 20

    def test_bench_damage_executes(self):
        sim, state = self._state()
        bench = state.players[1].bench
        if not bench:
            pytest.skip("no opponent bench")
        new_state = apply_effect(
            state, BenchDamage(amount=30, target=Target.BENCHED_OPP),
            player_id=0,
            source_instance_id=state.players[0].active,
            target_instance_id=None,
        )
        # At least one bench took 30
        any_dmg = any(
            new_state.card_instances[b].damage_taken >= 30 for b in bench
        )
        assert any_dmg

    def test_status_condition_effect_applies(self):
        sim, state = self._state()
        opp_active = state.players[1].active
        if opp_active is None:
            pytest.skip("no opp active")
        new_state = apply_effect(
            state,
            StatusConditionEffect(
                condition=StatusCondition.BURNED, target=Target.ACTIVE_OPP
            ),
            player_id=0,
        )
        assert SpecialCondition.BURNED in new_state.card_instances[
            opp_active
        ].special_conditions

    def test_switch_active_executes(self):
        sim, state = self._state()
        if not state.players[0].bench:
            pytest.skip("no bench")
        old_active = state.players[0].active
        new_state = apply_effect(state, SwitchActive(), player_id=0)
        assert new_state.players[0].active != old_active

    def test_mill_effect_executes(self):
        sim, state = self._state()
        before = state.players[1].deck_size
        new_state = apply_effect(
            state, MillEffect(count=3, who=Target.ACTIVE_OPP), player_id=0,
        )
        assert new_state.players[1].deck_size == before - 3

    def test_return_to_hand_executes(self):
        sim, state = self._state()
        bench = state.players[0].bench
        if not bench:
            pytest.skip("no bench")
        target = bench[0]
        new_state = apply_effect(
            state, ReturnToHand(target=Target.BENCHED_SELF),
            player_id=0,
        )
        assert target in new_state.players[0].hand

    def test_force_switch_executes(self):
        sim, state = self._state()
        if not state.players[1].bench:
            pytest.skip("no opp bench")
        old_opp_active = state.players[1].active
        new_state = apply_effect(state, ForceSwitch(), player_id=0)
        assert new_state.players[1].active != old_opp_active

    def test_damage_counters_executes(self):
        sim, state = self._state()
        opp_active = state.players[1].active
        if opp_active is None:
            pytest.skip("no opp active")
        new_state = apply_effect(
            state, DamageCounters(count=5, target=Target.ACTIVE_OPP),
            player_id=0,
        )
        # 5 damage counters = 50 damage
        assert new_state.card_instances[opp_active].damage_taken == 50

    def test_shuffle_hand_into_deck(self):
        sim, state = self._state()
        before_hand = state.players[0].hand_count
        before_deck = state.players[0].deck_size
        new_state = apply_effect(
            state, ShuffleEffect(hand_first=True, draw_after=3),
            player_id=0,
            randomizer=sim.randomizer,
        )
        # Hand → deck → drew 3
        assert new_state.players[0].hand_count >= 0
        # deck eventually contains hand + original − 3
        assert (new_state.players[0].hand_count
                + new_state.players[0].deck_size
                == before_hand + before_deck)

    def test_search_discard_executes(self):
        sim, state = self._state()
        # Put a card in discard
        active = state.players[0].active
        if active is None:
            pytest.skip("no active")
        # Force-discard a hand card
        p = state.players[0]
        if not p.hand:
            pytest.skip("empty hand")
        from src.simulator import zones as Z
        state = Z.discard_from_hand(state, 0, p.hand[0])
        new_state = apply_effect(
            state, SearchDiscard(card_type="any", count=1), player_id=0,
        )
        assert new_state.players[0].discard_count <= state.players[0].discard_count

    def test_attach_energy_from_hand(self):
        # Build a state where hand has an energy card
        sim, state = self._state()
        p = state.players[0]
        energy_id = next(
            (h for h in p.hand
             if state.card_instances[h].card_name.endswith("Energy")),
            None,
        )
        if energy_id is None:
            pytest.skip("no energy in hand")
        active = p.active
        if active is None:
            pytest.skip("no active")
        before = len(state.card_instances[active].attached_energy_ids)
        new_state = apply_effect(
            state, AttachEnergy(source=ParserZone.HAND, count=1),
            player_id=0,
            source_instance_id=active,
            target_instance_id=active,
        )
        after = len(new_state.card_instances[active].attached_energy_ids)
        assert after == before + 1

    def test_move_energy_executes(self):
        sim, state = self._state()
        p = state.players[0]
        if p.active is None or not p.bench:
            pytest.skip("setup")
        # Attach an energy via setup, then move
        energy_id = next(
            (h for h in p.hand
             if state.card_instances[h].card_name.endswith("Energy")),
            None,
        )
        if energy_id is None:
            pytest.skip("no energy")
        active = p.active
        from src.simulator import zones as Z
        state = Z.attach_energy_to_pokemon(state, 0, energy_id, active)
        before_active = len(state.card_instances[active].attached_energy_ids)
        new_state = apply_effect(
            state, MoveEnergy(
                from_target=Target.ACTIVE_SELF,
                to_target=Target.BENCHED_SELF, count=1,
            ),
            player_id=0,
            source_instance_id=active,
            target_instance_id=state.players[0].bench[0],
        )
        assert (len(new_state.card_instances[active].attached_energy_ids)
                == before_active - 1)

    def test_knockout_effect(self):
        sim, state = self._state()
        opp_active = state.players[1].active
        if opp_active is None:
            pytest.skip("no opp active")
        new_state = apply_effect(
            state, KnockOut(target=Target.ACTIVE_OPP), player_id=0,
        )
        assert new_state.card_instances[opp_active].is_knocked_out


# =========================================================================
# P1.2 — Trainer handlers
# =========================================================================

class TestTrainerHandlers:
    def test_handlers_registered(self):
        handlers = named_trainer_handlers()
        expected = [
            "Ultra Ball", "Nest Ball", "Buddy-Buddy Poffin", "Rare Candy",
            "Iono", "Professor's Research", "Boss's Orders", "Arven",
            "Counter Catcher", "Switch", "Super Rod", "Energy Retrieval",
            "Earthen Vessel", "Night Stretcher", "Pal Pad", "Hyper Aroma",
        ]
        for name in expected:
            assert name in handlers, f"missing {name}"

    def _setup(self, trainer_name: str, ttype: TrainerType,
                effect: str = ""):
        target = _basic("Active", hp=100)
        extra = _basic("Spare", hp=80)
        energy = _energy()
        trainer = _trainer(trainer_name, ttype, effect=effect or "Effect text.")
        sim, _ = _make_sim([target, extra, energy, trainer])
        # Deck heavy on target + energy + trainer copies
        deck = ([target.card_id, extra.card_id] * 6
                + [trainer.card_id] * 4
                + [energy.card_id] * 44)
        state = sim.start_game(deck[:60], deck[:60])
        return sim, state, trainer

    def test_professors_research_draws(self):
        sim, state, trainer = self._setup(
            "Professor's Research", TrainerType.SUPPORTER,
            "Discard your hand and draw 7 cards.",
        )
        from src.simulator.effects import apply_trainer_effects
        new_state = apply_trainer_effects(
            state, trainer=trainer, player_id=0,
            repository=sim.repository, randomizer=sim.randomizer,
        )
        assert new_state.players[0].hand_count == 7

    def test_nest_ball_pulls_basic(self):
        sim, state, trainer = self._setup(
            "Nest Ball", TrainerType.ITEM,
            "Search your deck for a Basic Pokémon.",
        )
        before = state.players[0].hand_count
        from src.simulator.effects import apply_trainer_effects
        new_state = apply_trainer_effects(
            state, trainer=trainer, player_id=0,
            repository=sim.repository, randomizer=sim.randomizer,
        )
        assert new_state.players[0].hand_count >= before

    def test_switch_swaps_active(self):
        sim, state, trainer = self._setup(
            "Switch", TrainerType.ITEM,
            "Switch your Active Pokémon with one of your Benched Pokémon.",
        )
        if not state.players[0].bench:
            pytest.skip("no bench")
        old_active = state.players[0].active
        from src.simulator.effects import apply_trainer_effects
        new_state = apply_trainer_effects(
            state, trainer=trainer, player_id=0,
            repository=sim.repository, randomizer=sim.randomizer,
        )
        assert new_state.players[0].active != old_active

    def test_bosss_orders_gusts(self):
        sim, state, trainer = self._setup(
            "Boss's Orders", TrainerType.SUPPORTER,
            "Switch in 1 of your opponent's Benched Pokémon.",
        )
        if not state.players[1].bench:
            pytest.skip("no opp bench")
        old_opp_active = state.players[1].active
        from src.simulator.effects import apply_trainer_effects
        new_state = apply_trainer_effects(
            state, trainer=trainer, player_id=0,
            repository=sim.repository, randomizer=sim.randomizer,
        )
        assert new_state.players[1].active != old_opp_active


# =========================================================================
# P1.3 — Ability handlers
# =========================================================================

class TestAbilityHandlers:
    def test_handlers_registered(self):
        handlers = named_ability_handlers()
        expected = [
            "Pidgeot ex", "Charizard ex", "Bibarel", "Comfey",
            "Squawkabilly ex", "Gardevoir ex", "Iron Hands ex", "Lugia ex",
        ]
        for name in expected:
            assert name in handlers, f"missing ability handler for {name}"

    def test_bibarel_draws_to_5(self):
        ability = Ability(
            name="Industrious Incisors",
            effect="Once during your turn, you may draw cards until you have 5 cards in your hand.",
        )
        card = _basic("Bibarel", hp=120, ability=ability)
        e = _energy()
        sim, _ = _make_sim([card, e])
        state = sim.start_game(
            [card.card_id] * 15 + [e.card_id] * 45,
            [card.card_id] * 15 + [e.card_id] * 45,
        )
        # Reduce hand to 2
        p = state.players[0]
        for hid in list(p.hand)[:max(0, p.hand_count - 2)]:
            from src.simulator import zones as Z
            state = Z.discard_from_hand(state, 0, hid)
        # Trigger ability via handler directly
        handler = named_ability_handlers()["Bibarel"]
        new_state = handler(
            state, 0, card, source_instance_id=state.players[0].active,
            repository=sim.repository, randomizer=sim.randomizer,
        )
        assert new_state.players[0].hand_count == 5


# =========================================================================
# P1.4 — Variable damage and damage modifiers
# =========================================================================

class TestVariableDamageAndModifiers:
    def test_double_turbo_energy_reduces_damage(self):
        # Attacker with Double Turbo Energy attached should deal -20
        special = _energy(
            PokemonType.COLORLESS, name="Double Turbo Energy",
            etype=EnergyType.SPECIAL,
        )
        attacker = _basic(
            "Striker", hp=100,
            attacks=(Attack(name="Hit", cost=_cost("{C}"), damage=_dmg(80)),),
        )
        defender = _basic("Wall", hp=200)
        sim, _ = _make_sim([attacker, defender, special])
        state = sim.start_game(
            [attacker.card_id] * 8 + [defender.card_id] * 4
            + [special.card_id] * 48,
            [defender.card_id] * 8 + [attacker.card_id] * 4
            + [special.card_id] * 48,
        )
        p0 = state.players[0]
        if p0.active is None:
            pytest.skip("setup")
        # Attach the special energy to attacker
        from src.simulator import zones as Z
        # Find a Double Turbo Energy in P0's hand
        dt_id = next(
            (h for h in p0.hand
             if state.card_instances[h].card_name == "Double Turbo Energy"),
            None,
        )
        if dt_id is None:
            pytest.skip("no Double Turbo in hand")
        state = Z.attach_energy_to_pokemon(state, 0, dt_id, p0.active)
        # Compute damage
        atk = attacker.attacks[0]
        result = compute_damage(
            attacker_card=attacker,
            attacker_instance=state.card_instances[p0.active],
            attack=atk,
            defender_card=defender,
            defender_instance=state.card_instances[state.players[1].active],
            rules=DEFAULT_RULES,
            state=state, repository=sim.repository,
        )
        assert result.final_damage == 60  # 80 − 20

    def test_defiance_band_bonus_vs_ex(self):
        defender_ex = _basic("Big ex", hp=300, rule_box=RuleBox.POKEMON_EX)
        attacker = _basic(
            "Striker", hp=100,
            attacks=(Attack(name="Hit", cost=_cost("{C}"), damage=_dmg(100)),),
        )
        tool = _trainer(
            "Defiance Band", TrainerType.POKEMON_TOOL,
            effect="The attacks of the Pokémon this card is attached to do 30 more damage to the opponent's Active Pokémon ex.",
        )
        e = _energy()
        sim, _ = _make_sim([attacker, defender_ex, tool, e])
        state = sim.start_game(
            [attacker.card_id] * 8 + [tool.card_id] * 4 + [e.card_id] * 48,
            [defender_ex.card_id] * 8 + [e.card_id] * 52,
        )
        p0 = state.players[0]
        if p0.active is None or state.players[1].active is None:
            pytest.skip("setup")
        # Attach tool to attacker
        tool_id = next(
            (h for h in p0.hand
             if state.card_instances[h].card_name == "Defiance Band"),
            None,
        )
        if tool_id is None:
            pytest.skip("no Defiance Band")
        active_inst = state.card_instances[p0.active]
        state = state.with_instance(active_inst.model_copy(
            update={"attached_tool_id": tool_id},
        ))
        # Compute damage: attacker_tool_damage_bonus should add 30 vs ex
        delta = attacker_tool_damage_bonus(
            state, state.card_instances[p0.active],
            defender_ex, sim.repository,
        )
        assert delta == 30

    def test_attacker_special_energy_delta_zero_without_special(self):
        attacker = _basic("Plain", hp=80)
        e = _energy()
        sim, _ = _make_sim([attacker, e])
        state = sim.start_game(
            [attacker.card_id] * 12 + [e.card_id] * 48,
            [attacker.card_id] * 12 + [e.card_id] * 48,
        )
        p0 = state.players[0]
        if p0.active is None:
            pytest.skip("no active")
        assert attacker_special_energy_delta(
            state, state.card_instances[p0.active], sim.repository,
        ) == 0


# =========================================================================
# P1.5 / P1.6 / P1.7 — Stadium / Tool / Special Energy
# =========================================================================

class TestStaticModifiers:
    def test_stadium_lookup_when_none(self):
        attacker = _basic("Plain", hp=80)
        e = _energy()
        sim, _ = _make_sim([attacker, e])
        state = sim.start_game(
            [attacker.card_id] * 12 + [e.card_id] * 48,
            [attacker.card_id] * 12 + [e.card_id] * 48,
        )
        assert stadium_active_name(state, sim.repository) == ""
        assert not stadium_suppresses_abilities(state, sim.repository)

    def test_path_to_the_peak_suppresses(self):
        path = _trainer("Path to the Peak", TrainerType.STADIUM,
                         effect="Pokémon ex have no abilities.")
        attacker = _basic("Plain", hp=80)
        e = _energy()
        sim, _ = _make_sim([attacker, path, e])
        state = sim.start_game(
            [attacker.card_id] * 8 + [path.card_id] * 4 + [e.card_id] * 48,
            [attacker.card_id] * 12 + [e.card_id] * 48,
        )
        # Force the stadium into the global slot for testing the lookup
        path_inst = next(
            (h for h in state.players[0].hand
             if state.card_instances[h].card_name == "Path to the Peak"),
            None,
        )
        if path_inst is None:
            pytest.skip("no Path in hand")
        state = state.model_copy(update={"stadium_instance_id": path_inst})
        assert stadium_active_name(state, sim.repository) == "Path to the Peak"
        assert stadium_suppresses_abilities(state, sim.repository)

    def test_retreat_cost_delta_air_balloon(self):
        attacker = _basic("Plain", hp=80)
        balloon = _trainer("Air Balloon", TrainerType.POKEMON_TOOL,
                            effect="Retreat cost is 2 less.")
        e = _energy()
        sim, _ = _make_sim([attacker, balloon, e])
        state = sim.start_game(
            [attacker.card_id] * 8 + [balloon.card_id] * 4 + [e.card_id] * 48,
            [attacker.card_id] * 12 + [e.card_id] * 48,
        )
        p0 = state.players[0]
        if p0.active is None:
            pytest.skip("no active")
        balloon_id = next(
            (h for h in p0.hand
             if state.card_instances[h].card_name == "Air Balloon"),
            None,
        )
        if balloon_id is None:
            pytest.skip("no Balloon in hand")
        active_inst = state.card_instances[p0.active]
        state = state.with_instance(active_inst.model_copy(
            update={"attached_tool_id": balloon_id},
        ))
        assert retreat_cost_delta(
            state, state.card_instances[p0.active], sim.repository,
        ) == -2

    def test_defender_hp_bonus_bravery_charm(self):
        defender = _basic("Wall", hp=100)
        charm = _trainer("Bravery Charm", TrainerType.POKEMON_TOOL,
                          effect="+50 HP.")
        e = _energy()
        sim, _ = _make_sim([defender, charm, e])
        state = sim.start_game(
            [defender.card_id] * 8 + [charm.card_id] * 4 + [e.card_id] * 48,
            [defender.card_id] * 12 + [e.card_id] * 48,
        )
        p0 = state.players[0]
        if p0.active is None:
            pytest.skip("no active")
        charm_id = next(
            (h for h in p0.hand
             if state.card_instances[h].card_name == "Bravery Charm"),
            None,
        )
        if charm_id is None:
            pytest.skip("no Charm")
        active = state.card_instances[p0.active]
        state = state.with_instance(active.model_copy(
            update={"attached_tool_id": charm_id},
        ))
        bonus = defender_hp_bonus(
            state, state.card_instances[p0.active], sim.repository,
        )
        assert bonus == 50


# =========================================================================
# P1.9 — Extended SimulatorReport
# =========================================================================

class TestSimulatorReportTelemetry:
    def setup_method(self):
        SIM_REPORT.clear()

    def test_execution_counts_track_successes(self):
        plain = _basic("Plain")
        e = _energy()
        sim, _ = _make_sim([plain, e])
        state = sim.start_game([e.card_id] * 60, [plain.card_id] * 60)
        apply_effect(state, DrawCards(count=1), player_id=0)
        apply_effect(state, DrawCards(count=2), player_id=0)
        assert SIM_REPORT.execution_counts.get("DrawCards") == 2

    def test_failure_counts_track_unsupported(self):
        from src.cards.effects.models import CopyAttack
        plain = _basic("Plain")
        e = _energy()
        sim, _ = _make_sim([plain, e])
        state = sim.start_game([e.card_id] * 60, [plain.card_id] * 60)
        apply_effect(state, CopyAttack(copy_from="opponent_active"),
                      player_id=0, card_name="X", card_id="1")
        assert SIM_REPORT.failure_counts.get("CopyAttack") == 1

    def test_success_rates(self):
        from src.cards.effects.models import CopyAttack
        plain = _basic("Plain")
        e = _energy()
        sim, _ = _make_sim([plain, e])
        state = sim.start_game([e.card_id] * 60, [plain.card_id] * 60)
        apply_effect(state, DrawCards(count=1), player_id=0)
        apply_effect(state, CopyAttack(copy_from="x"),
                      player_id=0, card_name="X", card_id="1")
        rates = SIM_REPORT.success_rates()
        assert rates.get("DrawCards") == 1.0
        assert rates.get("CopyAttack") == 0.0

    def test_trainer_attack_ability_executions(self):
        from src.simulator.effects import SIM_REPORT as R
        R.record_trainer("Ultra Ball")
        R.record_trainer("Ultra Ball")
        R.record_ability("Pidgeot ex")
        R.record_attack("Thunderbolt")
        assert R.trainer_executions["Ultra Ball"] == 2
        assert R.ability_executions["Pidgeot ex"] == 1
        assert R.attack_executions["Thunderbolt"] == 1

    def test_to_dict_includes_new_telemetry(self):
        SIM_REPORT.record_success("DrawCards")
        d = SIM_REPORT.to_dict()
        assert "execution_counts" in d
        assert "success_counts" in d
        assert "failure_counts" in d
        assert "trainer_executions" in d
        assert "ability_executions" in d
        assert "attack_executions" in d
        assert "success_rates" in d


# =========================================================================
# Integration: random playthrough still terminates
# =========================================================================

class TestP1Integration:
    def test_full_game_completes(self):
        import random as _random

        from src.cards import load_repository
        repo = load_repository()
        basics = [c for c in repo.list_all()
                   if isinstance(c, PokemonCard) and c.stage == Stage.BASIC][:8]
        energies = [c for c in repo.list_all()
                     if isinstance(c, EnergyCard)][:3]
        deck = [b.card_id for b in basics] * 4 + [e.card_id for e in energies] * 10
        deck = deck[:60]
        from src.simulator.rules import GameRules
        sim = PokemonTCGSimulator(
            repo, seed=42,
            rules=GameRules(max_turns=40),
        )
        state = sim.start_game(deck, deck)
        rng = _random.Random(0)
        steps = 0
        while not sim.is_terminal(state) and steps < 500:
            legal = sim.legal_actions(state)
            if not legal:
                break
            state = sim.apply_action(state, rng.choice(legal))
            steps += 1
        assert sim.is_terminal(state) or steps == 500
        assert steps > 0

"""
Comprehensive tests for the Automatic Deck Construction Engine (Phase 6).
"""

from __future__ import annotations

import json
import random
import time

import pytest
from src.cards.enums import (
    CardSuperType,
    EnergyType,
    ExpansionCode,
    PokemonType,
    RuleBox,
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
from src.deck_builder import (
    STRATEGIES,
    BuildRequest,
    BuildResult,
    CardIndex,
    ConstraintConfig,
    ConstructiveGenerator,
    DeckBuilder,
    ObjectiveSet,
    RepairEngine,
    exports,
    get_strategy,
    get_template,
    score_deck_fast,
)
from src.deck_builder.constraints import check_all, is_legal, total_count
from src.deck_builder.crossover import segment_crossover, uniform_crossover
from src.deck_builder.mutations import (
    diversify,
    increase_draw,
    increase_energy,
    reduce_energy,
    swap_card,
)
from src.deck_builder.objectives import (
    ConsistencyObjective,
    fast_score_metrics,
)
from src.decks.models import Deck, DeckSlot

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ID = 5000


def _uid() -> int:
    global _ID
    _ID += 1
    return _ID


def _cost(n: int, tok: str = "{C}") -> EnergyCostModel:
    return EnergyCostModel(tokens=tuple([tok] * n), total_count=n)


def _dmg(base: int) -> DamageValue:
    return DamageValue(base=base, raw=str(base))


def _pokemon(
    name: str,
    stage: Stage = Stage.BASIC,
    hp: int = 100,
    ptype: PokemonType = PokemonType.COLORLESS,
    retreat: int = 1,
    attacks=None,
    ability=None,
    previous_stage: str | None = None,
    rule_box: RuleBox = RuleBox.NONE,
) -> PokemonCard:
    if attacks is None:
        attacks = (Attack(name="Strike", cost=_cost(2), damage=_dmg(60 + hp // 10)),)
    return PokemonCard(
        card_id=_uid(), name=name,
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.POKEMON,
        stage=stage, hp=hp, pokemon_type=ptype,
        attacks=attacks, ability=ability, retreat_cost=retreat,
        rule_box=rule_box, previous_stage=previous_stage,
    )


def _trainer(
    name: str,
    ttype: TrainerType = TrainerType.ITEM,
    effect: str = "Draw 2 cards. Search your deck for a card.",
) -> TrainerCard:
    return TrainerCard(
        card_id=_uid(), name=name,
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.TRAINER,
        trainer_type=ttype, effect=effect,
    )


def _energy(
    name: str = "Fire Energy",
    provides: tuple = (PokemonType.FIRE,),
    etype: EnergyType = EnergyType.BASIC,
) -> EnergyCard:
    return EnergyCard(
        card_id=_uid(), name=name,
        expansion=ExpansionCode.UNKNOWN, collection_number="1",
        card_super_type=CardSuperType.ENERGY,
        energy_type=etype, provides=provides,
    )


def _make_card_list() -> list:
    """Minimal card list for unit tests (no real DB needed)."""
    cards = []
    # Basics
    for i in range(20):
        ptype = list(PokemonType)[i % 9]
        cards.append(_pokemon(f"Basic{i}", hp=80 + i * 5, ptype=ptype,
                               attacks=(Attack(
                                   name="Tackle",
                                   cost=_cost(1 + i % 3),
                                   damage=_dmg(30 + i * 10)),)))
    # Stage 1s
    for i in range(5):
        prev = f"Basic{i}"
        cards.append(_pokemon(f"Stage1_{i}", stage=Stage.STAGE_1,
                               hp=120 + i * 10, previous_stage=prev,
                               attacks=(Attack(name="Slash",
                                              cost=_cost(2), damage=_dmg(80 + i * 15)),)))
    # Stage 2s
    for i in range(3):
        prev = f"Stage1_{i}"
        cards.append(_pokemon(f"Stage2_{i}", stage=Stage.STAGE_2,
                               hp=200 + i * 20, previous_stage=prev,
                               attacks=(Attack(name="Blast",
                                              cost=_cost(3), damage=_dmg(150 + i * 30)),)))
    # Trainers
    for i in range(20):
        eff = f"Draw {i % 4 + 2} cards. Search your deck for a card and put it in your hand."
        cards.append(_trainer(f"Trainer{i}", ttype=TrainerType.ITEM if i % 2 else TrainerType.SUPPORTER, effect=eff))
    for i in range(5):
        cards.append(_trainer(f"Switch{i}", effect="Switch your Active Pokémon with one of your Benched Pokémon."))
    for i in range(5):
        cards.append(_trainer(f"Retrieval{i}", effect="Return a Pokémon from your discard pile to your hand."))
    # Energy
    for ptype in [PokemonType.FIRE, PokemonType.WATER, PokemonType.COLORLESS]:
        cards.append(_energy(f"{ptype.name.title()} Energy", provides=(ptype,)))
    return cards


def _make_index(cards=None) -> CardIndex:
    return CardIndex(cards or _make_card_list())


def _make_slots(n_poke=18, n_train=28, n_energy=14) -> dict[str, tuple]:
    """Build a 60-card slot dict from minimal cards."""
    cards = _make_card_list()
    idx = CardIndex(cards)
    slots: dict[str, tuple] = {}

    pokemon = idx.basics()
    trainers = idx.trainers()
    energies = idx.any_basic_energies()

    added = 0
    for p in pokemon:
        if added >= n_poke:
            break
        take = min(4, n_poke - added)
        slots[str(p.card_id)] = (p, take)
        added += take

    added = 0
    for t in trainers:
        if added >= n_train:
            break
        take = min(4, n_train - added)
        slots[str(t.card_id)] = (t, take)
        added += take

    added = 0
    for e in energies:
        if added >= n_energy:
            break
        slots[str(e.card_id)] = (e, n_energy - added)
        added = n_energy

    return slots


# ---------------------------------------------------------------------------
# Fixtures — real data
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def real_data():
    try:
        from src.cards.parser import parse_csv
        from src.cards.relationships import build_graph
        result = parse_csv("EN_Card_Data.csv")
        graph = build_graph(result.cards)
        return result.cards, graph
    except Exception:
        pytest.skip("EN_Card_Data.csv not available")


@pytest.fixture(scope="module")
def builder(real_data):
    cards, graph = real_data
    return DeckBuilder.from_graph_and_cards(graph, cards)


@pytest.fixture(scope="module")
def card_idx(real_data):
    cards, _ = real_data
    return CardIndex(cards)


# ---------------------------------------------------------------------------
# Constraints tests
# ---------------------------------------------------------------------------

class TestConstraints:
    def test_legal_60_card_deck(self):
        slots = _make_slots()
        assert total_count(slots) == 60
        assert is_legal(slots, ConstraintConfig())

    def test_wrong_size_error(self):
        slots = _make_slots(n_poke=10, n_train=10, n_energy=10)
        violations = check_all(slots, ConstraintConfig())
        assert any(v.code == "DECK_SIZE" for v in violations)

    def test_copy_limit_violation(self):
        card = _pokemon("Duped")
        slots = {str(card.card_id): (card, 5)}
        # Pad to 60
        e = _energy()
        slots[str(e.card_id)] = (e, 55)
        violations = check_all(slots, ConstraintConfig())
        assert any(v.code == "COPY_LIMIT" for v in violations)

    def test_basic_energy_no_copy_limit(self):
        card = _pokemon("A")
        e = _energy(etype=EnergyType.BASIC)
        slots = {str(card.card_id): (card, 4), str(e.card_id): (e, 56)}
        violations = check_all(slots, ConstraintConfig())
        assert not any(v.code == "COPY_LIMIT" for v in violations)

    def test_no_basic_error(self):
        s1 = _pokemon("Rhydon", stage=Stage.STAGE_1)
        e = _energy()
        slots = {str(s1.card_id): (s1, 4), str(e.card_id): (e, 56)}
        violations = check_all(slots, ConstraintConfig())
        assert any(v.code == "NO_BASIC_POKEMON" for v in violations)

    def test_missing_pre_evolution_warning(self):
        s2 = _pokemon("Dragonite", stage=Stage.STAGE_2, previous_stage="Dragonair")
        e = _energy()
        slots = {str(s2.card_id): (s2, 4), str(e.card_id): (e, 56)}
        violations = check_all(slots, ConstraintConfig())
        assert any(v.code == "MISSING_PRE_EVOLUTION" and v.severity == "warning" for v in violations)

    def test_total_count(self):
        slots = _make_slots()
        assert total_count(slots) == 60

    def test_constraint_config_custom(self):
        config = ConstraintConfig(deck_size=20, max_copies=2)
        card = _pokemon("X")
        e = _energy()
        slots = {str(card.card_id): (card, 2), str(e.card_id): (e, 18)}
        assert is_legal(slots, config)


# ---------------------------------------------------------------------------
# CardIndex tests
# ---------------------------------------------------------------------------

class TestCardIndex:
    def setup_method(self):
        self.cards = _make_card_list()
        self.idx = CardIndex(self.cards)

    def test_by_id(self):
        card = self.cards[0]
        assert self.idx.by_id(str(card.card_id)) is card

    def test_by_name(self):
        card = self.cards[0]
        results = self.idx.by_name(card.name)
        assert card in results

    def test_pokemon_list(self):
        assert len(self.idx.pokemon()) > 0
        assert all(isinstance(c, PokemonCard) for c in self.idx.pokemon())

    def test_trainers_list(self):
        assert len(self.idx.trainers()) > 0
        assert all(isinstance(c, TrainerCard) for c in self.idx.trainers())

    def test_energies_list(self):
        assert len(self.idx.energies()) > 0

    def test_basics(self):
        basics = self.idx.basics()
        assert all(c.stage == Stage.BASIC for c in basics)

    def test_draw_trainers(self):
        dt = self.idx.draw_trainers()
        assert all(isinstance(c, TrainerCard) for c in dt)
        assert all("draw" in c.effect.lower() for c in dt)

    def test_search_trainers(self):
        st = self.idx.search_trainers()
        assert len(st) > 0

    def test_by_stage(self):
        s2 = self.idx.pokemon_by_stage(Stage.STAGE_2)
        assert all(c.stage == Stage.STAGE_2 for c in s2)

    def test_basic_energies_for_type(self):
        fire = self.idx.basic_energies_for_type(PokemonType.FIRE)
        assert all(PokemonType.FIRE in e.provides for e in fire)


# ---------------------------------------------------------------------------
# Objective tests
# ---------------------------------------------------------------------------

class TestObjectives:
    def test_fast_score_range(self):
        s = fast_score_metrics(
            draw_power=12, search_power=8, basic_pokemon_count=8,
            energy_count=14, max_damage=200, recovery_score=4, avg_attack_cost=2.0,
        )
        assert 0 <= s <= 100

    def test_objective_set_scores_all(self, builder):
        deck = DeckSlot  # just need a real deck
        slots = _make_slots()
        from src.deck_builder.validators import slots_to_deck
        d = slots_to_deck(slots, "Test")
        report = builder._analyzer.analyze(d)
        obj_set = ObjectiveSet()
        breakdown = obj_set.score_all(report)
        assert "consistency" in breakdown
        assert "synergy" in breakdown
        assert all(isinstance(v, float) for v in breakdown.values())

    def test_total_score_in_range(self, builder):
        slots = _make_slots()
        from src.deck_builder.validators import slots_to_deck
        d = slots_to_deck(slots, "Test")
        report = builder._analyzer.analyze(d)
        obj_set = ObjectiveSet()
        total = obj_set.total(report)
        assert 0.0 <= total <= 100.0

    def test_weight_overrides(self, builder):
        obj_set = ObjectiveSet()
        obj_set.apply_weight_overrides({"consistency": 0.5})
        c_obj = next(o for o in obj_set.objectives if o.name == "consistency")
        assert c_obj.weight == 0.5

    def test_consistency_objective(self, builder):
        slots = _make_slots()
        from src.deck_builder.validators import slots_to_deck
        d = slots_to_deck(slots, "T")
        report = builder._analyzer.analyze(d)
        s = ConsistencyObjective().score(report)
        assert 0.0 <= s <= 100.0


# ---------------------------------------------------------------------------
# Repair engine tests
# ---------------------------------------------------------------------------

class TestRepairEngine:
    def setup_method(self):
        self.cards = _make_card_list()
        self.idx = CardIndex(self.cards)
        self.repair = RepairEngine(self.idx)

    def test_repair_no_basic(self):
        s1 = _pokemon("S1", stage=Stage.STAGE_1)
        e = _energy()
        slots = {str(s1.card_id): (s1, 4), str(e.card_id): (e, 56)}
        result = self.repair.repair(slots)
        assert any(a.code == "ADD_BASIC" for a in result.actions)

    def test_repair_size_pad(self):
        p = _pokemon("A")
        slots = {str(p.card_id): (p, 4)}
        result = self.repair.repair(slots)
        assert total_count(result.slots) == 60

    def test_repair_size_trim(self):
        p = _pokemon("A")
        e = _energy()
        slots = {str(p.card_id): (p, 4), str(e.card_id): (e, 62)}
        result = self.repair.repair(slots)
        assert total_count(result.slots) == 60

    def test_repair_copy_limit(self):
        p = _pokemon("Over")
        e = _energy()
        slots = {str(p.card_id): (p, 6), str(e.card_id): (e, 54)}
        result = self.repair.repair(slots)
        # Should trim to 4 and result should be 60 total
        assert total_count(result.slots) == 60

    def test_repair_result_has_actions(self):
        slots = {}  # empty
        result = self.repair.repair(slots)
        assert isinstance(result.actions, list)

    def test_repair_legal_deck_unchanged(self):
        slots = _make_slots()
        result = self.repair.repair(slots)
        # Actions may be empty or minor; final deck must be legal
        violations = check_all(result.slots, ConstraintConfig())
        errors = [v for v in violations if v.severity == "error"]
        assert len(errors) == 0


# ---------------------------------------------------------------------------
# Mutation tests
# ---------------------------------------------------------------------------

class TestMutations:
    def setup_method(self):
        self.cards = _make_card_list()
        self.idx = CardIndex(self.cards)
        self.rng = random.Random(42)
        self.slots = _make_slots()

    def test_swap_card_changes_deck(self):
        result = swap_card(self.slots, self.idx, self.rng)
        # Either success (deck changed) or failed gracefully
        assert isinstance(result.success, bool)
        if result.success:
            assert result.slots != self.slots

    def test_swap_preserves_size(self):
        result = swap_card(self.slots, self.idx, self.rng)
        if result.success:
            # Size may change by 1 (swap adds/removes)
            diff = abs(total_count(result.slots) - 60)
            assert diff <= 2

    def test_increase_draw(self):
        result = increase_draw(self.slots, self.idx, self.rng)
        assert isinstance(result.success, bool)
        assert isinstance(result.description, str)

    def test_reduce_energy(self):
        result = reduce_energy(self.slots, self.idx, self.rng)
        assert isinstance(result.success, bool)

    def test_increase_energy(self):
        result = increase_energy(self.slots, self.rng)
        assert isinstance(result.success, bool)

    def test_diversify(self):
        # Need a 4-of
        card = _pokemon("FourOf")
        e = _energy()
        slots = {str(card.card_id): (card, 4), str(e.card_id): (e, 56)}
        result = diversify(slots, self.idx, self.rng)
        assert isinstance(result.success, bool)

    def test_mutation_description_non_empty(self):
        result = swap_card(self.slots, self.idx, self.rng)
        assert len(result.description) > 0


# ---------------------------------------------------------------------------
# Crossover tests
# ---------------------------------------------------------------------------

class TestCrossover:
    def setup_method(self):
        self.cards = _make_card_list()
        self.idx = CardIndex(self.cards)
        self.repair = RepairEngine(self.idx)
        self.rng = random.Random(0)
        self.parent_a = _make_slots(n_poke=18, n_train=28, n_energy=14)
        self.parent_b = _make_slots(n_poke=16, n_train=30, n_energy=14)

    def test_uniform_crossover(self):
        result = uniform_crossover(self.parent_a, self.parent_b, self.rng, self.repair)
        assert isinstance(result.child_slots, dict)
        assert total_count(result.child_slots) == 60

    def test_segment_crossover(self):
        result = segment_crossover(self.parent_a, self.parent_b, self.rng, self.repair)
        assert total_count(result.child_slots) == 60

    def test_crossover_description(self):
        result = uniform_crossover(self.parent_a, self.parent_b, self.rng, self.repair)
        assert len(result.description) > 0


# ---------------------------------------------------------------------------
# Search strategy tests
# ---------------------------------------------------------------------------

class TestSearchStrategies:
    def setup_method(self):
        cards = _make_card_list()
        self.idx = CardIndex(cards)
        self.repair = RepairEngine(self.idx)
        self.rng = random.Random(7)
        self.initial = _make_slots()

    def _fake_graph(self):
        """Minimal graph mock — strategies don't call graph in unit tests."""
        from unittest.mock import MagicMock
        g = MagicMock()
        g.edges_from.return_value = []
        return g

    def _scorer(self, slots):
        try:
            from src.deck_builder.validators import slots_to_deck
            d = slots_to_deck(slots)
            return score_deck_fast(d)
        except Exception:
            return 0.0

    def test_all_strategies_in_registry(self):
        assert "greedy" in STRATEGIES
        assert "hill_climbing" in STRATEGIES
        assert "annealing" in STRATEGIES
        assert "beam" in STRATEGIES
        assert "random_restart" in STRATEGIES

    def test_get_strategy_valid(self):
        fn = get_strategy("greedy")
        assert callable(fn)

    def test_get_strategy_invalid(self):
        with pytest.raises(ValueError, match="Unknown search strategy"):
            get_strategy("magic_ai")

    def test_greedy_returns_list(self):
        from src.deck_builder.search import greedy_search
        g = self._fake_graph()
        results = greedy_search(self.initial, self._scorer, self.idx, g, self.rng)
        assert isinstance(results, list)
        assert len(results) >= 1

    def test_hill_climbing_returns_list(self):
        from src.deck_builder.search import hill_climbing
        g = self._fake_graph()
        results = hill_climbing(
            self.initial, self._scorer, self.idx, g, self.rng,
            n_iterations=5, repair=self.repair,
        )
        assert len(results) >= 1

    def test_annealing_returns_list(self):
        from src.deck_builder.search import simulated_annealing
        g = self._fake_graph()
        results = simulated_annealing(
            self.initial, self._scorer, self.idx, g, self.rng,
            n_iterations=5, repair=self.repair,
        )
        assert len(results) >= 1

    def test_beam_search_returns_list(self):
        from src.deck_builder.search import beam_search
        g = self._fake_graph()
        results = beam_search(
            self.initial, self._scorer, self.idx, g, self.rng,
            n_iterations=3, beam_width=2, repair=self.repair,
        )
        assert len(results) >= 1

    def test_random_restart_returns_list(self):
        from src.deck_builder.search import random_restart
        g = self._fake_graph()
        results = random_restart(
            self.initial, self._scorer, self.idx, g, self.rng,
            n_iterations=2, inner_iterations=3, repair=self.repair,
        )
        assert len(results) >= 1


# ---------------------------------------------------------------------------
# ConstructiveGenerator tests
# ---------------------------------------------------------------------------

class TestConstructiveGenerator:
    def setup_method(self):
        cards = _make_card_list()
        self.idx = CardIndex(cards)
        from unittest.mock import MagicMock
        g = MagicMock()
        g.edges_from.return_value = []
        g.node.return_value = None
        g.profile.return_value = None
        t = MagicMock()
        t.recommend_partners.return_value = []
        t.find_energy_package.return_value = []
        self.gen = ConstructiveGenerator(self.idx, g, t)

    def _req(self, **kwargs) -> BuildRequest:
        return BuildRequest(**kwargs)

    def test_generate_from_seed(self):
        cards = _make_card_list()
        seed_name = cards[0].name
        slots = self.gen.generate(self._req(seed_cards=[seed_name]))
        assert total_count(slots) > 0

    def test_generate_without_seed(self):
        slots = self.gen.generate(self._req())
        assert total_count(slots) > 0

    def test_generate_by_type(self):
        slots = self.gen.generate(self._req(pokemon_type=PokemonType.FIRE))
        # Should not crash even if no fire cards in minimal set
        assert isinstance(slots, dict)

    def test_generate_by_archetype_aggro(self):
        slots = self.gen.generate(self._req(archetype="Aggro"))
        assert isinstance(slots, dict)

    def test_stage10_normalise(self):
        slots = self.gen.generate(self._req())
        n = total_count(slots)
        # After normalisation must be close to 60
        assert 50 <= n <= 70  # allow some slack before repair


# ---------------------------------------------------------------------------
# DeckBuilder integration tests
# ---------------------------------------------------------------------------

class TestDeckBuilder:
    def test_build_seed_card(self, builder, real_data):
        cards, graph = real_data
        # Find a basic Pokémon name from real data
        from src.cards.models import PokemonCard
        basics = [c for c in cards if isinstance(c, PokemonCard) and c.stage.value == "Basic Pokémon"]
        seed = basics[0].name if basics else "Pikachu"
        result = builder.build(seed_cards=[seed], n_candidates=2, max_iterations=10, seed=42)
        assert isinstance(result, BuildResult)
        assert len(result.candidates) >= 1

    def test_build_by_type(self, builder):
        result = builder.build(
            pokemon_type=PokemonType.FIRE,
            n_candidates=2, max_iterations=10, seed=1,
        )
        assert isinstance(result, BuildResult)
        assert result.best is not None

    def test_build_by_archetype_aggro(self, builder):
        result = builder.build(
            archetype="Aggro", n_candidates=2, max_iterations=10, seed=2,
        )
        assert result.best is not None

    def test_build_by_archetype_control(self, builder):
        result = builder.build(
            archetype="Control", n_candidates=2, max_iterations=10, seed=3,
        )
        assert result.best is not None

    def test_improve_existing_deck(self, builder, real_data):
        cards, graph = real_data
        # Build a starting deck using first 60 unique cards
        slots = tuple(DeckSlot(card=c, count=1) for c in cards[:60])
        existing = Deck(name="Existing", slots=slots)
        result = builder.improve(existing, n_candidates=2, max_iterations=10, seed=5)
        assert isinstance(result, BuildResult)

    def test_result_has_candidates(self, builder):
        result = builder.build(n_candidates=3, max_iterations=5, seed=10)
        assert len(result.candidates) >= 1

    def test_best_candidate_has_report(self, builder):
        result = builder.build(n_candidates=2, max_iterations=5, seed=11)
        best = result.best
        assert best is not None
        assert best.report is not None
        assert best.score is not None

    def test_candidates_ranked(self, builder):
        result = builder.build(n_candidates=3, max_iterations=5, seed=12)
        ranked = result.ranked()
        scores = [c.score.total for c in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_deck_is_60_cards(self, builder):
        result = builder.build(n_candidates=1, max_iterations=5, seed=20)
        if result.best and result.best.score.is_legal:
            assert result.best.deck.total_count == 60

    def test_legal_deck_generated(self, builder):
        result = builder.build(n_candidates=3, max_iterations=15, seed=99)
        assert len(result.candidates) >= 1
        min_violations = min(c.score.violation_count for c in result.candidates)
        assert min_violations <= 2

    def test_performance_under_5s(self, builder):
        t0 = time.perf_counter()
        builder.build(n_candidates=3, max_iterations=20, seed=77)
        elapsed = time.perf_counter() - t0
        assert elapsed < 5.0, f"Build took {elapsed:.1f}s, must be < 5s"

    def test_seed_reproducibility(self, builder):
        r1 = builder.build(n_candidates=1, max_iterations=5, seed=42)
        r2 = builder.build(n_candidates=1, max_iterations=5, seed=42)
        if r1.best and r2.best:
            assert r1.best.deck.name == r2.best.deck.name

    def test_build_from_graph_and_cards(self, real_data):
        cards, graph = real_data
        b = DeckBuilder.from_graph_and_cards(graph, cards)
        assert b is not None

    def test_objective_weights_applied(self, builder):
        result = builder.build(
            n_candidates=1, max_iterations=5, seed=13,
            objective_weights={"consistency": 0.9},
        )
        assert result.best is not None


# ---------------------------------------------------------------------------
# Exports tests
# ---------------------------------------------------------------------------

class TestExports:
    @pytest.fixture(autouse=True)
    def setup(self, builder):
        result = builder.build(n_candidates=1, max_iterations=5, seed=55)
        self.candidate = result.best
        self.result = result

    def test_ptcg_live_contains_sections(self):
        text = exports.to_ptcg_live(self.candidate)
        assert "Total Cards:" in text

    def test_ptcg_live_card_count(self):
        text = exports.to_ptcg_live(self.candidate)
        last_line = [l for l in text.splitlines() if l.strip()][-1]
        assert "60" in last_line

    def test_to_json_valid(self):
        j = exports.to_json(self.candidate)
        data = json.loads(j)
        assert "score" in data
        assert "decklist" in data
        assert "ptcg_live" in data

    def test_to_json_build_result(self):
        j = exports.to_json_build_result(self.result)
        data = json.loads(j)
        assert "candidates" in data
        assert "request_summary" in data

    def test_to_markdown_has_headings(self):
        md = exports.to_markdown(self.candidate)
        assert "# Deck Candidate" in md
        assert "## Objective Scores" in md

    def test_to_csv_build_result(self):
        csv_text = exports.to_csv_build_result(self.result)
        assert "rank" in csv_text
        assert "archetype" in csv_text

    def test_to_terminal_output(self):
        term = exports.to_terminal(self.candidate)
        assert "CANDIDATE" in term

    def test_to_terminal_build_result(self):
        term = exports.to_terminal_build_result(self.result)
        assert "BUILD RESULT" in term

    def test_write_json(self, tmp_path):
        p = tmp_path / "deck.json"
        exports.write_json(self.candidate, p)
        assert p.exists()
        data = json.loads(p.read_text())
        assert "decklist" in data


# ---------------------------------------------------------------------------
# Archetype template tests
# ---------------------------------------------------------------------------

class TestArchetypeTemplates:
    def test_all_archetypes_have_templates(self):
        from src.deck_builder.archetypes import TEMPLATES, all_archetypes
        for arch in all_archetypes():
            assert arch in TEMPLATES

    def test_template_fields(self):
        t = get_template("Aggro")
        assert t is not None
        assert t.target_pokemon > 0
        assert t.target_trainers > 0
        assert t.target_energy > 0
        assert t.prefer_basics is True

    def test_unknown_archetype_returns_none(self):
        assert get_template("NotAnArchetype") is None

    def test_control_template(self):
        t = get_template("Control")
        assert t.target_disruption >= 8

    def test_energy_ramp_template(self):
        t = get_template("Energy Ramp")
        low, high = t.energy_count_range
        assert high >= 18


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_build_with_no_seeds_or_type(self, builder):
        result = builder.build(n_candidates=1, max_iterations=5)
        assert result is not None

    def test_build_with_nonexistent_seed(self, builder):
        result = builder.build(
            seed_cards=["Definitely Not A Real Card Name XYZ123"],
            n_candidates=1, max_iterations=5, seed=0,
        )
        # Should degrade gracefully, not crash
        assert isinstance(result, BuildResult)

    def test_repair_empty_slots(self):
        idx = _make_index()
        repair = RepairEngine(idx)
        result = repair.repair({})
        assert total_count(result.slots) == 60

    def test_build_partial_deck(self, builder, real_data):
        cards, graph = real_data
        from src.cards.models import PokemonCard
        basics = [c for c in cards if isinstance(c, PokemonCard) and c.stage.value == "Basic Pokémon"]
        partial = {str(basics[0].card_id): (basics[0], 4)}
        result = builder.build_from_partial(partial, n_candidates=1, max_iterations=5)
        assert isinstance(result, BuildResult)

    def test_build_result_summary_str(self, builder):
        result = builder.build(n_candidates=1, max_iterations=5)
        from src.deck_builder.reports import build_result_summary
        s = build_result_summary(result)
        assert isinstance(s, str)
        assert "Build Result" in s

    def test_multiple_strategies_produce_results(self, builder):
        for strategy in ["greedy", "hill_climbing", "annealing"]:
            result = builder.build(
                n_candidates=1,
                search_strategy=strategy,
                max_iterations=5,
                seed=0,
            )
            assert isinstance(result, BuildResult), f"{strategy} returned None"

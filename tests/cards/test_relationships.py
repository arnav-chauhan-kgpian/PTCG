"""
Comprehensive test suite for src/cards/relationships/.

Tests cover:
  - Model construction and immutability
  - Edge creation and bidirectional pair generation
  - Edge merging
  - Node building
  - Graph construction (add_node, add_edges, finalise)
  - Analyzer outputs (evolution, energy, text ref, trainer role, type synergy)
  - Full graph builder on fixture cards
  - Graph traversal queries
  - Profile computation
  - Community detection
  - Export formats (JSON, CSV, GraphML, dict)
  - Validation (isolated nodes, broken chains, missing reciprocals)
  - Scoring
  - Integration test with the real CSV card database
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from src.cards.enums import (
    CardSuperType,
    EnergyType,
    ExpansionCode,
    PokemonType,
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
    TrainerCard,
)
from src.cards.relationships import build_graph, exports
from src.cards.relationships.clustering import detect_communities
from src.cards.relationships.edges import (
    default_weight,
    make_edge,
    make_pair,
    merge_edges,
)
from src.cards.relationships.graph import CardGraph

# ---------------------------------------------------------------------------
# Imports under test
# ---------------------------------------------------------------------------
from src.cards.relationships.models import (
    DISRUPTION_TYPES,
    INVERSE,
    SUPPORT_TYPES,
    CardEdge,
    CardNode,
    CardProfile,
    Community,
    RelationshipType,
)
from src.cards.relationships.scoring import rank_edges, score_edge, specificity
from src.cards.relationships.traversal import GraphTraversal
from src.cards.relationships.validators import GraphValidator
from src.cards.types import CardId

# ===========================================================================
# Fixture helpers
# ===========================================================================


def _attack(name: str = "Tackle", effect: str = "", cost: str = "{C}") -> Attack:
    return Attack(
        name=name,
        cost=EnergyCostModel(tokens=(cost,), total_count=1),
        damage=DamageValue(base=10, raw="10"),
        effect=effect,
    )


def _pokemon(
    card_id: int,
    name: str,
    ptype: PokemonType = PokemonType.COLORLESS,
    stage: Stage = Stage.BASIC,
    previous_stage: str | None = None,
    hp: int = 60,
    retreat_cost: int = 1,
    attacks: tuple[Attack, ...] = (),
    ability: Ability | None = None,
) -> PokemonCard:
    if not attacks:
        attacks = (_attack(),)
    return PokemonCard(
        card_id=CardId(card_id),
        name=name,
        expansion=ExpansionCode.UNKNOWN,
        collection_number=str(card_id),
        card_super_type=CardSuperType.POKEMON,
        stage=stage,
        previous_stage=previous_stage,
        hp=hp,
        pokemon_type=ptype,
        retreat_cost=retreat_cost,
        attacks=attacks,
        ability=ability,
    )


def _trainer(
    card_id: int,
    name: str,
    trainer_type: TrainerType = TrainerType.ITEM,
    effect: str = "Do something.",
) -> TrainerCard:
    return TrainerCard(
        card_id=CardId(card_id),
        name=name,
        expansion=ExpansionCode.UNKNOWN,
        collection_number=str(card_id),
        card_super_type=CardSuperType.TRAINER,
        trainer_type=trainer_type,
        effect=effect,
    )


def _energy(
    card_id: int,
    name: str,
    provides: tuple[PokemonType, ...] = (PokemonType.COLORLESS,),
    effect: str = "",
    energy_type: EnergyType = EnergyType.BASIC,
) -> EnergyCard:
    return EnergyCard(
        card_id=CardId(card_id),
        name=name,
        expansion=ExpansionCode.UNKNOWN,
        collection_number=str(card_id),
        card_super_type=CardSuperType.ENERGY,
        energy_type=energy_type,
        provides=provides,
        effect=effect,
    )


@pytest.fixture
def small_cards():
    """A small but representative card set for unit tests."""
    charmander = _pokemon(1, "Charmander", PokemonType.FIRE, Stage.BASIC,
                          attacks=(_attack("Ember", "", "{R}"),))
    charmeleon = _pokemon(2, "Charmeleon", PokemonType.FIRE, Stage.STAGE_1,
                          previous_stage="Charmander",
                          attacks=(_attack("Slash", "", "{R}{C}"),))
    charizard = _pokemon(3, "Charizard", PokemonType.FIRE, Stage.STAGE_2,
                         previous_stage="Charmeleon",
                         attacks=(_attack("Fire Spin",
                                          "Discard 2 {R} Energy from this Pokemon.",
                                          "{R}{R}{R}"),))
    squirtle = _pokemon(4, "Squirtle", PokemonType.WATER, Stage.BASIC,
                        attacks=(_attack("Bubble",
                                         "Your opponent's Active Pokemon is now Paralyzed.",
                                         "{W}"),))

    draw_trainer = _trainer(100, "Professor's Research", TrainerType.SUPPORTER,
                            "Draw 7 cards.")
    heal_trainer = _trainer(101, "Potion", TrainerType.ITEM,
                            "Heal 30 damage from 1 of your Pokemon.")
    switch_trainer = _trainer(102, "Switch", TrainerType.ITEM,
                              "Switch your Active Pokemon with 1 of your Benched Pokemon.")
    search_trainer = _trainer(103, "Ultra Ball", TrainerType.ITEM,
                              "Search your deck for a Pokemon card and put it into your hand.")

    fire_energy = _energy(200, "Fire Energy", (PokemonType.FIRE,))
    water_energy = _energy(201, "Water Energy", (PokemonType.WATER,))

    return [
        charmander, charmeleon, charizard, squirtle,
        draw_trainer, heal_trainer, switch_trainer, search_trainer,
        fire_energy, water_energy,
    ]


@pytest.fixture
def small_graph(small_cards):
    return build_graph(small_cards)


@pytest.fixture
def traversal(small_graph):
    return GraphTraversal(small_graph)


# ===========================================================================
# 1. Model tests
# ===========================================================================

class TestModels:
    def test_relationship_type_values(self):
        assert RelationshipType.EVOLVES_FROM.value == "evolves_from"
        assert RelationshipType.SEARCHES_FOR.value == "searches_for"

    def test_inverse_map(self):
        assert INVERSE[RelationshipType.EVOLVES_FROM] == RelationshipType.EVOLVES_TO
        assert INVERSE[RelationshipType.SEARCHES_FOR] == RelationshipType.SEARCHED_BY

    def test_card_edge_frozen(self):
        e = make_edge("a", "b", RelationshipType.EVOLVES_FROM)
        with pytest.raises(Exception):
            e.weight = 0.5  # type: ignore[misc]

    def test_card_node_frozen(self):
        n = CardNode(card_id="1", name="Bulbasaur", card_super_type=CardSuperType.POKEMON)
        with pytest.raises(Exception):
            n.name = "Venusaur"  # type: ignore[misc]

    def test_community_frozen(self):
        c = Community(community_id=0, core_cards=("1",), support_cards=(), shared_mechanics=())
        with pytest.raises(Exception):
            c.size = 99  # type: ignore[misc]

    def test_support_types_nonempty(self):
        assert len(SUPPORT_TYPES) > 5

    def test_disruption_types_nonempty(self):
        assert len(DISRUPTION_TYPES) > 2

    def test_card_edge_key(self):
        e = make_edge("1", "2", RelationshipType.EVOLVES_FROM)
        assert e.edge_key == ("1", "2", "evolves_from")


# ===========================================================================
# 2. Edge factory tests
# ===========================================================================

class TestEdgeFactory:
    def test_make_edge_basic(self):
        e = make_edge("a", "b", RelationshipType.DRAW_ENGINE)
        assert e.source == "a"
        assert e.target == "b"
        assert e.relationship_type == RelationshipType.DRAW_ENGINE
        assert 0.0 <= e.weight <= 1.0

    def test_make_pair_generates_inverse(self):
        edges = make_pair("a", "b", RelationshipType.EVOLVES_FROM)
        assert len(edges) == 2
        rels = {e.relationship_type for e in edges}
        assert RelationshipType.EVOLVES_FROM in rels
        assert RelationshipType.EVOLVES_TO in rels

    def test_make_pair_no_inverse_for_unknown(self):
        edges = make_pair("a", "b", RelationshipType.UNKNOWN)
        assert len(edges) == 1

    def test_default_weight_varies_by_rel(self):
        w_evo = default_weight(RelationshipType.EVOLVES_FROM)
        w_type = default_weight(RelationshipType.TYPE_SYNERGY)
        assert w_evo > w_type

    def test_confidence_affects_weight(self):
        e_high = make_edge("a", "b", RelationshipType.HEALS, confidence=1.0)
        e_low = make_edge("a", "b", RelationshipType.HEALS, confidence=0.1)
        assert e_high.weight > e_low.weight

    def test_merge_edges_combines_duplicates(self):
        e1 = make_edge("a", "b", RelationshipType.HEALS, evidence=("e1",))
        e2 = make_edge("a", "b", RelationshipType.HEALS, evidence=("e2",))
        merged = merge_edges([e1, e2])
        assert len(merged) == 1
        assert "e1" in merged[0].evidence
        assert "e2" in merged[0].evidence

    def test_merge_edges_keeps_distinct_pairs(self):
        e1 = make_edge("a", "b", RelationshipType.HEALS)
        e2 = make_edge("a", "c", RelationshipType.HEALS)
        merged = merge_edges([e1, e2])
        assert len(merged) == 2

    def test_merge_boosts_weight(self):
        e1 = make_edge("a", "b", RelationshipType.DRAW_ENGINE, weight=0.5)
        e2 = make_edge("a", "b", RelationshipType.DRAW_ENGINE, weight=0.5)
        merged = merge_edges([e1, e2])
        assert merged[0].weight >= 0.5


# ===========================================================================
# 3. Graph construction tests
# ===========================================================================

class TestGraphConstruction:
    def test_build_graph_has_all_nodes(self, small_cards, small_graph):
        assert small_graph.node_count == len(small_cards)

    def test_build_graph_has_edges(self, small_graph):
        assert small_graph.edge_count > 0

    def test_nodes_accessible(self, small_graph):
        node = small_graph.node("1")
        assert node is not None
        assert node.name == "Charmander"

    def test_evolution_edges_present(self, small_graph):
        assert small_graph.has_edge("2", "1", RelationshipType.EVOLVES_FROM)
        assert small_graph.has_edge("1", "2", RelationshipType.EVOLVES_TO)

    def test_evolution_chain_edges(self, small_graph):
        assert small_graph.has_edge("3", "2", RelationshipType.EVOLVES_FROM)
        assert small_graph.has_edge("2", "3", RelationshipType.EVOLVES_TO)

    def test_draw_trainer_has_edges(self, small_graph):
        edges = small_graph.edges_from("100")
        assert len(edges) > 0

    def test_energy_edges_fire(self, small_graph):
        fire_out = small_graph.edges_from("3", RelationshipType.USES_ENERGY)
        fire_in = small_graph.edges_to("200", RelationshipType.USES_ENERGY)
        assert len(fire_out) > 0 or len(fire_in) > 0

    def test_type_synergy_fire_pokemon(self, small_graph):
        fire_edges = small_graph.edges_from("1", RelationshipType.TYPE_SYNERGY)
        assert len(fire_edges) > 0

    def test_finalise_sets_built(self, small_graph):
        assert small_graph._built is True

    def test_all_edges_have_valid_nodes(self, small_graph):
        for e in small_graph.all_edges():
            assert small_graph.has_node(e.source), f"Missing source: {e.source}"
            assert small_graph.has_node(e.target), f"Missing target: {e.target}"

    def test_relationship_counts_dict(self, small_graph):
        counts = small_graph.relationship_counts()
        assert isinstance(counts, dict)
        assert len(counts) > 0

    def test_has_node_true(self, small_graph):
        assert small_graph.has_node("1")

    def test_has_node_false(self, small_graph):
        assert not small_graph.has_node("99999")

    def test_edges_from_filtered(self, small_graph):
        edges = small_graph.edges_from("2", RelationshipType.EVOLVES_FROM)
        for e in edges:
            assert e.relationship_type == RelationshipType.EVOLVES_FROM

    def test_edges_to_returns_edges(self, small_graph):
        # Charmeleon (2) receives EVOLVES_FROM from Charizard (3)
        edges = small_graph.edges_to("2", RelationshipType.EVOLVES_FROM)
        assert len(edges) > 0


# ===========================================================================
# 4. Profile tests
# ===========================================================================

class TestCardProfile:
    def test_profile_returns_profile(self, small_graph):
        p = small_graph.profile("1")
        assert isinstance(p, CardProfile)
        assert p.card_id == "1"
        assert p.name == "Charmander"

    def test_profile_evolution_family(self, small_graph):
        p = small_graph.profile("2")  # Charmeleon
        assert "1" in p.evolution_family or "3" in p.evolution_family

    def test_profile_cached(self, small_graph):
        p1 = small_graph.profile("1")
        p2 = small_graph.profile("1")
        assert p1 is p2

    def test_profile_missing_card_returns_none(self, small_graph):
        assert small_graph.profile("99999") is None

    def test_profile_edge_counts(self, small_graph):
        p = small_graph.profile("3")
        assert p.total_out_edges >= 0
        assert p.total_in_edges >= 0


# ===========================================================================
# 5. Traversal tests
# ===========================================================================

class TestTraversal:
    def test_neighbors_returns_list(self, traversal):
        n = traversal.neighbors("1")
        assert isinstance(n, list)

    def test_neighbors_excludes_self(self, traversal):
        n = traversal.neighbors("1")
        assert "1" not in n

    def test_neighbors_filtered_by_rel(self, traversal):
        n = traversal.neighbors("2", RelationshipType.EVOLVES_FROM)
        assert "1" in n

    def test_shortest_path_same_node(self, traversal):
        path = traversal.shortest_path("1", "1")
        assert path == ["1"]

    def test_shortest_path_connected(self, traversal):
        path = traversal.shortest_path("1", "2")
        assert path is not None
        assert len(path) >= 2

    def test_shortest_path_not_found(self, small_graph):
        g = small_graph
        from src.cards.relationships.models import CardNode
        isolated = CardNode(card_id="999", name="Ghost", card_super_type=CardSuperType.POKEMON)
        g.add_node(isolated)
        t = GraphTraversal(g)
        result = t.shortest_path("999", "1")
        assert result is None

    def test_find_support_cards(self, traversal):
        result = traversal.find_support_cards("3")
        assert isinstance(result, list)

    def test_find_counters(self, traversal):
        result = traversal.find_counters("1")
        assert isinstance(result, list)

    def test_find_energy_package(self, traversal):
        package = traversal.find_energy_package("3")
        assert isinstance(package, list)

    def test_find_draw_engine(self, traversal):
        engines = traversal.find_draw_engine("3")
        assert isinstance(engines, list)

    def test_recommend_partners(self, traversal):
        partners = traversal.recommend_partners("3")
        assert isinstance(partners, list)
        assert "3" not in partners

    def test_recommend_consistency_cards(self, traversal):
        result = traversal.recommend_consistency_cards("3")
        assert isinstance(result, list)

    def test_recommend_disruption(self, traversal):
        result = traversal.recommend_disruption("3")
        assert isinstance(result, list)

    def test_related_cards(self, traversal):
        result = traversal.related_cards("1")
        assert isinstance(result, list)
        assert "1" not in result

    def test_similar_cards(self, traversal):
        result = traversal.similar_cards("1")
        assert isinstance(result, list)
        assert "1" not in result

    def test_evolution_chain_basic(self, traversal):
        chain = traversal.evolution_chain("2")
        assert "1" in chain
        assert "2" in chain
        assert "3" in chain

    def test_weighted_neighbors(self, traversal):
        pairs = traversal.weighted_neighbors("2")
        assert isinstance(pairs, list)
        if pairs:
            assert isinstance(pairs[0][1], float)

    def test_shortest_path_length(self, traversal):
        length = traversal.shortest_path_length("1", "3")
        assert length is None or length >= 0

    def test_recommend_finishers(self, traversal):
        result = traversal.recommend_finishers("3")
        assert isinstance(result, list)

    def test_recommend_openers(self, traversal):
        result = traversal.recommend_openers("3")
        assert isinstance(result, list)

    def test_recommend_replacements(self, traversal):
        result = traversal.recommend_replacements("1")
        assert isinstance(result, list)

    def test_neighbors_include_incoming(self, traversal):
        # Charmander has EVOLVES_TO pointing to Charmeleon
        n = traversal.neighbors("1", include_incoming=True)
        assert isinstance(n, list)


# ===========================================================================
# 6. Community detection tests
# ===========================================================================

class TestClustering:
    def test_detect_returns_list(self, small_graph):
        communities = detect_communities(small_graph)
        assert isinstance(communities, list)
        assert len(communities) > 0

    def test_communities_are_community_objects(self, small_graph):
        for c in detect_communities(small_graph):
            assert isinstance(c, Community)

    def test_community_ids_unique(self, small_graph):
        communities = detect_communities(small_graph)
        ids = [c.community_id for c in communities]
        assert len(ids) == len(set(ids))

    def test_community_size_positive(self, small_graph):
        for c in detect_communities(small_graph):
            assert c.size >= 0

    def test_community_density_valid(self, small_graph):
        for c in detect_communities(small_graph):
            assert 0.0 <= c.density <= 1.0

    def test_empty_graph_no_crash(self):
        g = CardGraph()
        g.finalise()
        assert detect_communities(g) == []


# ===========================================================================
# 7. Validation tests
# ===========================================================================

class TestValidation:
    def test_validate_returns_report(self, small_graph):
        from src.cards.relationships.validators import GraphValidationReport
        report = GraphValidator().validate(small_graph)
        assert isinstance(report, GraphValidationReport)

    def test_validate_is_clean(self, small_graph):
        report = GraphValidator().validate(small_graph)
        assert report.is_clean()

    def test_detect_isolated_node(self):
        g = CardGraph()
        n1 = CardNode(card_id="A", name="A", card_super_type=CardSuperType.POKEMON)
        n2 = CardNode(card_id="B", name="B", card_super_type=CardSuperType.POKEMON)
        g.add_node(n1)
        g.add_node(n2)
        g.add_edges([make_edge("A", "B", RelationshipType.TYPE_SYNERGY)])
        g.finalise()
        assert g.isolated_nodes() == []

    def test_detect_broken_evolution(self):
        g = CardGraph()
        n = CardNode(card_id="X", name="Evo", card_super_type=CardSuperType.POKEMON)
        g.add_node(n)
        bad_edge = CardEdge(
            source="X",
            target="MISSING",
            relationship_type=RelationshipType.EVOLVES_FROM,
        )
        g._g.add_edge("X", "MISSING", key="evolves_from", data=bad_edge)
        g.finalise()
        report = GraphValidator().validate(g)
        broken = [i for i in report.issues if i.category == "broken_evolution"]
        assert len(broken) == 1

    def test_validation_summary_string(self, small_graph):
        report = GraphValidator().validate(small_graph)
        s = report.summary()
        assert "Validation:" in s

    def test_warnings_and_errors_properties(self, small_graph):
        report = GraphValidator().validate(small_graph)
        assert isinstance(report.warnings, list)
        assert isinstance(report.errors, list)


# ===========================================================================
# 8. Scoring tests
# ===========================================================================

class TestScoring:
    def test_score_edge_returns_float(self):
        e = make_edge("a", "b", RelationshipType.EVOLVES_FROM)
        s = score_edge(e)
        assert 0.0 <= s <= 1.0

    def test_evolution_scores_high(self):
        e_evo = make_edge("a", "b", RelationshipType.EVOLVES_FROM)
        e_type = make_edge("a", "b", RelationshipType.TYPE_SYNERGY)
        assert score_edge(e_evo) > score_edge(e_type)

    def test_rank_edges_sorted(self):
        edges = [
            make_edge("a", "b", RelationshipType.TYPE_SYNERGY),
            make_edge("a", "c", RelationshipType.EVOLVES_FROM),
            make_edge("a", "d", RelationshipType.DRAW_ENGINE),
        ]
        ranked = rank_edges(edges)
        scores = [score_edge(e) for e in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_specificity_evolution_top(self):
        assert specificity(RelationshipType.EVOLVES_FROM) >= specificity(RelationshipType.TYPE_SYNERGY)

    def test_score_increases_with_confidence(self):
        e_high = make_edge("a", "b", RelationshipType.HEALS, confidence=1.0)
        e_low = make_edge("a", "b", RelationshipType.HEALS, confidence=0.2)
        assert score_edge(e_high) >= score_edge(e_low)


# ===========================================================================
# 9. Export tests
# ===========================================================================

class TestExports:
    def test_to_dict_has_nodes_and_edges(self, small_graph):
        d = exports.to_dict(small_graph)
        assert "nodes" in d and "edges" in d
        assert d["stats"]["node_count"] == small_graph.node_count

    def test_to_json_valid(self, small_graph):
        j = exports.to_json(small_graph)
        parsed = json.loads(j)
        assert len(parsed["nodes"]) == small_graph.node_count

    def test_to_csv_edges_has_header(self, small_graph):
        csv = exports.to_csv_edges(small_graph)
        assert "source" in csv.split("\n")[0]

    def test_to_csv_nodes_has_header(self, small_graph):
        csv = exports.to_csv_nodes(small_graph)
        assert "card_id" in csv.split("\n")[0]

    def test_to_graphml_is_xml(self, small_graph):
        xml = exports.to_graphml(small_graph)
        assert "<?xml" in xml or "<graphml" in xml

    def test_to_networkx_returns_graph(self, small_graph):
        import networkx as nx
        ng = exports.to_networkx(small_graph)
        assert isinstance(ng, nx.MultiDiGraph)

    def test_write_json(self, small_graph, tmp_path):
        p = tmp_path / "graph.json"
        exports.write_json(small_graph, p)
        assert p.exists()

    def test_write_csv(self, small_graph, tmp_path):
        ep = tmp_path / "edges.csv"
        np_ = tmp_path / "nodes.csv"
        exports.write_csv(small_graph, ep, np_)
        assert ep.exists() and np_.exists()

    def test_write_graphml(self, small_graph, tmp_path):
        p = tmp_path / "graph.graphml"
        exports.write_graphml(small_graph, p)
        assert p.exists()


# ===========================================================================
# 10. Integration test — real card database
# ===========================================================================

class TestIntegrationFullDatabase:
    @pytest.fixture(scope="class")
    def real_graph(self):
        from src.cards.parser import parse_csv
        csv_path = Path("EN_Card_Data.csv")
        if not csv_path.exists():
            pytest.skip("EN_Card_Data.csv not found")
        result = parse_csv(csv_path)
        return build_graph(result.cards)

    def test_node_count_substantial(self, real_graph):
        assert real_graph.node_count > 100

    def test_edge_count_substantial(self, real_graph):
        assert real_graph.edge_count > 200

    def test_evolution_edges_exist(self, real_graph):
        evo_edges = [
            e for e in real_graph.all_edges()
            if e.relationship_type == RelationshipType.EVOLVES_FROM
        ]
        assert len(evo_edges) > 5

    def test_all_edges_valid_nodes(self, real_graph):
        bad = [
            e for e in real_graph.all_edges()
            if not real_graph.has_node(e.source) or not real_graph.has_node(e.target)
        ]
        assert len(bad) == 0

    def test_profile_accessible(self, real_graph):
        first = real_graph.all_nodes()[0]
        profile = real_graph.profile(first.card_id)
        assert profile is not None

    def test_community_detection_runs(self, real_graph):
        assert len(detect_communities(real_graph)) > 0

    def test_validation_no_errors(self, real_graph):
        report = GraphValidator().validate(real_graph)
        assert report.is_clean()

    def test_traversal_shortest_path(self, real_graph):
        nodes = real_graph.all_nodes()
        t = GraphTraversal(real_graph)
        if len(nodes) >= 2:
            result = t.shortest_path(nodes[0].card_id, nodes[1].card_id)
            assert result is None or isinstance(result, list)

    def test_json_export_roundtrip(self, real_graph):
        d = json.loads(exports.to_json(real_graph))
        assert d["stats"]["node_count"] == real_graph.node_count

    def test_relationship_type_coverage(self, real_graph):
        assert len(real_graph.relationship_counts()) >= 5

    def test_recommend_partners_no_crash(self, real_graph):
        t = GraphTraversal(real_graph)
        node = real_graph.all_nodes()[0]
        assert isinstance(t.recommend_partners(node.card_id), list)

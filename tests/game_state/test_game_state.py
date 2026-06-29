"""
Comprehensive tests for the Game State Representation & Feature Encoding Engine
(Phase 7).
"""

from __future__ import annotations

import json
import uuid

import pytest
from src.game_state import (
    TOTAL_FEATURE_SIZE,
    TOTAL_MASK_SIZE,
    ActionMask,
    ActionRecord,
    ActionType,
    CardCategory,
    CardInstance,
    EncodedFeatures,
    EnergyTypeCode,
    FeatureEncoder,
    FeatureGroup,
    GameHistory,
    GameState,
    GameStatus,
    KnockoutRecord,
    PlayerState,
    PokemonStage,
    SpecialCondition,
    StateSnapshot,
    Zone,
    canonical_dict,
    encode,
    encode_flat,
    from_bytes,
    from_dict,
    from_json,
    instance_fingerprint,
    make_action,
    state_fingerprint,
    state_hash_int,
    to_bytes,
    to_dict,
    to_json,
    to_markdown,
    to_terminal,
    validate_state,
)
from src.game_state.features import (
    GROUP_SIZES,
    POKEMON_FEAT_SIZE,
)

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------

def _make_pokemon(
    card_id: str = "pika001",
    card_name: str = "Pikachu",
    owner: int = 0,
    base_hp: int = 60,
    stage: PokemonStage = PokemonStage.BASIC,
    zone: Zone = Zone.HAND,
    instance_id: str | None = None,
) -> CardInstance:
    return CardInstance(
        instance_id=instance_id or str(uuid.uuid4()),
        card_id=card_id,
        card_name=card_name,
        owner=owner,
        zone=zone,
        category=CardCategory.POKEMON,
        base_hp=base_hp,
        stage=stage,
        prize_value=PokemonStage.prize_value(stage),
    )


def _make_energy(
    owner: int = 0,
    energy_type: EnergyTypeCode = EnergyTypeCode.LIGHTNING,
    zone: Zone = Zone.ATTACHED,
    instance_id: str | None = None,
) -> CardInstance:
    return CardInstance(
        instance_id=instance_id or str(uuid.uuid4()),
        card_id="e-lightning",
        card_name="Lightning Energy",
        owner=owner,
        zone=zone,
        category=CardCategory.ENERGY_BASIC,
    )


def _make_trainer(
    card_name: str = "Potion",
    owner: int = 0,
    category: CardCategory = CardCategory.TRAINER_ITEM,
    instance_id: str | None = None,
) -> CardInstance:
    return CardInstance(
        instance_id=instance_id or str(uuid.uuid4()),
        card_id="potion001",
        card_name=card_name,
        owner=owner,
        zone=Zone.HAND,
        category=category,
    )


def _make_simple_state() -> GameState:
    """A minimal valid 2-player game in progress."""
    pika_id = "pika-active-p0"
    charm_id = "charm-active-p1"
    bench_id = "bulb-bench-p0"
    e1_id = "energy-1"
    e2_id = "energy-2"

    pika = _make_pokemon("pika001", "Pikachu", 0, 70, zone=Zone.ACTIVE, instance_id=pika_id)
    charm = _make_pokemon("char001", "Charmander", 1, 50, zone=Zone.ACTIVE, instance_id=charm_id)
    bench = _make_pokemon("bulb001", "Bulbasaur", 0, 60, zone=Zone.BENCH, instance_id=bench_id)
    e1 = _make_energy(0, instance_id=e1_id)
    e2 = _make_energy(0, instance_id=e2_id)

    # Attach two energies to Pikachu
    pika = pika.model_copy(update={"attached_energy_ids": (e1_id, e2_id)})

    p0 = PlayerState(
        player_id=0,
        active=pika_id,
        bench=(bench_id,),
        bench_count=1,
        hand=(),
        hand_count=4,
        deck_size=50,
        prizes_remaining=6,
    )
    p1 = PlayerState(
        player_id=1,
        active=charm_id,
        bench_count=0,
        hand_count=5,
        deck_size=52,
        prizes_remaining=6,
    )

    instances = {
        pika_id: pika,
        charm_id: charm,
        bench_id: bench,
        e1_id: e1,
        e2_id: e2,
    }

    return GameState(
        turn_number=3,
        current_player=0,
        game_status=GameStatus.ONGOING,
        players=(p0, p1),
        card_instances=instances,
    )


# -------------------------------------------------------------------------
# CardInstance tests
# -------------------------------------------------------------------------

class TestCardInstance:
    def test_creation(self):
        inst = _make_pokemon()
        assert inst.card_name == "Pikachu"
        assert inst.max_hp == 60
        assert inst.remaining_hp == 60
        assert inst.hp_ratio == 1.0
        assert not inst.is_knocked_out

    def test_damage(self):
        inst = _make_pokemon(base_hp=100)
        inst2 = inst.with_damage(40)
        assert inst2.damage_taken == 40
        assert inst2.remaining_hp == 60
        assert inst2.hp_ratio == pytest.approx(0.6)
        # Original unchanged
        assert inst.damage_taken == 0

    def test_added_damage(self):
        inst = _make_pokemon(base_hp=100).with_damage(30)
        inst2 = inst.with_added_damage(50)
        assert inst2.damage_taken == 80

    def test_knockout(self):
        inst = _make_pokemon(base_hp=100).with_damage(100)
        assert inst.is_knocked_out
        assert inst.remaining_hp == 0

    def test_hp_modifier(self):
        inst = _make_pokemon(base_hp=100)
        inst2 = inst.model_copy(update={"hp_modifier": 30})
        assert inst2.max_hp == 130

    def test_conditions(self):
        inst = _make_pokemon()
        inst2 = inst.with_condition(SpecialCondition.PARALYZED)
        assert SpecialCondition.PARALYZED in inst2.special_conditions
        inst3 = inst2.without_conditions()
        assert len(inst3.special_conditions) == 0

    def test_multiple_conditions(self):
        inst = _make_pokemon()
        inst2 = inst.with_condition(SpecialCondition.BURNED)
        inst3 = inst2.with_condition(SpecialCondition.POISONED)
        assert len(inst3.special_conditions) == 2

    def test_energy_attachment(self):
        inst = _make_pokemon()
        e = _make_energy()
        inst2 = inst.with_energy_attached(e.instance_id)
        assert e.instance_id in inst2.attached_energy_ids
        inst3 = inst2.without_energy(e.instance_id)
        assert e.instance_id not in inst3.attached_energy_ids

    def test_zone_update(self):
        inst = _make_pokemon(zone=Zone.HAND)
        inst2 = inst.with_zone(Zone.ACTIVE)
        assert inst2.zone == Zone.ACTIVE
        assert inst.zone == Zone.HAND  # original unchanged

    def test_effect_flags(self):
        inst = _make_pokemon()
        inst2 = inst.with_flag("poke_power_used")
        assert inst2.has_flag("poke_power_used")
        inst3 = inst2.with_flag("bonus_damage", "20")
        assert inst3.get_flag("bonus_damage") == "20"
        inst4 = inst3.without_flag("poke_power_used")
        assert not inst4.has_flag("poke_power_used")

    def test_frozen_immutable(self):
        inst = _make_pokemon()
        with pytest.raises(Exception):
            inst.card_name = "Raichu"  # type: ignore[misc]

    def test_factory_create_pokemon(self):
        inst = CardInstance.create_pokemon("id1", "Charizard", 0, 120, PokemonStage.STAGE_2)
        assert inst.card_name == "Charizard"
        assert inst.max_hp == 120
        assert inst.stage == PokemonStage.STAGE_2

    def test_factory_create_energy(self):
        inst = CardInstance.create_energy("e1", "Fire Energy", 0, EnergyTypeCode.FIRE, True)
        assert inst.category == CardCategory.ENERGY_BASIC

    def test_prize_value_ex(self):
        inst = _make_pokemon(stage=PokemonStage.EX)
        assert inst.prize_value == 2

    def test_prize_value_basic(self):
        inst = _make_pokemon(stage=PokemonStage.BASIC)
        assert inst.prize_value == 1


# -------------------------------------------------------------------------
# PlayerState tests
# -------------------------------------------------------------------------

class TestPlayerState:
    def test_creation(self):
        p = PlayerState(player_id=0, prizes_remaining=6, deck_size=56)
        assert p.player_id == 0
        assert not p.has_active

    def test_with_active(self):
        p = PlayerState(player_id=0)
        p2 = p.with_active("pikachu-1")
        assert p2.active == "pikachu-1"
        assert p.active is None

    def test_bench_operations(self):
        p = PlayerState(player_id=0)
        p2 = p.with_bench_added("b1").with_bench_added("b2")
        assert len(p2.bench) == 2
        assert p2.bench_count == 2
        p3 = p2.without_bench("b1")
        assert "b1" not in p3.bench
        assert p3.bench_count == 1

    def test_bench_slots_free(self):
        p = PlayerState(player_id=0, bench=("a", "b", "c"), bench_count=3)
        assert p.bench_slots_free == 2

    def test_card_drawn(self):
        p = PlayerState(player_id=0, deck_size=40, hand=(), hand_count=3)
        p2 = p.with_card_drawn("new-card")
        assert "new-card" in p2.hand
        assert p2.hand_count == 4
        assert p2.deck_size == 39

    def test_card_discarded(self):
        p = PlayerState(player_id=0, hand=("card-1",), hand_count=1, discard_count=0)
        p2 = p.with_card_discarded("card-1")
        assert "card-1" not in p2.hand
        assert "card-1" in p2.discard
        assert p2.hand_count == 0

    def test_prize_taken(self):
        p = PlayerState(player_id=0, prizes=("prize1",), prizes_remaining=1, hand_count=0)
        p2 = p.with_prize_taken("prize1")
        assert p2.prizes_remaining == 0
        assert "prize1" in p2.hand

    def test_reset_turn_flags(self):
        p = PlayerState(
            player_id=0,
            supporter_played_this_turn=True,
            energy_attached_this_turn=True,
        )
        p2 = p.reset_turn_flags()
        assert not p2.supporter_played_this_turn
        assert not p2.energy_attached_this_turn

    def test_all_pokemon_ids(self):
        p = PlayerState(player_id=0, active="a1", bench=("b1", "b2"))
        ids = p.all_pokemon_ids
        assert "a1" in ids
        assert "b1" in ids
        assert "b2" in ids


# -------------------------------------------------------------------------
# GameState tests
# -------------------------------------------------------------------------

class TestGameState:
    def test_new_game(self):
        gs = GameState.new_game()
        assert gs.game_status == GameStatus.NOT_STARTED
        assert gs.turn_number == 0
        assert len(gs.players) == 2

    def test_current_player_state(self):
        gs = _make_simple_state()
        assert gs.current_player_state.player_id == 0

    def test_opponent_state(self):
        gs = _make_simple_state()
        assert gs.opponent_player_state.player_id == 1

    def test_get_instance(self):
        gs = _make_simple_state()
        inst = gs.get_instance("pika-active-p0")
        assert inst is not None
        assert inst.card_name == "Pikachu"

    def test_with_instance(self):
        gs = _make_simple_state()
        new_pika = gs.get_instance("pika-active-p0").with_damage(20)
        gs2 = gs.with_instance(new_pika)
        assert gs2.get_instance("pika-active-p0").damage_taken == 20
        assert gs.get_instance("pika-active-p0").damage_taken == 0

    def test_with_action(self):
        gs = _make_simple_state()
        action = ActionRecord.make(ActionType.ATTACK, 0, turn=3, attack="Thunder Shock")
        gs2 = gs.with_action(action)
        assert len(gs2.action_history) == 1
        assert gs2.last_action.action_type == ActionType.ATTACK

    def test_with_next_turn(self):
        gs = _make_simple_state()
        gs2 = gs.with_next_turn()
        assert gs2.turn_number == 4
        assert gs2.current_player == 1

    def test_is_terminal(self):
        gs = _make_simple_state()
        assert not gs.is_terminal
        gs2 = gs.with_status(GameStatus.PLAYER_0_WIN, winner=0)
        assert gs2.is_terminal

    def test_with_player(self):
        gs = _make_simple_state()
        p0_new = gs.players[0].model_copy(update={"prizes_remaining": 3})
        gs2 = gs.with_player(0, p0_new)
        assert gs2.players[0].prizes_remaining == 3
        assert gs.players[0].prizes_remaining == 6

    def test_with_knockout(self):
        gs = _make_simple_state()
        ko = KnockoutRecord(
            turn=3, knocked_out_instance_id="charm-active-p1",
            knocked_out_name="Charmander", owner=1, by_player=0, prizes_taken=1,
        )
        gs2 = gs.with_knockout(ko)
        assert len(gs2.knockout_history) == 1

    def test_frozen(self):
        gs = _make_simple_state()
        with pytest.raises(Exception):
            gs.turn_number = 99  # type: ignore[misc]


# -------------------------------------------------------------------------
# Hashing tests
# -------------------------------------------------------------------------

class TestHashing:
    def test_identical_states_same_hash(self):
        gs1 = _make_simple_state()
        gs2 = _make_simple_state()
        # Note: state_ids differ, but fingerprints should differ too since
        # state_id is included in model dump but excluded from canonical_dict
        fp1 = state_fingerprint(gs1)
        # Rebuild identical state manually
        gs3 = GameState.model_validate(gs1.model_dump())
        gs3_no_id = gs3.model_copy(update={"state_id": gs1.state_id})
        assert state_fingerprint(gs3_no_id) == fp1

    def test_different_states_different_hash(self):
        gs1 = _make_simple_state()
        gs2 = gs1.with_instance(
            gs1.get_instance("pika-active-p0").with_damage(30)
        )
        assert state_fingerprint(gs1) != state_fingerprint(gs2)

    def test_hash_int_is_int(self):
        gs = _make_simple_state()
        h = state_hash_int(gs)
        assert isinstance(h, int)

    def test_canonical_dict_excludes_state_id(self):
        gs1 = _make_simple_state()
        gs2 = gs1.model_copy(update={"state_id": "different-id"})
        cd1 = canonical_dict(gs1)
        cd2 = canonical_dict(gs2)
        assert cd1 == cd2

    def test_hash_usable_as_dict_key(self):
        gs = _make_simple_state()
        d = {hash(gs): "value"}
        assert d[hash(gs)] == "value"

    def test_instance_fingerprint(self):
        inst = _make_pokemon()
        fp = instance_fingerprint(inst)
        assert isinstance(fp, str)
        assert len(fp) == 16

    def test_state_snapshot(self):
        snap = StateSnapshot()
        gs = _make_simple_state()
        fp = snap.put(gs)
        assert fp in snap
        assert snap.get(fp) is gs
        assert len(snap) == 1

    def test_state_snapshot_deduplication(self):
        snap = StateSnapshot()
        gs1 = _make_simple_state()
        gs2 = gs1.model_copy(update={"state_id": "another-id"})
        fp1 = snap.put(gs1)
        fp2 = snap.put(gs2)
        # Same board → same fingerprint → only 1 entry
        assert fp1 == fp2
        assert len(snap) == 1

    def test_canonical_dict_has_expected_keys(self):
        gs = _make_simple_state()
        cd = canonical_dict(gs)
        for key in ("turn_number", "current_player", "players", "card_instances"):
            assert key in cd

    def test_canonical_json_deterministic(self):
        import json as _json
        gs = _make_simple_state()
        j1 = _json.dumps(canonical_dict(gs), sort_keys=True, separators=(",", ":"))
        j2 = _json.dumps(canonical_dict(gs), sort_keys=True, separators=(",", ":"))
        assert j1 == j2


# -------------------------------------------------------------------------
# Serialization tests
# -------------------------------------------------------------------------

class TestSerialization:
    def test_to_dict_round_trip(self):
        gs = _make_simple_state()
        d = to_dict(gs)
        gs2 = from_dict(d)
        assert gs2.turn_number == gs.turn_number
        assert gs2.current_player == gs.current_player
        assert set(gs2.card_instances.keys()) == set(gs.card_instances.keys())

    def test_to_json_round_trip(self):
        gs = _make_simple_state()
        j = to_json(gs)
        assert isinstance(j, str)
        gs2 = from_json(j)
        assert gs2.turn_number == gs.turn_number
        assert gs2.game_status == gs.game_status

    def test_to_json_valid_json(self):
        gs = _make_simple_state()
        j = to_json(gs)
        parsed = json.loads(j)
        assert "turn_number" in parsed
        assert "players" in parsed

    def test_to_bytes_round_trip(self):
        gs = _make_simple_state()
        b = to_bytes(gs)
        assert isinstance(b, bytes)
        gs2 = from_bytes(b)
        assert gs2.turn_number == gs.turn_number

    def test_bytes_compressed(self):
        gs = _make_simple_state()
        b = to_bytes(gs)
        j = to_json(gs).encode("utf-8")
        # Compressed bytes should generally be smaller than raw JSON
        assert len(b) < len(j) * 2  # generous bound

    def test_json_with_action_history(self):
        gs = _make_simple_state()
        act = ActionRecord.make(ActionType.ATTACK, 0, turn=3, attack="Thunderbolt")
        gs = gs.with_action(act)
        j = to_json(gs)
        gs2 = from_json(j)
        assert len(gs2.action_history) == 1
        assert gs2.action_history[0].action_type == ActionType.ATTACK

    def test_json_with_knockout(self):
        gs = _make_simple_state()
        ko = KnockoutRecord(
            turn=3, knocked_out_instance_id="charm-active-p1",
            knocked_out_name="Charmander", owner=1, by_player=0,
        )
        gs = gs.with_knockout(ko)
        gs2 = from_json(to_json(gs))
        assert len(gs2.knockout_history) == 1

    def test_write_read_json(self, tmp_path):
        from src.game_state.serialization import read_json, write_json
        gs = _make_simple_state()
        path = tmp_path / "state.json"
        write_json(gs, path)
        gs2 = read_json(path)
        assert gs2.turn_number == gs.turn_number

    def test_write_read_bytes(self, tmp_path):
        from src.game_state.serialization import read_bytes, write_bytes
        gs = _make_simple_state()
        path = tmp_path / "state.bin"
        write_bytes(gs, path)
        gs2 = read_bytes(path)
        assert gs2.turn_number == gs.turn_number

    def test_serialization_preserves_instances(self):
        gs = _make_simple_state()
        gs2 = from_json(to_json(gs))
        inst_orig = gs.get_instance("pika-active-p0")
        inst_restored = gs2.get_instance("pika-active-p0")
        assert inst_restored.card_name == inst_orig.card_name
        assert inst_restored.owner == inst_orig.owner
        assert inst_restored.zone == inst_orig.zone

    def test_serialization_preserves_conditions(self):
        gs = _make_simple_state()
        pika = gs.get_instance("pika-active-p0")
        pika2 = pika.with_condition(SpecialCondition.BURNED)
        gs2 = gs.with_instance(pika2)
        gs3 = from_json(to_json(gs2))
        inst = gs3.get_instance("pika-active-p0")
        assert SpecialCondition.BURNED in inst.special_conditions


# -------------------------------------------------------------------------
# Feature encoding tests
# -------------------------------------------------------------------------

class TestFeatureEncoding:
    def setup_method(self):
        self.encoder = FeatureEncoder()
        self.gs = _make_simple_state()

    def test_encode_returns_encoded_features(self):
        f = self.encoder.encode(self.gs)
        assert isinstance(f, EncodedFeatures)

    def test_flat_vector_length(self):
        f = self.encoder.encode(self.gs)
        assert len(f.flat) == TOTAL_FEATURE_SIZE

    def test_group_sizes_correct(self):
        f = self.encoder.encode(self.gs)
        for fg in FeatureGroup.ordered():
            expected = GROUP_SIZES[fg]
            actual = len(f.groups[fg.value])
            assert actual == expected, f"Group {fg.value}: expected {expected}, got {actual}"

    def test_feature_values_in_range(self):
        f = self.encoder.encode(self.gs)
        for i, v in enumerate(f.flat):
            assert -0.01 <= v <= 1.01, f"Feature {i} out of range: {v}"

    def test_deterministic(self):
        f1 = self.encoder.encode(self.gs)
        f2 = self.encoder.encode(self.gs)
        assert f1.flat == f2.flat

    def test_different_states_different_features(self):
        gs2 = self.gs.with_instance(
            self.gs.get_instance("pika-active-p0").with_damage(30)
        )
        f1 = self.encoder.encode(self.gs)
        f2 = self.encoder.encode(gs2)
        assert f1.flat != f2.flat

    def test_perspective_affects_self_opp(self):
        f0 = self.encoder.encode(self.gs, perspective=0)
        f1 = self.encoder.encode(self.gs, perspective=1)
        assert f0.flat != f1.flat

    def test_encode_flat_shortcut(self):
        flat = encode_flat(self.gs)
        assert len(flat) == TOTAL_FEATURE_SIZE

    def test_encode_sparse(self):
        sparse = self.encoder.encode_sparse(self.gs)
        assert isinstance(sparse, dict)
        assert all(v != 0.0 for v in sparse.values())

    def test_group_slicing(self):
        f = self.encoder.encode(self.gs)
        sliced = f.slice(FeatureGroup.ACTIVE_SELF)
        from src.game_state.features import GROUP_ACTIVE_SIZE
        assert len(sliced) == GROUP_ACTIVE_SIZE

    def test_active_self_present_flag(self):
        f = self.encoder.encode(self.gs)
        active_feats = f.slice(FeatureGroup.ACTIVE_SELF)
        # First feature is the present flag — should be 1 since we have an active
        assert active_feats[0] == 1.0

    def test_empty_active_slot(self):
        gs = GameState.new_game()
        f = self.encoder.encode(gs)
        active_feats = f.slice(FeatureGroup.ACTIVE_SELF)
        assert active_feats[0] == 0.0  # no active → present=0

    def test_bench_encoding(self):
        f = self.encoder.encode(self.gs)
        bench_feats = f.slice(FeatureGroup.BENCH_SELF)
        # First bench slot should have present=1 (Bulbasaur on bench)
        assert bench_feats[0] == 1.0
        # Second slot should be absent
        assert bench_feats[POKEMON_FEAT_SIZE] == 0.0

    def test_embedding_placeholder_zeros(self):
        f = self.encoder.encode(self.gs)
        emb = f.slice(FeatureGroup.EMBEDDINGS)
        assert all(v == 0.0 for v in emb)

    def test_history_encoding(self):
        gs = _make_simple_state()
        for i in range(5):
            act = ActionRecord.make(ActionType.ATTACK, 0, turn=i)
            gs = gs.with_action(act)
        f = self.encoder.encode(gs)
        hist = f.slice(FeatureGroup.HISTORY)
        # At least some history should be non-zero
        assert any(v > 0 for v in hist)

    def test_turn_features(self):
        f = self.encoder.encode(self.gs)
        turn_feats = f.slice(FeatureGroup.TURN)
        # turn_number=3 → 3/100 = 0.03
        assert turn_feats[0] == pytest.approx(0.03)
        # current_player=0, perspective=0 → flag=1
        assert turn_feats[1] == 1.0

    def test_encode_groups_shortcut(self):
        groups = self.encoder.encode_groups(self.gs)
        assert isinstance(groups, dict)
        assert FeatureGroup.ACTIVE_SELF.value in groups

    def test_feature_stability_after_serialization(self):
        gs2 = from_json(to_json(self.gs))
        f1 = encode_flat(self.gs)
        f2 = encode_flat(gs2)
        assert f1 == f2


# -------------------------------------------------------------------------
# Action mask tests
# -------------------------------------------------------------------------

class TestActionMask:
    def test_all_blocked(self):
        m = ActionMask.all_blocked("no cards")
        assert not m.can_attack
        assert m.can_end_turn  # always available
        assert not m.has_any_action or m.can_end_turn

    def test_end_turn_only(self):
        m = ActionMask.end_turn_only()
        assert m.can_end_turn
        assert not m.can_attack

    def test_as_vector_length(self):
        m = ActionMask()
        assert len(m.as_vector) == TOTAL_MASK_SIZE

    def test_as_vector_values(self):
        m = ActionMask(can_attack=True, can_retreat=True)
        v = m.as_vector
        assert v[0] == 1.0   # can_attack
        assert v[1] == 1.0   # can_retreat
        assert v[2] == 0.0   # can_evolve

    def test_round_trip_from_vector(self):
        m = ActionMask(
            can_attack=True, can_end_turn=True,
            attack_mask=(True, False, False, False),
        )
        v = m.as_vector
        m2 = ActionMask.from_vector(v)
        assert m2.can_attack == m.can_attack
        assert m2.can_end_turn == m.can_end_turn

    def test_placeholder_for_state(self):
        gs = _make_simple_state()
        m = ActionMask.placeholder_for_state(gs)
        # P0 has active + bench, so can_attack and can_retreat should be True
        assert m.can_attack
        assert m.can_retreat
        assert m.can_end_turn

    def test_placeholder_empty_board(self):
        gs = GameState.new_game()
        m = ActionMask.placeholder_for_state(gs)
        assert not m.can_attack  # no active
        assert m.can_end_turn

    def test_legal_attack_indices(self):
        m = ActionMask(attack_mask=(True, False, True, False))
        assert m.legal_attack_indices == (0, 2)

    def test_bench_evolve_mask(self):
        m = ActionMask(bench_evolve_mask=(True, False, True, False, False))
        assert m.legal_evolve_slots == (0, 2)

    def test_has_any_action_false(self):
        m = ActionMask()
        assert not m.has_any_action

    def test_frozen(self):
        m = ActionMask()
        with pytest.raises(Exception):
            m.can_attack = True  # type: ignore[misc]


# -------------------------------------------------------------------------
# Action history tests
# -------------------------------------------------------------------------

class TestActionHistory:
    def test_make_action(self):
        act = make_action(ActionType.ATTACK, 0, 3, card_instance_id="pika-1", attack="Thunderbolt")
        assert act.action_type == ActionType.ATTACK
        assert act.player == 0
        assert act.turn == 3
        assert act.get_detail("attack") == "Thunderbolt"

    def test_action_record_immutable(self):
        act = ActionRecord.make(ActionType.DRAW, 1, 2)
        with pytest.raises(Exception):
            act.player = 0  # type: ignore[misc]

    def test_game_history_by_player(self):
        gs = _make_simple_state()
        gs = gs.with_action(make_action(ActionType.ATTACK, 0, 1))
        gs = gs.with_action(make_action(ActionType.ATTACK, 1, 2))
        gs = gs.with_action(make_action(ActionType.DRAW, 0, 3))
        h = GameHistory.from_state(gs)
        assert len(h.by_player(0)) == 2
        assert len(h.by_player(1)) == 1

    def test_game_history_by_type(self):
        gs = _make_simple_state()
        gs = gs.with_action(make_action(ActionType.ATTACK, 0, 1))
        gs = gs.with_action(make_action(ActionType.ATTACK, 0, 2))
        gs = gs.with_action(make_action(ActionType.DRAW, 0, 3))
        h = GameHistory.from_state(gs)
        assert len(h.by_type(ActionType.ATTACK)) == 2

    def test_game_history_last_n(self):
        gs = _make_simple_state()
        for i in range(10):
            gs = gs.with_action(make_action(ActionType.DRAW, 0, i))
        h = GameHistory.from_state(gs)
        assert len(h.last_n(3)) == 3

    def test_knockout_history(self):
        gs = _make_simple_state()
        ko = KnockoutRecord(
            turn=3, knocked_out_instance_id="charm-active-p1",
            knocked_out_name="Charmander", owner=1, by_player=0, prizes_taken=1,
        )
        gs = gs.with_knockout(ko)
        h = GameHistory.from_state(gs)
        assert len(h.kos_by(0)) == 1
        assert h.prizes_taken(0) == 1

    def test_action_type_counts(self):
        gs = _make_simple_state()
        gs = gs.with_action(make_action(ActionType.ATTACK, 0, 1))
        gs = gs.with_action(make_action(ActionType.ATTACK, 0, 2))
        gs = gs.with_action(make_action(ActionType.END_TURN, 0, 2))
        h = GameHistory.from_state(gs)
        counts = h.action_type_counts()
        assert counts[ActionType.ATTACK] == 2
        assert counts[ActionType.END_TURN] == 1


# -------------------------------------------------------------------------
# Validation tests
# -------------------------------------------------------------------------

class TestValidation:
    def test_valid_state(self):
        gs = _make_simple_state()
        report = validate_state(gs)
        assert report.is_valid, f"Unexpected errors: {[e.message for e in report.errors]}"

    def test_new_game_valid(self):
        gs = GameState.new_game()
        report = validate_state(gs)
        assert report.is_valid

    def test_negative_damage(self):
        gs = _make_simple_state()
        pika = gs.get_instance("pika-active-p0")
        bad_pika = pika.model_copy(update={"damage_taken": -10})
        gs2 = gs.with_instance(bad_pika)
        report = validate_state(gs2)
        assert any(e.code == "NEGATIVE_DAMAGE" for e in report.errors)

    def test_negative_hp(self):
        gs = _make_simple_state()
        pika = gs.get_instance("pika-active-p0")
        bad_pika = pika.model_copy(update={"base_hp": -10})
        gs2 = gs.with_instance(bad_pika)
        report = validate_state(gs2)
        assert any(e.code == "NEGATIVE_HP" for e in report.errors)

    def test_active_on_bench(self):
        gs = _make_simple_state()
        p0 = gs.players[0]
        bad_p0 = p0.model_copy(update={"bench": (p0.active,)})
        gs2 = gs.with_player(0, bad_p0)
        report = validate_state(gs2)
        assert any(e.code == "ACTIVE_ON_BENCH" for e in report.errors)

    def test_bench_overflow(self):
        gs = _make_simple_state()
        p0 = gs.players[0]
        bad_p0 = p0.model_copy(update={"bench": ("a", "b", "c", "d", "e", "f")})
        gs2 = gs.with_player(0, bad_p0)
        report = validate_state(gs2)
        assert any(e.code == "BENCH_OVERFLOW" for e in report.errors)

    def test_invalid_prize_count(self):
        gs = _make_simple_state()
        p0 = gs.players[0].model_copy(update={"prizes_remaining": 10})
        gs2 = gs.with_player(0, p0)
        report = validate_state(gs2)
        assert any(e.code == "INVALID_PRIZE_COUNT" for e in report.errors)

    def test_missing_instance_reference(self):
        gs = _make_simple_state()
        p0 = gs.players[0].model_copy(update={"active": "nonexistent-id"})
        gs2 = gs.with_player(0, p0)
        report = validate_state(gs2)
        # Either MISSING_INSTANCE or similar
        assert not report.is_valid

    def test_duplicate_zone(self):
        gs = _make_simple_state()
        pika_id = "pika-active-p0"
        p0 = gs.players[0]
        bad_p0 = p0.model_copy(update={
            "bench": (pika_id,) + p0.bench,
            "bench_count": len(p0.bench) + 1,
        })
        gs2 = gs.with_player(0, bad_p0)
        report = validate_state(gs2)
        assert any(e.code in ("DUPLICATE_ZONE", "ACTIVE_ON_BENCH") for e in report.errors)

    def test_report_summary(self):
        gs = _make_simple_state()
        report = validate_state(gs)
        assert "Valid" in report.summary()

    def test_report_errors_warnings(self):
        report = validate_state(_make_simple_state())
        assert isinstance(report.errors, list)
        assert isinstance(report.warnings, list)


# -------------------------------------------------------------------------
# Exports tests
# -------------------------------------------------------------------------

class TestExports:
    def test_to_terminal(self):
        gs = _make_simple_state()
        text = to_terminal(gs)
        assert "GAME STATE" in text
        assert "Pikachu" in text
        assert "Charmander" in text

    def test_to_markdown(self):
        gs = _make_simple_state()
        md = to_markdown(gs)
        assert "# Game State" in md
        assert "Player 0" in md
        assert "Player 1" in md

    def test_terminal_shows_hp(self):
        gs = _make_simple_state()
        text = to_terminal(gs)
        assert "70" in text  # Pikachu's HP

    def test_summary_dict(self):
        from src.game_state.exports import to_summary_dict
        gs = _make_simple_state()
        s = to_summary_dict(gs)
        assert "turn" in s
        assert "player_0" in s
        assert "player_1" in s
        assert s["turn"] == 3

    def test_features_summary(self):
        from src.game_state.exports import features_summary
        gs = _make_simple_state()
        f = encode(gs)
        text = features_summary(f)
        assert "EncodedFeatures" in text
        assert "active_self" in text


# -------------------------------------------------------------------------
# Tensor tests
# -------------------------------------------------------------------------

class TestTensors:
    def test_features_to_list(self):
        from src.game_state.tensors import features_to_list
        gs = _make_simple_state()
        f = encode(gs)
        lst = features_to_list(f)
        assert isinstance(lst, list)
        assert len(lst) == TOTAL_FEATURE_SIZE

    def test_mask_to_list(self):
        from src.game_state.tensors import mask_to_list
        m = ActionMask(can_attack=True)
        lst = mask_to_list(m)
        assert lst[0] == 1.0

    def test_batch_features(self):
        from src.game_state.tensors import batch_features_to_numpy
        gs = _make_simple_state()
        fs = [encode(gs) for _ in range(4)]
        batch = batch_features_to_numpy(fs)
        # Works as list of lists if numpy not available
        assert len(batch) == 4

    def test_encode_transition(self):
        from src.game_state.tensors import encode_transition
        gs = _make_simple_state()
        f = encode(gs)
        m = ActionMask.placeholder_for_state(gs)
        t = encode_transition(f, m)
        assert "obs" in t
        assert "mask" in t
        assert "obs_groups" in t

    def test_dict_of_arrays(self):
        from src.game_state.tensors import features_to_dict_of_arrays
        gs = _make_simple_state()
        f = encode(gs)
        d = features_to_dict_of_arrays(f)
        assert "active_self" in d


# -------------------------------------------------------------------------
# Real card integration (optional — skips if no EN_Card_Data.csv)
# -------------------------------------------------------------------------

class TestRealCardIntegration:
    @pytest.fixture(autouse=True)
    def load_cards(self):
        try:
            from src.cards.parser import parse_csv
            result = parse_csv("EN_Card_Data.csv")
            self.cards = result.cards
        except Exception:
            pytest.skip("EN_Card_Data.csv not available")

    def test_create_instances_from_real_cards(self):
        from src.cards.models import PokemonCard
        basics = [c for c in self.cards if isinstance(c, PokemonCard) and c.stage.value == "Basic Pokémon"]
        card = basics[0]
        inst = CardInstance.create_pokemon(
            card_id=str(card.card_id),
            card_name=card.name,
            owner=0,
            base_hp=card.hp or 60,
            stage=PokemonStage.BASIC,
        )
        assert inst.card_name == card.name
        assert inst.max_hp == (card.hp or 60)

    def test_encode_real_game_state(self):
        from src.cards.models import PokemonCard
        basics = [c for c in self.cards if isinstance(c, PokemonCard) and c.stage.value == "Basic Pokémon"]
        pika_id = "real-pika"
        charm_id = "real-charm"
        inst0 = CardInstance.create_pokemon(
            str(basics[0].card_id), basics[0].name, 0, basics[0].hp or 60,
            instance_id=pika_id,
        )
        inst1 = CardInstance.create_pokemon(
            str(basics[1].card_id), basics[1].name, 1, basics[1].hp or 60,
            instance_id=charm_id,
        )
        # Move to active zones
        inst0 = inst0.with_zone(Zone.ACTIVE)
        inst1 = inst1.with_zone(Zone.ACTIVE)

        p0 = PlayerState(player_id=0, active=pika_id, hand_count=5, deck_size=54, prizes_remaining=6)
        p1 = PlayerState(player_id=1, active=charm_id, hand_count=5, deck_size=54, prizes_remaining=6)
        gs = GameState(
            turn_number=1,
            current_player=0,
            game_status=GameStatus.ONGOING,
            players=(p0, p1),
            card_instances={pika_id: inst0, charm_id: inst1},
        )
        f = encode(gs)
        assert len(f.flat) == TOTAL_FEATURE_SIZE
        # Active present = 1
        assert f.slice(FeatureGroup.ACTIVE_SELF)[0] == 1.0
        report = validate_state(gs)
        assert report.is_valid

    def test_encode_stable_across_rebuilds(self):
        from src.cards.models import PokemonCard
        basics = [c for c in self.cards if isinstance(c, PokemonCard) and c.stage.value == "Basic Pokémon"]
        inst = CardInstance.create_pokemon(
            str(basics[0].card_id), basics[0].name, 0, basics[0].hp or 60,
            instance_id="stable-test",
        ).with_zone(Zone.ACTIVE)
        p0 = PlayerState(player_id=0, active="stable-test", hand_count=5, deck_size=55, prizes_remaining=6)
        p1 = PlayerState(player_id=1, hand_count=5, deck_size=55, prizes_remaining=6)
        gs = GameState(
            turn_number=1, current_player=0, game_status=GameStatus.ONGOING,
            players=(p0, p1), card_instances={"stable-test": inst},
        )
        f1 = encode_flat(gs)
        gs2 = from_json(to_json(gs))
        f2 = encode_flat(gs2)
        assert f1 == f2

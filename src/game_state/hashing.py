"""
Deterministic hashing for GameState.

Two game states that are structurally identical must produce the same hash,
regardless of object identity, creation order, or state_id.  The state_id
field is excluded from the hash so that copies of the same board position
collide correctly in transposition tables.

Strategy
--------
1. Serialize the state to a canonical dict (sorted keys, no state_id).
2. Encode to UTF-8 JSON with sorted keys and no whitespace.
3. Apply SHA-256.
4. Return the first 8 bytes as a signed 64-bit integer for __hash__.

The full hex digest (``state_fingerprint``) is used for equality checks
and cache keys.
"""

from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game_state.models import CardInstance
    from src.game_state.player import PlayerState
    from src.game_state.state import GameState


# -------------------------------------------------------------------------
# Canonical dict builder (excludes identity fields)
# -------------------------------------------------------------------------

def _canon_card(inst: CardInstance) -> dict:
    return {
        "card_id": inst.card_id,
        "owner": inst.owner,
        "zone": inst.zone.value,
        "category": inst.category.value,
        "base_hp": inst.base_hp,
        "hp_modifier": inst.hp_modifier,
        "damage_taken": inst.damage_taken,
        "stage": inst.stage.value,
        "prize_value": inst.prize_value,
        "attached_energy_ids": sorted(inst.attached_energy_ids),
        "attached_tool_id": inst.attached_tool_id,
        "special_conditions": sorted(c.value for c in inst.special_conditions),
        "turn_entered_play": inst.turn_entered_play,
        "has_attacked": inst.has_attacked,
        "has_retreated": inst.has_retreated,
        "is_evolved_this_turn": inst.is_evolved_this_turn,
        "ability_used": inst.ability_used,
        "effect_flags": sorted(inst.effect_flags),
        "previous_stage_instance_id": inst.previous_stage_instance_id,
    }


def _canon_player(p: PlayerState) -> dict:
    return {
        "player_id": p.player_id,
        "active": p.active,
        "bench": list(p.bench),
        "hand": sorted(p.hand),  # hand order may be arbitrary
        "hand_count": p.hand_count,
        "deck_size": p.deck_size,
        "discard": list(p.discard),
        "lost_zone": list(p.lost_zone),
        "prizes": list(p.prizes),
        "prizes_remaining": p.prizes_remaining,
        "supporter_played_this_turn": p.supporter_played_this_turn,
        "energy_attached_this_turn": p.energy_attached_this_turn,
        "stadium_played_this_turn": p.stadium_played_this_turn,
        "bench_count": p.bench_count,
        "discard_count": p.discard_count,
        "lost_zone_count": p.lost_zone_count,
    }


def _canon_action(a) -> dict:
    return {
        "action_type": a.action_type.value,
        "player": a.player,
        "turn": a.turn,
        "card_instance_id": a.card_instance_id,
        "target_instance_id": a.target_instance_id,
        "details": [[k, v] for k, v in a.details],
    }


def _canon_ko(k) -> dict:
    return {
        "turn": k.turn,
        "knocked_out_instance_id": k.knocked_out_instance_id,
        "knocked_out_name": k.knocked_out_name,
        "owner": k.owner,
        "by_player": k.by_player,
        "by_attack_name": k.by_attack_name,
        "prizes_taken": k.prizes_taken,
    }


def canonical_dict(state: GameState) -> dict:
    """
    Return a canonical dict of the game state, excluding volatile identity
    fields (state_id).  This is the basis for hashing and equality.
    """
    # Sort card_instances by instance_id for stable ordering
    instances_sorted = sorted(state.card_instances.items())

    return {
        "turn_number": state.turn_number,
        "current_player": state.current_player,
        "game_status": state.game_status.value,
        "winner": state.winner,
        "players": [_canon_player(p) for p in state.players],
        "card_instances": {k: _canon_card(v) for k, v in instances_sorted},
        "stadium_instance_id": state.stadium_instance_id,
        "action_history": [_canon_action(a) for a in state.action_history],
        "knockout_history": [_canon_ko(k) for k in state.knockout_history],
    }


# -------------------------------------------------------------------------
# Hash computation
# -------------------------------------------------------------------------

def state_fingerprint(state: GameState) -> str:
    """Return the SHA-256 hex digest of the canonical state dict."""
    canon = canonical_dict(state)
    raw = json.dumps(canon, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def state_hash_int(state: GameState) -> int:
    """Return a 64-bit signed integer hash derived from SHA-256."""
    digest = hashlib.sha256(
        json.dumps(canonical_dict(state), sort_keys=True, separators=(",", ":"))
        .encode("utf-8")
    ).digest()
    # Use first 8 bytes as unsigned 64-bit, convert to signed
    val = int.from_bytes(digest[:8], "big", signed=False)
    # Map to signed int64 range
    if val >= (1 << 63):
        val -= 1 << 64
    return val


def instance_fingerprint(inst: CardInstance) -> str:
    """Return a short fingerprint for a single CardInstance."""
    raw = json.dumps(_canon_card(inst), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]

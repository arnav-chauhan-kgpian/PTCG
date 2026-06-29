"""
Human-readable export formats for GameState.

Provides terminal output, structured summary dicts, and markdown rendering.
These are for inspection and debugging; ML pipelines should use encoder.py.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game_state.encoder import EncodedFeatures
    from src.game_state.player import PlayerState
    from src.game_state.state import GameState


# -------------------------------------------------------------------------
# Summary dict
# -------------------------------------------------------------------------

def to_summary_dict(state: GameState) -> dict:
    """Return a compact summary of the game state as a plain dict."""
    p0, p1 = state.players

    def _player_summary(p: PlayerState, label: str) -> dict:
        active_name = ""
        if p.active and p.active in state.card_instances:
            inst = state.card_instances[p.active]
            active_name = (
                f"{inst.card_name} "
                f"({inst.remaining_hp}/{inst.max_hp} HP)"
            )
        bench_names = []
        for bid in p.bench:
            if bid in state.card_instances:
                inst = state.card_instances[bid]
                bench_names.append(f"{inst.card_name} ({inst.remaining_hp}/{inst.max_hp})")
        return {
            "label": label,
            "active": active_name or "(none)",
            "bench": bench_names,
            "hand_count": p.hand_count,
            "deck_size": p.deck_size,
            "prizes_remaining": p.prizes_remaining,
            "discard_count": p.discard_count,
            "lost_zone_count": p.lost_zone_count,
        }

    return {
        "state_id": state.state_id,
        "turn": state.turn_number,
        "current_player": state.current_player,
        "status": state.game_status.value,
        "winner": state.winner,
        "stadium": (
            state.card_instances[state.stadium_instance_id].card_name
            if state.stadium_instance_id and state.stadium_instance_id in state.card_instances
            else None
        ),
        "player_0": _player_summary(p0, "P0"),
        "player_1": _player_summary(p1, "P1"),
        "total_actions": len(state.action_history),
        "total_knockouts": len(state.knockout_history),
    }


# -------------------------------------------------------------------------
# Terminal output
# -------------------------------------------------------------------------

def to_terminal(state: GameState) -> str:
    """Return a multi-line terminal-friendly representation."""
    lines: list[str] = []
    _hr = "─" * 60

    lines.append(_hr)
    lines.append(f"  GAME STATE  Turn {state.turn_number}  │  Player {state.current_player}'s turn")
    lines.append(f"  Status: {state.game_status.value}" + (
        f"  │  Winner: P{state.winner}" if state.winner is not None else ""
    ))
    lines.append(_hr)

    for pidx, p in enumerate(state.players):
        marker = " ◄" if pidx == state.current_player else ""
        lines.append(f"  PLAYER {pidx}{marker}")

        # Active
        active_str = "(no active)"
        if p.active and p.active in state.card_instances:
            inst = state.card_instances[p.active]
            conds = "/".join(c.value for c in inst.special_conditions) or "—"
            en_count = len(inst.attached_energy_ids)
            active_str = (
                f"{inst.card_name}  HP {inst.remaining_hp}/{inst.max_hp}"
                f"  E:{en_count}  Status:{conds}"
            )
        lines.append(f"    Active: {active_str}")

        # Bench
        bench_parts = []
        for bid in p.bench:
            if bid in state.card_instances:
                inst = state.card_instances[bid]
                bench_parts.append(
                    f"{inst.card_name}({inst.remaining_hp}/{inst.max_hp})"
                )
        lines.append(f"    Bench:  {', '.join(bench_parts) or '(empty)'}")

        # Zones
        lines.append(
            f"    Hand:{p.hand_count}  Deck:{p.deck_size}  "
            f"Prizes:{p.prizes_remaining}  Discard:{p.discard_count}  "
            f"LostZone:{p.lost_zone_count}"
        )
        lines.append(
            f"    Flags  Supporter:{p.supporter_played_this_turn}  "
            f"Energy:{p.energy_attached_this_turn}"
        )

    # Stadium
    if state.stadium_instance_id and state.stadium_instance_id in state.card_instances:
        st = state.card_instances[state.stadium_instance_id]
        lines.append(f"  Stadium: {st.card_name}")

    # Recent actions
    recent = state.action_history[-5:]
    if recent:
        lines.append("  Recent actions:")
        for act in recent:
            lines.append(
                f"    T{act.turn} P{act.player}: {act.action_type.value}"
                + (f" [{act.card_instance_id[:8]}]" if act.card_instance_id else "")
            )

    lines.append(_hr)
    return "\n".join(lines)


# -------------------------------------------------------------------------
# Markdown
# -------------------------------------------------------------------------

def to_markdown(state: GameState) -> str:
    """Return a Markdown-formatted game state report."""
    s = to_summary_dict(state)
    lines = [
        f"# Game State — Turn {s['turn']}",
        "",
        f"**Status:** {s['status']}  ",
        f"**Current Player:** {s['current_player']}  ",
        (f"**Winner:** Player {s['winner']}" if s['winner'] is not None else ""),
        (f"**Stadium:** {s['stadium']}" if s['stadium'] else ""),
        "",
        "## Player 0",
        f"- **Active:** {s['player_0']['active']}",
        "- **Bench:** " + (", ".join(s["player_0"]["bench"]) or "empty"),
        f"- Hand: {s['player_0']['hand_count']}  Deck: {s['player_0']['deck_size']}  "
        f"Prizes: {s['player_0']['prizes_remaining']}",
        "",
        "## Player 1",
        f"- **Active:** {s['player_1']['active']}",
        "- **Bench:** " + (", ".join(s["player_1"]["bench"]) or "empty"),
        f"- Hand: {s['player_1']['hand_count']}  Deck: {s['player_1']['deck_size']}  "
        f"Prizes: {s['player_1']['prizes_remaining']}",
        "",
        f"**Actions recorded:** {s['total_actions']}  ",
        f"**Knockouts recorded:** {s['total_knockouts']}",
    ]
    return "\n".join(l for l in lines if l is not None)


# -------------------------------------------------------------------------
# Feature encoding summary
# -------------------------------------------------------------------------

def features_summary(features: EncodedFeatures) -> str:
    """Return a compact summary of encoded feature groups."""
    lines = [
        f"EncodedFeatures (perspective=P{features.perspective}, total={features.total_size})",
    ]
    for name, vec in features.groups.items():
        non_zero = sum(1 for v in vec if v != 0.0)
        lines.append(f"  {name:<20} size={len(vec):>4}  non-zero={non_zero}")
    return "\n".join(lines)

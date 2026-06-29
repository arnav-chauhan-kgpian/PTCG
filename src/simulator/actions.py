"""
Action codec — conventions for encoding game actions as ``MCTSAction``.

Every legal player decision is represented as an ``MCTSAction`` so the
existing MCTS / neural pipeline can consume it without modification.
The ``details`` tuple carries the typed parameters needed to execute it.

Conventions
-----------
end_turn                 → action_type='end_turn'
attack                   → 'attack',           details=(('slot', '0..3'),)
attach_energy            → 'attach_energy',    details=(('hand_idx', N), ('target', 'active'|'bench:I'))
play_pokemon (basic)     → 'play_pokemon',     details=(('hand_idx', N),)
evolve                   → 'evolve',           details=(('hand_idx', N), ('target', 'active'|'bench:I'))
retreat                  → 'retreat',          details=(('to_bench_idx', N), ('discarded', '0,1,...'))
play_item                → 'play_item',        details=(('hand_idx', N), ...)
play_supporter           → 'play_supporter',   details=(('hand_idx', N), ...)
play_stadium             → 'play_stadium',     details=(('hand_idx', N),)
attach_tool              → 'attach_tool',      details=(('hand_idx', N), ('target', ...))
use_ability              → 'use_ability',      details=(('source', 'active'|'bench:I'), ('name', '...'))
"""

from __future__ import annotations

from src.mcts.node import MCTSAction

# -------------------------------------------------------------------------
# Target descriptor helpers
# -------------------------------------------------------------------------

def target_active() -> str:
    return "active"


def target_bench(index: int) -> str:
    return f"bench:{index}"


def parse_target(s: str) -> tuple[str, int]:
    """Return ('active', 0) or ('bench', i)."""
    if s == "active":
        return "active", 0
    if s.startswith("bench:"):
        return "bench", int(s.split(":", 1)[1])
    raise ValueError(f"Unknown target descriptor: {s!r}")


# -------------------------------------------------------------------------
# Factories
# -------------------------------------------------------------------------

def end_turn() -> MCTSAction:
    return MCTSAction(action_type="end_turn")


def attack(slot: int) -> MCTSAction:
    return MCTSAction(action_type="attack", details=(("slot", str(slot)),))


def attach_energy(hand_idx: int, target: str) -> MCTSAction:
    return MCTSAction(
        action_type="attach_energy",
        details=(("hand_idx", str(hand_idx)), ("target", target)),
    )


def play_pokemon(hand_idx: int) -> MCTSAction:
    return MCTSAction(
        action_type="play_pokemon",
        details=(("hand_idx", str(hand_idx)),),
    )


def promote_to_active(bench_idx: int) -> MCTSAction:
    """Forced promotion of a benched Pokémon to the empty Active slot."""
    return MCTSAction(
        action_type="promote_to_active",
        details=(("bench_idx", str(bench_idx)),),
    )


def evolve(hand_idx: int, target: str) -> MCTSAction:
    return MCTSAction(
        action_type="evolve",
        details=(("hand_idx", str(hand_idx)), ("target", target)),
    )


def retreat(to_bench_idx: int, discarded: list[int]) -> MCTSAction:
    return MCTSAction(
        action_type="retreat",
        details=(
            ("to_bench_idx", str(to_bench_idx)),
            ("discarded", ",".join(str(i) for i in discarded)),
        ),
    )


def play_item(hand_idx: int, target: str | None = None) -> MCTSAction:
    details = [("hand_idx", str(hand_idx))]
    if target:
        details.append(("target", target))
    return MCTSAction(action_type="play_item", details=tuple(details))


def play_supporter(hand_idx: int, target: str | None = None) -> MCTSAction:
    details = [("hand_idx", str(hand_idx))]
    if target:
        details.append(("target", target))
    return MCTSAction(action_type="play_supporter", details=tuple(details))


def play_stadium(hand_idx: int) -> MCTSAction:
    return MCTSAction(
        action_type="play_stadium",
        details=(("hand_idx", str(hand_idx)),),
    )


def attach_tool(hand_idx: int, target: str) -> MCTSAction:
    return MCTSAction(
        action_type="attach_tool",
        details=(("hand_idx", str(hand_idx)), ("target", target)),
    )


def use_ability(source: str, name: str) -> MCTSAction:
    return MCTSAction(
        action_type="use_ability",
        details=(("source", source), ("name", name)),
    )


# -------------------------------------------------------------------------
# Detail extraction
# -------------------------------------------------------------------------

def _detail(action: MCTSAction, key: str) -> str | None:
    for k, v in action.details:
        if k == key:
            return v
    return None


def get_int(action: MCTSAction, key: str, default: int = 0) -> int:
    val = _detail(action, key)
    return int(val) if val is not None else default


def get_str(action: MCTSAction, key: str, default: str = "") -> str:
    val = _detail(action, key)
    return val if val is not None else default


def get_int_list(action: MCTSAction, key: str) -> list[int]:
    val = _detail(action, key) or ""
    if not val:
        return []
    return [int(s) for s in val.split(",") if s]

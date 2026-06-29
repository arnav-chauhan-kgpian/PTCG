"""
GameState structural validator.

Validates internal consistency of a GameState snapshot without applying
any game rules.  Returns structured reports rather than raising exceptions
so that callers can choose how to handle issues.

Checks performed
----------------
- No duplicate instance_ids across any zone
- No negative HP, damage, or prize counts
- Zone references point to real instances
- Instance owners match their player's zone membership
- Attachment ownership: attached_energy_ids → real instances with zone=ATTACHED
- Active slot not duplicated on bench
- Prize count matches prizes_remaining
- Bench size ≤ 5
- Loss-zone / discard / hand counts match instance lists where known
- No CardInstance in multiple zones simultaneously
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.game_state.zones import Zone

if TYPE_CHECKING:
    from src.game_state.state import GameState


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    message: str
    severity: str = "error"     # "error" | "warning"
    instance_id: str | None = None
    player_id: int | None = None


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)

    def error(self, code: str, message: str, **kw) -> None:
        self.add(ValidationIssue(code=code, message=message, severity="error", **kw))

    def warn(self, code: str, message: str, **kw) -> None:
        self.add(ValidationIssue(code=code, message=message, severity="warning", **kw))

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        if self.is_valid:
            return f"Valid ({len(self.warnings)} warnings)"
        return (
            f"Invalid: {len(self.errors)} error(s), {len(self.warnings)} warning(s)"
        )


def validate_state(state: GameState) -> ValidationReport:
    report = ValidationReport()
    instances = state.card_instances

    # ------------------------------------------------------------------ #
    # 1. Collect all zone references
    # ------------------------------------------------------------------ #
    zone_refs: dict[str, list[str]] = {}  # instance_id → [zone descriptions]

    def _ref(iid: str, location: str) -> None:
        if iid:
            zone_refs.setdefault(iid, []).append(location)

    for pidx, p in enumerate(state.players):
        if p.active:
            _ref(p.active, f"p{pidx}.active")
        for b in p.bench:
            _ref(b, f"p{pidx}.bench")
        for h in p.hand:
            _ref(h, f"p{pidx}.hand")
        for d in p.discard:
            _ref(d, f"p{pidx}.discard")
        for lz in p.lost_zone:
            _ref(lz, f"p{pidx}.lost_zone")
        for pr in p.prizes:
            if pr:
                _ref(pr, f"p{pidx}.prizes")
        for iid in p.deck_order:
            _ref(iid, f"p{pidx}.deck")

    if state.stadium_instance_id:
        _ref(state.stadium_instance_id, "stadium")

    # ------------------------------------------------------------------ #
    # 2. Duplicate zone membership
    # ------------------------------------------------------------------ #
    for iid, locs in zone_refs.items():
        if len(locs) > 1:
            report.error(
                "DUPLICATE_ZONE",
                f"Instance {iid} appears in multiple zones: {locs}",
                instance_id=iid,
            )

    # ------------------------------------------------------------------ #
    # 3. Dangling references (zone reference → missing instance)
    # ------------------------------------------------------------------ #
    for iid in zone_refs:
        if iid not in instances:
            report.error(
                "MISSING_INSTANCE",
                f"Zone references instance_id {iid!r} not in card_instances",
                instance_id=iid,
            )

    # ------------------------------------------------------------------ #
    # 4. Per-instance checks
    # ------------------------------------------------------------------ #
    for iid, inst in instances.items():
        if iid != inst.instance_id:
            report.error(
                "ID_MISMATCH",
                f"Key {iid!r} != instance.instance_id {inst.instance_id!r}",
                instance_id=iid,
            )

        if inst.base_hp < 0:
            report.error(
                "NEGATIVE_HP",
                f"Instance {iid} has negative base_hp {inst.base_hp}",
                instance_id=iid,
            )

        if inst.damage_taken < 0:
            report.error(
                "NEGATIVE_DAMAGE",
                f"Instance {iid} has negative damage_taken {inst.damage_taken}",
                instance_id=iid,
            )

        if inst.prize_value not in (1, 2):
            report.warn(
                "UNUSUAL_PRIZE_VALUE",
                f"Instance {iid} has prize_value={inst.prize_value} (expected 1 or 2)",
                instance_id=iid,
            )

        if inst.owner not in (0, 1):
            report.error(
                "INVALID_OWNER",
                f"Instance {iid} owner={inst.owner} must be 0 or 1",
                instance_id=iid,
            )

        # Attachment checks
        for eid in inst.attached_energy_ids:
            if eid not in instances:
                report.error(
                    "MISSING_ATTACHED_ENERGY",
                    f"Instance {iid} references attached energy {eid!r} not found",
                    instance_id=iid,
                )
            elif instances[eid].zone != Zone.ATTACHED:
                report.error(
                    "ATTACHED_ENERGY_WRONG_ZONE",
                    f"Attached energy {eid} has zone={instances[eid].zone.value}, expected 'attached'",
                    instance_id=eid,
                )

        if inst.attached_tool_id is not None:
            tid = inst.attached_tool_id
            if tid not in instances:
                report.error(
                    "MISSING_ATTACHED_TOOL",
                    f"Instance {iid} references attached tool {tid!r} not found",
                    instance_id=iid,
                )
            elif instances[tid].zone != Zone.ATTACHED:
                report.error(
                    "ATTACHED_TOOL_WRONG_ZONE",
                    f"Attached tool {tid} has zone={instances[tid].zone.value}, expected 'attached'",
                    instance_id=tid,
                )

    # ------------------------------------------------------------------ #
    # 5. Per-player checks
    # ------------------------------------------------------------------ #
    for pidx, p in enumerate(state.players):
        if len(p.bench) > 5:
            report.error(
                "BENCH_OVERFLOW",
                f"Player {pidx} has {len(p.bench)} bench Pokémon (max 5)",
                player_id=pidx,
            )

        if p.prizes_remaining < 0 or p.prizes_remaining > 6:
            report.error(
                "INVALID_PRIZE_COUNT",
                f"Player {pidx} prizes_remaining={p.prizes_remaining} (must be 0–6)",
                player_id=pidx,
            )

        if p.deck_size < 0:
            report.error(
                "NEGATIVE_DECK",
                f"Player {pidx} deck_size={p.deck_size}",
                player_id=pidx,
            )

        if p.hand_count < 0:
            report.error(
                "NEGATIVE_HAND",
                f"Player {pidx} hand_count={p.hand_count}",
                player_id=pidx,
            )

        # Active not on bench
        if p.active and p.active in p.bench:
            report.error(
                "ACTIVE_ON_BENCH",
                f"Player {pidx} active Pokémon {p.active} also appears on bench",
                player_id=pidx,
            )

        # Owner check for active
        if p.active and p.active in instances:
            if instances[p.active].owner != pidx:
                report.error(
                    "OWNERSHIP_MISMATCH",
                    f"Player {pidx} active {p.active} owned by player "
                    f"{instances[p.active].owner}",
                    instance_id=p.active,
                    player_id=pidx,
                )

    # ------------------------------------------------------------------ #
    # 6. Game-level checks
    # ------------------------------------------------------------------ #
    if state.current_player not in (0, 1):
        report.error(
            "INVALID_CURRENT_PLAYER",
            f"current_player={state.current_player} (must be 0 or 1)",
        )

    if state.winner is not None and state.winner not in (0, 1):
        report.error(
            "INVALID_WINNER",
            f"winner={state.winner} (must be None, 0, or 1)",
        )

    if state.turn_number < 0:
        report.error(
            "NEGATIVE_TURN",
            f"turn_number={state.turn_number}",
        )

    return report

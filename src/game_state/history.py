"""
History helpers — query and summarize the game's action and knockout records.

The raw ``action_history`` and ``knockout_history`` tuples live on
GameState; this module provides higher-level views without owning any state.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from src.game_state.actions import ActionRecord, ActionType, KnockoutRecord

if TYPE_CHECKING:
    from src.game_state.state import GameState


@dataclass(frozen=True)
class GameHistory:
    """
    Read-only view over the action and knockout history of a GameState.
    All methods are O(n) and produce new containers; nothing is mutated.
    """
    action_history: tuple[ActionRecord, ...]
    knockout_history: tuple[KnockoutRecord, ...]

    # ------------------------------------------------------------------ #
    # Action queries
    # ------------------------------------------------------------------ #

    def by_player(self, player_id: int) -> tuple[ActionRecord, ...]:
        return tuple(a for a in self.action_history if a.player == player_id)

    def by_type(self, action_type: ActionType) -> tuple[ActionRecord, ...]:
        return tuple(a for a in self.action_history if a.action_type == action_type)

    def by_turn(self, turn: int) -> tuple[ActionRecord, ...]:
        return tuple(a for a in self.action_history if a.turn == turn)

    def last_n(self, n: int) -> tuple[ActionRecord, ...]:
        return self.action_history[-n:] if n > 0 else ()

    def attacks(self) -> tuple[ActionRecord, ...]:
        return self.by_type(ActionType.ATTACK)

    def knockouts(self) -> tuple[ActionRecord, ...]:
        return self.by_type(ActionType.KNOCK_OUT)

    def supporter_plays(self, player_id: int) -> tuple[ActionRecord, ...]:
        return tuple(
            a for a in self.action_history
            if a.player == player_id and a.action_type == ActionType.PLAY_SUPPORTER
        )

    # ------------------------------------------------------------------ #
    # Knockout queries
    # ------------------------------------------------------------------ #

    def kos_by(self, player_id: int) -> tuple[KnockoutRecord, ...]:
        return tuple(k for k in self.knockout_history if k.by_player == player_id)

    def kos_suffered(self, player_id: int) -> tuple[KnockoutRecord, ...]:
        return tuple(k for k in self.knockout_history if k.owner == player_id)

    def prizes_taken(self, player_id: int) -> int:
        return sum(k.prizes_taken for k in self.kos_by(player_id))

    # ------------------------------------------------------------------ #
    # Summary stats (used by encoder)
    # ------------------------------------------------------------------ #

    def action_type_counts(self) -> dict[ActionType, int]:
        counts: dict[ActionType, int] = {}
        for action in self.action_history:
            counts[action.action_type] = counts.get(action.action_type, 0) + 1
        return counts

    def turn_density(self, turn: int) -> int:
        """Number of actions taken this turn."""
        return len(self.by_turn(turn))

    @classmethod
    def from_state(cls, state: GameState) -> GameHistory:
        return cls(
            action_history=state.action_history,
            knockout_history=state.knockout_history,
        )


def make_action(
    action_type: ActionType,
    player: int,
    turn: int,
    *,
    card_instance_id: str | None = None,
    target_instance_id: str | None = None,
    **details: str,
) -> ActionRecord:
    """Convenience constructor for ActionRecord."""
    return ActionRecord.make(
        action_type=action_type,
        player=player,
        turn=turn,
        card_instance_id=card_instance_id,
        target_instance_id=target_instance_id,
        **details,
    )

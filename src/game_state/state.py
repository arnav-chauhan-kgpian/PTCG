"""
GameState — the canonical, immutable top-level representation.

A GameState is a complete snapshot of the public game information at a
single point in time.  It is:

  • immutable   – all fields are frozen; updates produce new instances
  • serializable – round-trips through JSON / dict / bytes losslessly
  • hashable     – deterministic hash via canonical serialization (SHA-256)
  • copyable     – ``model_copy(update=...)`` is O(1)
  • deterministic – identical board positions produce identical hashes

``card_instances`` maps every instance_id in play to its runtime state.
All zone lists in PlayerState store instance_ids resolved here.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from src.game_state.actions import ActionRecord, KnockoutRecord
from src.game_state.models import CardInstance
from src.game_state.player import PlayerState
from src.game_state.zones import GameStatus


class GameState(BaseModel):
    """
    Complete immutable snapshot of a PTCG game at one point in time.

    Designed for:
    - Forward simulation (copy-on-write via model_copy)
    - ML feature extraction (encoder.py)
    - MCTS transposition table keys (hashing.py)
    - Replay / serialization (serialization.py)
    """
    model_config = ConfigDict(frozen=True)

    # ------------------------------------------------------------------ #
    # Identity
    # ------------------------------------------------------------------ #
    state_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # ------------------------------------------------------------------ #
    # Turn metadata
    # ------------------------------------------------------------------ #
    turn_number: int = 0
    current_player: int = 0            # 0 or 1
    game_status: GameStatus = GameStatus.NOT_STARTED
    winner: int | None = None        # None, 0, or 1

    # ------------------------------------------------------------------ #
    # Players
    # ------------------------------------------------------------------ #
    players: tuple[PlayerState, PlayerState] = Field(
        default_factory=lambda: (
            PlayerState(player_id=0),
            PlayerState(player_id=1),
        )
    )

    # ------------------------------------------------------------------ #
    # Cards (all instances, keyed by instance_id)
    # ------------------------------------------------------------------ #
    # Note: dict field; __hash__ is overridden to use canonical SHA-256.
    card_instances: dict[str, CardInstance] = Field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Shared board elements
    # ------------------------------------------------------------------ #
    stadium_instance_id: str | None = None

    # ------------------------------------------------------------------ #
    # History
    # ------------------------------------------------------------------ #
    action_history: tuple[ActionRecord, ...] = ()
    knockout_history: tuple[KnockoutRecord, ...] = ()

    # ------------------------------------------------------------------ #
    # Dunder overrides
    # ------------------------------------------------------------------ #

    def __hash__(self) -> int:
        from src.game_state.hashing import state_hash_int
        return state_hash_int(self)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, GameState):
            return NotImplemented
        # Structural equality via fingerprint
        from src.game_state.hashing import state_fingerprint
        return state_fingerprint(self) == state_fingerprint(other)

    # ------------------------------------------------------------------ #
    # Convenience accessors
    # ------------------------------------------------------------------ #

    @property
    def current_player_state(self) -> PlayerState:
        return self.players[self.current_player]

    @property
    def opponent_player_state(self) -> PlayerState:
        return self.players[1 - self.current_player]

    @property
    def is_terminal(self) -> bool:
        return self.game_status not in (
            GameStatus.NOT_STARTED, GameStatus.ONGOING
        )

    @property
    def last_action(self) -> ActionRecord | None:
        return self.action_history[-1] if self.action_history else None

    def get_instance(self, instance_id: str) -> CardInstance | None:
        return self.card_instances.get(instance_id)

    def player(self, player_id: int) -> PlayerState:
        return self.players[player_id]

    # ------------------------------------------------------------------ #
    # Immutable update helpers
    # ------------------------------------------------------------------ #

    def with_players(
        self,
        p0: PlayerState | None = None,
        p1: PlayerState | None = None,
    ) -> GameState:
        new_p0 = p0 if p0 is not None else self.players[0]
        new_p1 = p1 if p1 is not None else self.players[1]
        return self.model_copy(update={"players": (new_p0, new_p1)})

    def with_player(self, player_id: int, state: PlayerState) -> GameState:
        if player_id == 0:
            return self.with_players(p0=state)
        return self.with_players(p1=state)

    def with_instance(self, instance: CardInstance) -> GameState:
        new_instances = dict(self.card_instances)
        new_instances[instance.instance_id] = instance
        return self.model_copy(update={"card_instances": new_instances})

    def with_instances(self, instances: dict[str, CardInstance]) -> GameState:
        new_instances = dict(self.card_instances)
        new_instances.update(instances)
        return self.model_copy(update={"card_instances": new_instances})

    def without_instance(self, instance_id: str) -> GameState:
        new_instances = {
            k: v for k, v in self.card_instances.items() if k != instance_id
        }
        return self.model_copy(update={"card_instances": new_instances})

    def with_action(self, action: ActionRecord) -> GameState:
        return self.model_copy(
            update={"action_history": self.action_history + (action,)}
        )

    def with_knockout(self, ko: KnockoutRecord) -> GameState:
        return self.model_copy(
            update={"knockout_history": self.knockout_history + (ko,)}
        )

    def with_status(self, status: GameStatus, winner: int | None = None) -> GameState:
        return self.model_copy(update={"game_status": status, "winner": winner})

    def with_next_turn(self) -> GameState:
        next_player = 1 - self.current_player
        new_players = (
            self.players[0].reset_turn_flags(),
            self.players[1].reset_turn_flags(),
        )
        return self.model_copy(update={
            "turn_number": self.turn_number + 1,
            "current_player": next_player,
            "players": new_players,
        })

    # ------------------------------------------------------------------ #
    # Factory
    # ------------------------------------------------------------------ #

    @classmethod
    def new_game(cls, seed: int | None = None) -> GameState:
        """Return an empty game in NOT_STARTED status."""
        return cls(
            players=(
                PlayerState(player_id=0),
                PlayerState(player_id=1),
            ),
            game_status=GameStatus.NOT_STARTED,
        )

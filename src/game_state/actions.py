"""
Action types and structured action records for the game history.

Every player decision or game event is recorded as an ActionRecord.
The history provides a complete audit trail for replay, debugging, and
future RL consumption.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class ActionType(str, Enum):
    """All possible action types in a PTCG game."""
    # Player decisions
    PLAY_POKEMON = "play_pokemon"
    EVOLVE = "evolve"
    ATTACH_ENERGY = "attach_energy"
    PLAY_ITEM = "play_item"
    PLAY_SUPPORTER = "play_supporter"
    PLAY_STADIUM = "play_stadium"
    ATTACH_TOOL = "attach_tool"
    RETREAT = "retreat"
    ATTACK = "attack"
    USE_ABILITY = "use_ability"
    SWITCH = "switch"
    END_TURN = "end_turn"
    PASS = "pass"

    # Game events
    DRAW = "draw"
    SEARCH = "search"
    SHUFFLE = "shuffle"
    KNOCK_OUT = "knock_out"
    TAKE_PRIZE = "take_prize"
    MULLIGAN = "mulligan"
    COIN_FLIP = "coin_flip"
    DISCARD = "discard"
    LOST_ZONE = "lost_zone"
    HEAL = "heal"
    DAMAGE = "damage"

    @classmethod
    def ordered(cls) -> tuple[ActionType, ...]:
        return (
            cls.PLAY_POKEMON, cls.EVOLVE, cls.ATTACH_ENERGY,
            cls.PLAY_ITEM, cls.PLAY_SUPPORTER, cls.PLAY_STADIUM, cls.ATTACH_TOOL,
            cls.RETREAT, cls.ATTACK, cls.USE_ABILITY, cls.SWITCH, cls.END_TURN,
            cls.PASS, cls.DRAW, cls.SEARCH, cls.SHUFFLE,
            cls.KNOCK_OUT, cls.TAKE_PRIZE, cls.MULLIGAN, cls.COIN_FLIP,
            cls.DISCARD, cls.LOST_ZONE, cls.HEAL, cls.DAMAGE,
        )

    @classmethod
    def index(cls, action: ActionType) -> int:
        return cls.ordered().index(action)


class ActionRecord(BaseModel):
    """
    An immutable record of a single game action.

    ``details`` stores key-value pairs as a sorted tuple so the record
    remains hashable and serializable without a nested dict.
    """
    model_config = ConfigDict(frozen=True)

    action_type: ActionType
    player: int                                     # 0 or 1 (or -1 for game events)
    turn: int = 0
    card_instance_id: str | None = None          # primary card acted upon
    target_instance_id: str | None = None        # target card (e.g., evolution target)
    details: tuple[tuple[str, str], ...] = ()       # sorted key-value pairs

    def get_detail(self, key: str) -> str | None:
        for k, v in self.details:
            if k == key:
                return v
        return None

    @classmethod
    def make(
        cls,
        action_type: ActionType,
        player: int,
        turn: int = 0,
        card_instance_id: str | None = None,
        target_instance_id: str | None = None,
        **kwargs: str,
    ) -> ActionRecord:
        details = tuple(sorted(kwargs.items()))
        return cls(
            action_type=action_type,
            player=player,
            turn=turn,
            card_instance_id=card_instance_id,
            target_instance_id=target_instance_id,
            details=details,
        )


class KnockoutRecord(BaseModel):
    """Record of a single knockout event."""
    model_config = ConfigDict(frozen=True)

    turn: int
    knocked_out_instance_id: str
    knocked_out_name: str
    owner: int                      # player who owned the knocked out pokemon
    by_player: int                  # player whose attack caused the KO
    by_attack_name: str = ""
    prizes_taken: int = 1

"""
Curriculum schedules — produce initial states for each training round.

A ``CurriculumStage`` knows how to build a starting state.  The
``Curriculum`` advances through stages based on round number or external
trigger (e.g. promotion success).  Both are pluggable: any callable
matching ``(round_index) -> GameState`` works.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.game_state.state import GameState


StateBuilder = Callable[[int], "GameState"]


@dataclass(frozen=True)
class CurriculumStage:
    name: str
    builder: StateBuilder
    min_rounds: int = 0       # earliest round this stage activates
    description: str = ""


@dataclass
class Curriculum:
    """
    Linear curriculum: stages are tried in order; the latest stage whose
    ``min_rounds`` ≤ current round is selected.
    """

    stages: list[CurriculumStage] = field(default_factory=list)

    def add_stage(self, stage: CurriculumStage) -> None:
        self.stages.append(stage)
        self.stages.sort(key=lambda s: s.min_rounds)

    def stage_for_round(self, round_index: int) -> CurriculumStage:
        if not self.stages:
            raise ValueError("Curriculum has no stages")
        active = self.stages[0]
        for s in self.stages:
            if s.min_rounds <= round_index:
                active = s
            else:
                break
        return active

    def build_state(self, round_index: int) -> GameState:
        return self.stage_for_round(round_index).builder(round_index)

    def summary(self) -> list[dict]:
        return [
            {"name": s.name, "min_rounds": s.min_rounds, "description": s.description}
            for s in self.stages
        ]


# -------------------------------------------------------------------------
# Default — a simple "empty game state" curriculum so the trainer always
# has something to start from.
# -------------------------------------------------------------------------

def default_curriculum() -> Curriculum:
    """Single-stage curriculum that just returns ``GameState.new_game()``."""
    from src.game_state.state import GameState

    def _empty(_round: int) -> GameState:
        return GameState.new_game()

    return Curriculum(stages=[
        CurriculumStage(
            name="empty_state",
            builder=_empty,
            min_rounds=0,
            description="Empty starting state — useful for unit tests.",
        ),
    ])

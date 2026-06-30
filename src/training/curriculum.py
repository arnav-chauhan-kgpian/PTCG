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
#
# WARNING: ``default_curriculum()`` produces a NOT_STARTED state with no
# decks shuffled in. That state is already-terminal from the simulator's
# perspective, so selfplay produces zero training samples per round.
# The pipeline detects this and raises (see TrainingPipeline._run_round)
# rather than silently running 0-progress rounds. For real training,
# use ``make_curriculum(simulator, deck_a, deck_b)`` below.
# -------------------------------------------------------------------------

def default_curriculum() -> Curriculum:
    """Single-stage curriculum returning ``GameState.new_game()``.

    Only useful for unit tests that don't actually run a round through
    the pipeline. For training, use ``make_curriculum(...)``.
    """
    from src.game_state.state import GameState

    def _empty(_round: int) -> GameState:
        return GameState.new_game()

    return Curriculum(stages=[
        CurriculumStage(
            name="empty_state_test_only",
            builder=_empty,
            min_rounds=0,
            description="Empty starting state — TEST-ONLY, not for training.",
        ),
    ])


def make_curriculum(
    simulator,
    deck_a: list[int],
    deck_b: list[int] | None = None,
    *,
    name: str = "default_match",
    description: str = "Stacked-deck mirror match.",
) -> Curriculum:
    """Build a training curriculum that starts each round with a real game.

    Each call to ``build_state(round_idx)`` reseeds the simulator (so games
    differ between rounds) and returns ``simulator.start_game(deck_a, deck_b)``.

    Args:
        simulator: A ``SimulatorProtocol`` with ``start_game`` and ``reseed``.
        deck_a: 60-card decklist as a list of ``card_id`` ints.
        deck_b: 60-card decklist for the opponent. Defaults to ``deck_a``
            (mirror match).
        name: Stage name surfaced in experiment metadata.
        description: Stage description.
    """
    if deck_b is None:
        deck_b = deck_a

    def _builder(round_idx: int):
        if hasattr(simulator, "reseed"):
            simulator.reseed(round_idx)
        return simulator.start_game(deck_a, deck_b)

    return Curriculum(stages=[
        CurriculumStage(
            name=name,
            builder=_builder,
            min_rounds=0,
            description=description,
        ),
    ])

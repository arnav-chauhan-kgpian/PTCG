"""
P2.4 — Self-play analytics.

Instruments a stream of games with summary metrics and exports CSV /
Markdown reports.  Reads ``SIM_REPORT`` for unsupported-mechanic counts.
"""

from __future__ import annotations

import csv
import io
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.simulator import SIM_REPORT, PokemonTCGSimulator

if TYPE_CHECKING:
    from src.cards.repository import CardRepository
    from src.game_state.state import GameState


@dataclass
class GameRecord:
    """Per-game summary metrics."""
    game_id: int
    move_count: int = 0
    branching_avg: float = 0.0
    winner: int | None = None
    terminated_by: str = ""
    prize_progression: list[tuple[int, int]] = field(default_factory=list)  # (p0, p1) per turn
    trainer_plays: int = 0
    ability_uses: int = 0
    attacks: int = 0
    repeated_states: int = 0
    illegal_attempts: int = 0


@dataclass
class SelfPlayAnalyticsReport:
    games: list[GameRecord] = field(default_factory=list)
    unsupported_classes: dict[str, int] = field(default_factory=dict)
    trainer_executions: dict[str, int] = field(default_factory=dict)
    ability_executions: dict[str, int] = field(default_factory=dict)
    attack_executions: dict[str, int] = field(default_factory=dict)
    total_actions: int = 0
    total_repeated_states: int = 0
    total_illegal_attempts: int = 0

    @property
    def avg_game_length(self) -> float:
        if not self.games:
            return 0.0
        return sum(g.move_count for g in self.games) / len(self.games)

    @property
    def avg_branching_factor(self) -> float:
        if not self.games:
            return 0.0
        return sum(g.branching_avg for g in self.games) / len(self.games)

    @property
    def deckout_rate(self) -> float:
        if not self.games:
            return 0.0
        n = sum(1 for g in self.games if g.terminated_by == "deckout")
        return n / len(self.games)

    @property
    def termination_rate(self) -> float:
        if not self.games:
            return 0.0
        n = sum(1 for g in self.games if g.winner is not None)
        return n / len(self.games)

    def to_dict(self) -> dict:
        return {
            "n_games": len(self.games),
            "avg_game_length": round(self.avg_game_length, 2),
            "avg_branching_factor": round(self.avg_branching_factor, 2),
            "termination_rate": round(self.termination_rate, 4),
            "deckout_rate": round(self.deckout_rate, 4),
            "total_actions": self.total_actions,
            "total_repeated_states": self.total_repeated_states,
            "total_illegal_attempts": self.total_illegal_attempts,
            "unsupported_classes": dict(self.unsupported_classes),
            "trainer_executions": dict(sorted(
                self.trainer_executions.items(),
                key=lambda x: -x[1])[:20]),
            "ability_executions": dict(self.ability_executions),
            "attack_executions": dict(sorted(
                self.attack_executions.items(),
                key=lambda x: -x[1])[:20]),
        }

    def to_csv(self) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow([
            "game_id", "move_count", "branching_avg",
            "winner", "terminated_by", "trainer_plays",
            "ability_uses", "attacks", "repeated_states",
            "illegal_attempts",
        ])
        for g in self.games:
            writer.writerow([
                g.game_id, g.move_count, round(g.branching_avg, 2),
                g.winner if g.winner is not None else "",
                g.terminated_by, g.trainer_plays, g.ability_uses, g.attacks,
                g.repeated_states, g.illegal_attempts,
            ])
        return buf.getvalue()

    def to_markdown(self) -> str:
        d = self.to_dict()
        lines = [
            "# Self-Play Analytics",
            "",
            f"- Games: {d['n_games']}",
            f"- Avg game length: {d['avg_game_length']}",
            f"- Avg branching factor: {d['avg_branching_factor']}",
            f"- Termination rate: {d['termination_rate']:.2%}",
            f"- Deckout rate: {d['deckout_rate']:.2%}",
            f"- Total actions: {d['total_actions']}",
            f"- Repeated states: {d['total_repeated_states']}",
            f"- Illegal attempts: {d['total_illegal_attempts']}",
            "",
            "## Top trainer cards by frequency",
            "",
        ]
        for k, v in d["trainer_executions"].items():
            lines.append(f"- **{k}**: {v}")
        lines.append("")
        lines.append("## Unsupported effect classes")
        lines.append("")
        for k, v in d["unsupported_classes"].items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)


def record_game(
    simulator: PokemonTCGSimulator,
    state: GameState,
    *,
    rng: random.Random,
    max_moves: int = 400,
    game_id: int = 0,
) -> GameRecord:
    """Play one random self-play game and return its GameRecord."""
    from src.game_state.hashing import state_fingerprint
    record = GameRecord(game_id=game_id)
    branching_samples: list[int] = []
    seen_states: set[str] = set()
    illegal_attempts = 0

    while not simulator.is_terminal(state) and record.move_count < max_moves:
        legal = simulator.legal_actions(state)
        if not legal:
            break
        branching_samples.append(len(legal))
        chosen = rng.choice(legal)
        # Count action category
        if chosen.action_type in ("play_item", "play_supporter", "play_stadium"):
            record.trainer_plays += 1
        elif chosen.action_type == "attack":
            record.attacks += 1
        elif chosen.action_type == "use_ability":
            record.ability_uses += 1
        if chosen not in legal:
            illegal_attempts += 1
        state = simulator.apply_action(state, chosen)
        record.move_count += 1
        fp = state_fingerprint(state)
        if fp in seen_states:
            record.repeated_states += 1
        else:
            seen_states.add(fp)

    record.branching_avg = (
        sum(branching_samples) / len(branching_samples)
        if branching_samples else 0.0
    )
    if state.is_terminal:
        if state.winner is not None:
            record.winner = state.winner
        from src.game_state.zones import GameStatus
        if state.game_status == GameStatus.DRAW:
            record.terminated_by = "draw"
        elif (state.players[0].deck_size == 0
              or state.players[1].deck_size == 0):
            record.terminated_by = "deckout"
        else:
            record.terminated_by = "prize_or_no_pokemon"
    else:
        record.terminated_by = "max_moves"
    record.illegal_attempts = illegal_attempts
    return record


def analyze_games(
    repository: CardRepository,
    *,
    n_games: int = 20,
    max_moves: int = 400,
    seed: int = 0,
    deck_a: list[int] | None = None,
    deck_b: list[int] | None = None,
) -> SelfPlayAnalyticsReport:
    """Drive ``n_games`` random self-play games and aggregate analytics."""
    SIM_REPORT.clear()
    report = SelfPlayAnalyticsReport()
    base_rng = random.Random(seed)

    if deck_a is None or deck_b is None:
        from src.evaluation.simulator_validation import _default_deck
        deck = _default_deck(repository)
        deck_a = deck_a or deck
        deck_b = deck_b or deck

    for i in range(n_games):
        sim = PokemonTCGSimulator(repository, seed=base_rng.randint(0, 10_000))
        state = sim.start_game(deck_a, deck_b)
        rng = random.Random(base_rng.randint(0, 10_000))
        record = record_game(sim, state, rng=rng, max_moves=max_moves,
                              game_id=i)
        report.games.append(record)
        report.total_actions += record.move_count
        report.total_repeated_states += record.repeated_states
        report.total_illegal_attempts += record.illegal_attempts

    # Aggregate SIM_REPORT telemetry
    sim_d = SIM_REPORT.to_dict()
    report.unsupported_classes = sim_d.get("by_class", {})
    report.trainer_executions = sim_d.get("trainer_executions", {})
    report.ability_executions = sim_d.get("ability_executions", {})
    report.attack_executions = sim_d.get("attack_executions", {})
    return report

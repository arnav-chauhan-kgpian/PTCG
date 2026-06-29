"""
P2.9 — Evaluation dashboard.

Aggregates the various P2 reports and produces JSON or Markdown output
suitable for CLI display, CI artifacts, or pasting into reports.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.evaluation.benchmarks import BenchmarkReport
    from src.evaluation.elo_arena import EloLeague
    from src.evaluation.mcts_evaluation import MCTSEvaluationReport
    from src.evaluation.opening_book import OpeningBookReport
    from src.evaluation.selfplay_analytics import SelfPlayAnalyticsReport
    from src.evaluation.simulator_validation import SimulatorValidationReport


def render_dashboard(
    *,
    sim_validation: SimulatorValidationReport | None = None,
    selfplay: SelfPlayAnalyticsReport | None = None,
    mcts_eval: MCTSEvaluationReport | None = None,
    opening_book: OpeningBookReport | None = None,
    benchmarks: BenchmarkReport | None = None,
    elo: EloLeague | None = None,
    indent: int = 2,
) -> str:
    """Render the full evaluation snapshot as a JSON string."""
    payload: dict = {}
    if sim_validation is not None:
        payload["simulator_validation"] = {
            **sim_validation.to_dict(),
            "correctness_rate": round(sim_validation.correctness_rate, 4),
        }
    if selfplay is not None:
        payload["selfplay"] = selfplay.to_dict()
    if mcts_eval is not None:
        payload["mcts_evaluation"] = mcts_eval.to_dict()
    if opening_book is not None:
        payload["opening_book"] = opening_book.to_dict()
    if benchmarks is not None:
        payload["benchmarks"] = benchmarks.to_dict()
    if elo is not None:
        payload["elo"] = elo.to_dict()
    return json.dumps(payload, indent=indent, default=str)


def render_dashboard_markdown(
    *,
    sim_validation: SimulatorValidationReport | None = None,
    selfplay: SelfPlayAnalyticsReport | None = None,
    mcts_eval: MCTSEvaluationReport | None = None,
    opening_book: OpeningBookReport | None = None,
    benchmarks: BenchmarkReport | None = None,
    elo: EloLeague | None = None,
) -> str:
    """Produce a CLI-friendly Markdown report."""
    lines: list[str] = ["# Evaluation Dashboard", ""]

    if sim_validation is not None:
        v = sim_validation
        lines.extend([
            "## Simulator validation",
            "",
            f"- Games played: **{v.games_played}**",
            f"- Terminal rate: **{v.games_terminal}/{v.games_played}** "
            f"({(v.games_terminal/max(1,v.games_played)):.1%})",
            f"- Total actions: **{v.total_actions}**",
            f"- Illegal actions attempted: {v.illegal_actions_attempted}",
            f"- State mutation violations: {v.state_mutation_violations}",
            f"- Prize accounting errors: {v.prize_accounting_errors}",
            f"- Bench overflow observed: {v.bench_overflow_observed}",
            f"- Duplicate zone observed: {v.duplicate_zone_observed}",
            f"- Knockouts total: {v.knockouts_total}",
            f"- Burn / Poison / Asleep wake / Paralysis clear: "
            f"{v.burn_damage_events}/{v.poison_damage_events}/"
            f"{v.asleep_wake_events}/{v.paralysis_clear_events}",
            f"- Correctness rate: **{v.correctness_rate:.4f}**",
            "",
        ])

    if selfplay is not None:
        d = selfplay.to_dict()
        lines.extend([
            "## Self-play analytics",
            "",
            f"- Games: **{d['n_games']}**",
            f"- Avg length: **{d['avg_game_length']}** actions",
            f"- Avg branching factor: **{d['avg_branching_factor']}**",
            f"- Termination rate: **{d['termination_rate']:.1%}**",
            f"- Deckout rate: **{d['deckout_rate']:.1%}**",
            f"- Total trainer plays: {sum(d['trainer_executions'].values())}",
            f"- Unsupported effect classes still observed: "
            f"{len(d['unsupported_classes'])}",
            "",
        ])

    if mcts_eval is not None:
        d = mcts_eval.to_dict()
        lines.extend([
            "## MCTS quality",
            "",
            f"- Positions evaluated: **{len(d['positions'])}**",
            f"- Avg iter/sec: **{d['avg_iterations_per_second']:.0f}**",
            f"- Avg branching factor: **{d['avg_branching_factor']:.2f}**",
            f"- Heuristic ↔ alternate same-action rate: "
            f"**{d['heuristic_action_agreement_rate']:.2%}**",
            "",
        ])

    if opening_book is not None:
        d = opening_book.to_dict()
        lines.extend([
            "## Opening book",
            "",
            f"- Samples: **{d['n_samples']}**",
            f"- Distinct top actions: **{d['unique_chosen_actions']}**",
            f"- Avg policy entropy: **{d['avg_entropy']:.3f}**",
            f"- Avg top-1 visit share: **{d['avg_top1_share']:.2%}**",
            f"- Avg branching: **{d['avg_branching']:.1f}**",
            f"- Unstable openings (top1<50%): "
            f"**{d['unstable_openings']}/{d['n_samples']}**",
            "",
        ])

    if benchmarks is not None:
        d = benchmarks.to_dict()
        lines.extend([
            "## Performance benchmarks",
            "",
            f"- Simulator: **{d['simulator_actions_per_sec']:.0f}** actions/s, "
            f"**{d['simulator_games_per_sec']:.1f}** games/s"
            if d['simulator_actions_per_sec'] is not None else "",
            f"- Encoder: **{d['encoder_per_sec']:.0f}** encodes/s"
            if d['encoder_per_sec'] is not None else "",
            f"- Network single: **{d['network_single_latency_us']:.0f}** µs/call"
            if d['network_single_latency_us'] is not None else "",
            f"- Network batch: **{d['network_batch_per_sec']:.0f}** states/s"
            if d['network_batch_per_sec'] is not None else "",
            f"- MCTS: **{d['mcts_iterations_per_sec']:.0f}** iter/s"
            if d['mcts_iterations_per_sec'] is not None else "",
            f"- Replay: **{d['replay_samples_per_sec']:.0f}** samples/s"
            if d['replay_samples_per_sec'] is not None else "",
            "",
        ])
        lines.extend(f"- Note: {n}" for n in d["notes"])
        lines.append("")

    if elo is not None:
        d = elo.to_dict()
        lines.extend([
            "## Elo standings",
            "",
            "| Player | Rating | Games | W | L | D |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ])
        for row in d["standings"]:
            lines.append(
                f"| {row['name']} | {row['rating']:.1f} | {row['games']} "
                f"| {row['wins']} | {row['losses']} | {row['draws']} |"
            )
        lines.append("")

    return "\n".join(l for l in lines if l is not None)

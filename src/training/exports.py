"""
Pretty-print helpers for the training pipeline.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.training.arena import ArenaResult
    from src.training.experiments import ExperimentManager
    from src.training.metrics import TrainingMetrics
    from src.training.promotion import PromotionDecision


def arena_to_terminal(result: ArenaResult) -> str:
    s = result.summary()
    return (
        f"Arena: cand={s['candidate_wins']} champ={s['champion_wins']} "
        f"draw={s['draws']}  rate={s['candidate_win_rate']:.3f}  "
        f"score={s['candidate_score']:.3f}  "
        f"len={s['avg_game_length']:.1f}  t={s['elapsed_s']}s"
    )


def metrics_to_terminal(metrics: TrainingMetrics) -> str:
    s = metrics.snapshot()
    lines = [
        "─" * 60,
        f"  TRAINING METRICS  (rounds={s['rounds']}, steps={s['training_steps']})",
        "─" * 60,
        f"  Last loss:  total={s['last_total_loss']}  "
        f"policy={s['last_policy_loss']}  value={s['last_value_loss']}",
        f"  Avg loss:   total={s['avg_total_loss']}  "
        f"policy={s['avg_policy_loss']}  value={s['avg_value_loss']}",
        f"  Win rate:   last={s['last_win_rate']}  avg={s['avg_win_rate']}  "
        f"best={s['best_win_rate']}",
        f"  Games:      {s['games_played']}  Moves: {s['moves_generated']}  "
        f"Avg len: {s['avg_game_length']}",
        f"  Replay:     {s['replay_size']}  Throughput: "
        f"{s['throughput_samples_per_sec']}/s",
        f"  Promotions: {s['promotion_count']}  Elapsed: {s['elapsed_s']}s",
        "─" * 60,
    ]
    return "\n".join(lines)


def promotion_to_terminal(decision: PromotionDecision) -> str:
    badge = "PROMOTED" if decision.promoted else "REJECTED"
    return (
        f"[{badge}] win_rate={decision.candidate_win_rate:.3f} "
        f"score={decision.candidate_score:.3f} "
        f"thr={decision.threshold:.3f} n={decision.n_games}  ({decision.reason})"
    )


def experiment_to_json(exp: ExperimentManager, indent: int | None = 2) -> str:
    return json.dumps(exp.manifest.to_dict(), indent=indent, default=str)


def experiment_to_terminal(exp: ExperimentManager) -> str:
    s = exp.summary()
    return (
        f"Experiment '{s['name']}'  status={s['status']}  "
        f"ckpts={s['checkpoints']}  best={s['best']}  "
        f"promos={s['promotions']}  t={s['training_duration_s']}s"
    )

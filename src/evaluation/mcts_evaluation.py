"""
P2.3 — MCTS quality evaluation.

Runs MCTS on a set of benchmark positions, compares heuristic vs. neural
search, and reports agreement and stability metrics.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from src.mcts import MCTSConfig, MCTSSearch

if TYPE_CHECKING:
    from src.game_state.state import GameState
    from src.mcts.node import MCTSAction
    from src.mcts.simulation import SimulatorProtocol


@dataclass
class PositionResult:
    """MCTS measurements on a single position."""
    name: str
    chosen_action: str = ""
    total_visits: int = 0
    branching_factor: float = 0.0
    elapsed_s: float = 0.0
    iterations_per_second: float = 0.0
    pv: list[str] = field(default_factory=list)
    policy_entropy: float = 0.0
    nodes_created: int = 0


@dataclass
class AgreementResult:
    """Compare two MCTS variants on the same position."""
    name: str = ""
    same_action: bool = False
    pv_overlap: int = 0
    visit_correlation: float = 0.0


@dataclass
class MCTSEvaluationReport:
    positions: list[PositionResult] = field(default_factory=list)
    agreements: list[AgreementResult] = field(default_factory=list)

    @property
    def heuristic_action_agreement_rate(self) -> float:
        if not self.agreements:
            return 0.0
        return sum(a.same_action for a in self.agreements) / len(self.agreements)

    @property
    def avg_iterations_per_second(self) -> float:
        if not self.positions:
            return 0.0
        return sum(p.iterations_per_second for p in self.positions) / len(self.positions)

    @property
    def avg_branching_factor(self) -> float:
        if not self.positions:
            return 0.0
        return sum(p.branching_factor for p in self.positions) / len(self.positions)

    def to_dict(self) -> dict:
        return {
            "positions": [vars(p) for p in self.positions],
            "agreements": [vars(a) for a in self.agreements],
            "heuristic_action_agreement_rate": self.heuristic_action_agreement_rate,
            "avg_iterations_per_second": self.avg_iterations_per_second,
            "avg_branching_factor": self.avg_branching_factor,
        }


def evaluate_mcts(
    simulator: SimulatorProtocol,
    positions: list[tuple[str, GameState]],
    *,
    iterations: int = 100,
    second_evaluator=None,
    second_prior_policy=None,
) -> MCTSEvaluationReport:
    """Run MCTS on each position; optionally compare to a second search.

    Args:
        simulator: shared simulator
        positions: list of (name, state) tuples to evaluate
        iterations: MCTS iterations per position
        second_evaluator: if supplied, also run MCTS using this evaluator
        second_prior_policy: if supplied, used with the second evaluator
    """
    report = MCTSEvaluationReport()
    cfg = MCTSConfig(iterations=iterations, time_budget_s=30.0)
    for name, state in positions:
        search = MCTSSearch(simulator, config=cfg)
        t0 = time.perf_counter()
        primary = search.run(state)
        elapsed = time.perf_counter() - t0
        report.positions.append(PositionResult(
            name=name,
            chosen_action=str(primary.best_action) if primary.best_action else "",
            total_visits=primary.total_visits,
            branching_factor=len(primary.visit_counts),
            elapsed_s=round(elapsed, 4),
            iterations_per_second=primary.statistics.iterations_per_second,
            pv=[str(a) for a in primary.principal_variation[:5]],
            policy_entropy=_entropy(list(primary.visit_counts.values())),
            nodes_created=primary.statistics.nodes_created,
        ))

        if second_evaluator is not None or second_prior_policy is not None:
            kwargs: dict = {}
            if second_evaluator is not None:
                kwargs["evaluator"] = second_evaluator
            if second_prior_policy is not None:
                kwargs["prior_policy"] = second_prior_policy
            search2 = MCTSSearch(simulator, config=cfg, **kwargs)
            secondary = search2.run(state)
            report.agreements.append(AgreementResult(
                name=name,
                same_action=(primary.best_action == secondary.best_action),
                pv_overlap=_pv_overlap(primary.principal_variation,
                                        secondary.principal_variation),
                visit_correlation=_visit_correlation(
                    primary.visit_counts, secondary.visit_counts,
                ),
            ))

    return report


def _entropy(counts: list[int]) -> float:
    import math
    total = sum(counts) or 1
    h = 0.0
    for c in counts:
        if c <= 0:
            continue
        p = c / total
        h -= p * math.log(p)
    return round(h, 4)


def _pv_overlap(a: list[MCTSAction], b: list[MCTSAction]) -> int:
    return sum(1 for x, y in zip(a, b) if x == y)


def _visit_correlation(a: dict, b: dict) -> float:
    if not a or not b:
        return 0.0
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    import math
    xa = [a[k] for k in keys]
    xb = [b[k] for k in keys]
    ma = sum(xa) / len(xa)
    mb = sum(xb) / len(xb)
    num = sum((va - ma) * (vb - mb) for va, vb in zip(xa, xb))
    da = math.sqrt(sum((v - ma) ** 2 for v in xa))
    db = math.sqrt(sum((v - mb) ** 2 for v in xb))
    denom = da * db
    if denom == 0:
        return 0.0
    return round(num / denom, 4)

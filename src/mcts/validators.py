"""
Validators for MCTS search components and results.

These are sanity checks for development and tests; production search uses
the simulator's own validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.mcts.config import MCTSConfig
    from src.mcts.node import MCTSNode
    from src.mcts.search import SearchResult
    from src.mcts.tree import MCTSTree


@dataclass(frozen=True)
class MCTSIssue:
    code: str
    message: str
    severity: str = "error"


@dataclass
class MCTSValidationReport:
    issues: list[MCTSIssue] = field(default_factory=list)

    def add(self, code: str, message: str, severity: str = "error") -> None:
        self.issues.append(MCTSIssue(code=code, message=message, severity=severity))

    @property
    def errors(self) -> list[MCTSIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[MCTSIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        return (
            f"{'Valid' if self.is_valid else 'Invalid'}: "
            f"{len(self.errors)} error(s), {len(self.warnings)} warning(s)"
        )


# -------------------------------------------------------------------------
# Validators
# -------------------------------------------------------------------------

def validate_config(config: MCTSConfig) -> MCTSValidationReport:
    """Re-validate configuration with structured output (vs. raise)."""
    report = MCTSValidationReport()
    try:
        config.validate()
    except AssertionError as exc:
        report.add("CONFIG_ASSERT", str(exc))
    if config.iterations < 1:
        report.add("BAD_ITERATIONS", "iterations must be >= 1")
    if config.time_budget_s <= 0:
        report.add("BAD_TIME_BUDGET", "time_budget_s must be > 0")
    if config.exploration_constant < 0:
        report.add("BAD_EXPLORATION", "exploration_constant must be >= 0")
    if not (0.0 <= config.discount <= 1.0):
        report.add("BAD_DISCOUNT", "discount must be in [0, 1]")
    if config.rollout_depth < 0:
        report.add("BAD_ROLLOUT_DEPTH", "rollout_depth must be >= 0")
    if config.determinizations < 1:
        report.add("BAD_DETERMINIZATIONS", "determinizations must be >= 1")
    return report


def validate_node(node: MCTSNode) -> MCTSValidationReport:
    """Sanity-check a single node's internal consistency."""
    report = MCTSValidationReport()

    if node.visit_count < 0:
        report.add("NEGATIVE_VISITS", f"visit_count={node.visit_count}")
    if node.depth < 0:
        report.add("NEGATIVE_DEPTH", f"depth={node.depth}")
    if node.virtual_loss < 0:
        report.add("NEGATIVE_VIRTUAL_LOSS", f"virtual_loss={node.virtual_loss}")
    if node.parent is not None and node.parent.depth + 1 != node.depth:
        report.add(
            "DEPTH_MISMATCH",
            f"node.depth={node.depth} parent.depth+1={node.parent.depth + 1}",
        )
    if not (0.0 <= node.prior <= 1.0 + 1e-9):
        report.add("BAD_PRIOR", f"prior={node.prior}", "warning")

    return report


def validate_tree(tree: MCTSTree) -> MCTSValidationReport:
    """Sanity-check the entire tree (BFS)."""
    from collections import deque
    report = MCTSValidationReport()

    seen_ids: set[int] = set()
    q: deque = deque([tree.root])
    visit_total = tree.root.visit_count

    while q:
        node = q.popleft()
        if node.node_id in seen_ids:
            report.add("DUPLICATE_NODE_ID", f"node_id={node.node_id} appears twice")
            continue
        seen_ids.add(node.node_id)

        sub = validate_node(node)
        report.issues.extend(sub.issues)

        # Children visits should not exceed parent (rough consistency)
        child_visit_sum = sum(c.visit_count for c in node.children.values())
        if child_visit_sum > node.visit_count + 1:
            report.add(
                "CHILD_VISITS_EXCEED_PARENT",
                f"node {node.node_id}: child sum {child_visit_sum} > "
                f"parent {node.visit_count}",
                "warning",
            )
        q.extend(node.children.values())

    if visit_total < 0:
        report.add("NEGATIVE_ROOT_VISITS", "root visit_count < 0")
    return report


def validate_result(result: SearchResult) -> MCTSValidationReport:
    """Sanity-check a SearchResult."""
    report = MCTSValidationReport()
    if result.elapsed_s < 0:
        report.add("NEGATIVE_TIME", f"elapsed_s={result.elapsed_s}")
    if not result.visit_counts and result.statistics.iterations > 0:
        report.add(
            "NO_VISITS_AFTER_ITER",
            "iterations ran but no root children produced — simulator may be empty",
            "warning",
        )
    if result.best_action is None and result.statistics.iterations > 0:
        report.add(
            "NO_BEST_ACTION", "iterations ran but no best action chosen", "warning",
        )
    return report

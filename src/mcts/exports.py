"""
Human-readable export formats for MCTS search results and trees.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.mcts.node import MCTSNode
    from src.mcts.search import SearchResult
    from src.mcts.tree import MCTSTree


def result_to_dict(result: SearchResult) -> dict:
    return result.to_dict()


def result_to_json(result: SearchResult, indent: int | None = 2) -> str:
    return json.dumps(result.to_dict(), indent=indent)


def result_to_terminal(result: SearchResult) -> str:
    """Multi-line terminal summary of a SearchResult."""
    lines: list[str] = []
    hr = "─" * 60
    lines.append(hr)
    lines.append(f"  MCTS RESULT  (elapsed={result.elapsed_s:.3f}s)")
    lines.append(hr)

    if result.best_action is not None:
        lines.append(f"  Best action: {result.best_action}")
    else:
        lines.append("  Best action: (none)")

    lines.append(f"  Total root visits: {result.total_visits}")
    lines.append(f"  Iterations: {result.statistics.iterations}")
    lines.append(f"  Iter/sec:   {result.statistics.iterations_per_second:.1f}")

    if result.action_ranking:
        lines.append("")
        lines.append("  Action ranking:")
        for i, (action, score) in enumerate(result.action_ranking[:8], 1):
            lines.append(f"    {i}. {action}  visits={int(score)}")

    if result.principal_variation:
        lines.append("")
        lines.append("  Principal variation:")
        for i, act in enumerate(result.principal_variation, 1):
            lines.append(f"    {i}. {act}")

    s = result.statistics
    lines.append("")
    lines.append(
        f"  Stats: nodes={s.nodes_created}  evals={s.evaluations}  "
        f"tt_hit={s.transposition_hit_rate:.1%}  mean_v={s.mean_value:.3f}"
    )
    lines.append(hr)
    return "\n".join(lines)


def tree_to_dot(tree: MCTSTree, max_depth: int = 3) -> str:
    """Render the search tree as a Graphviz DOT string."""
    from collections import deque
    lines = ["digraph MCTS {", "  node [shape=box, fontname=Helvetica];"]

    q: deque = deque([tree.root])
    seen: set[int] = set()
    while q:
        node = q.popleft()
        if node.node_id in seen or node.depth > max_depth:
            continue
        seen.add(node.node_id)

        label = (
            f"id={node.node_id}\\nN={node.visit_count}\\n"
            f"Q={node.q_value:.2f}\\ndepth={node.depth}"
        )
        lines.append(f'  n{node.node_id} [label="{label}"];')

        for action, child in node.children.items():
            lines.append(
                f'  n{node.node_id} -> n{child.node_id} '
                f'[label="{str(action)[:20]}"];'
            )
            q.append(child)

    lines.append("}")
    return "\n".join(lines)


def tree_to_markdown(tree: MCTSTree, max_depth: int = 3) -> str:
    """Render the search tree as a markdown nested list."""

    def _render(node: MCTSNode, indent: int) -> list[str]:
        prefix = "  " * indent + "- "
        line = (
            f"{prefix}**{str(node.action) if node.action else 'root'}**  "
            f"N={node.visit_count} Q={node.q_value:.3f}"
        )
        lines = [line]
        if indent >= max_depth:
            return lines
        sorted_children = sorted(
            node.children.items(),
            key=lambda kv: kv[1].visit_count,
            reverse=True,
        )
        for _, child in sorted_children:
            lines.extend(_render(child, indent + 1))
        return lines

    return "\n".join(_render(tree.root, 0))

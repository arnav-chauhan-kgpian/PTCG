"""
Graph validation — detects structural issues without raising.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from loguru import logger

from src.cards.relationships.graph import CardGraph
from src.cards.relationships.models import RelationshipType


@dataclass
class ValidationIssue:
    category: str
    card_id: str
    detail: str
    severity: str = "warning"  # "warning" | "error"


@dataclass
class GraphValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "warning"]

    def is_clean(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = [f"Validation: {len(self.issues)} issues "
                 f"({len(self.errors)} errors, {len(self.warnings)} warnings)"]
        for issue in self.issues[:20]:
            lines.append(f"  [{issue.severity.upper()}] {issue.category}: "
                         f"{issue.card_id} — {issue.detail}")
        if len(self.issues) > 20:
            lines.append(f"  ... and {len(self.issues) - 20} more")
        return "\n".join(lines)


class GraphValidator:
    """Validates structural integrity of a CardGraph."""

    def validate(self, graph: CardGraph) -> GraphValidationReport:
        report = GraphValidationReport()

        self._check_isolated_nodes(graph, report)
        self._check_broken_evolution_chains(graph, report)
        self._check_missing_reciprocal_edges(graph, report)
        self._check_invalid_self_loops(graph, report)

        logger.info(
            "Graph validation: {} issues ({} errors)",
            len(report.issues), len(report.errors),
        )
        return report

    def _check_isolated_nodes(
        self,
        graph: CardGraph,
        report: GraphValidationReport,
    ) -> None:
        for cid in graph.isolated_nodes():
            report.issues.append(ValidationIssue(
                category="isolated_node",
                card_id=cid,
                detail="card has no edges",
                severity="warning",
            ))

    def _check_broken_evolution_chains(
        self,
        graph: CardGraph,
        report: GraphValidationReport,
    ) -> None:
        for node in graph.all_nodes():
            evs = graph.edges_from(node.card_id, RelationshipType.EVOLVES_FROM)
            for e in evs:
                # A target node is broken if it has no CardNode data attached
                if graph.node(e.target) is None:
                    report.issues.append(ValidationIssue(
                        category="broken_evolution",
                        card_id=node.card_id,
                        detail=f"EVOLVES_FROM points to missing node {e.target}",
                        severity="error",
                    ))

    def _check_missing_reciprocal_edges(
        self,
        graph: CardGraph,
        report: GraphValidationReport,
    ) -> None:
        reciprocal_pairs = {
            RelationshipType.EVOLVES_FROM: RelationshipType.EVOLVES_TO,
            RelationshipType.EVOLVES_TO:   RelationshipType.EVOLVES_FROM,
            RelationshipType.SEARCHES_FOR: RelationshipType.SEARCHED_BY,
            RelationshipType.SEARCHED_BY:  RelationshipType.SEARCHES_FOR,
        }
        for node in graph.all_nodes():
            for e in graph.edges_from(node.card_id):
                expected_inv = reciprocal_pairs.get(e.relationship_type)
                if expected_inv is None:
                    continue
                if not graph.has_edge(e.target, e.source, expected_inv):
                    report.issues.append(ValidationIssue(
                        category="missing_reciprocal",
                        card_id=node.card_id,
                        detail=(
                            f"{e.relationship_type.value} to {e.target} "
                            f"has no {expected_inv.value} back-edge"
                        ),
                        severity="warning",
                    ))

    def _check_invalid_self_loops(
        self,
        graph: CardGraph,
        report: GraphValidationReport,
    ) -> None:
        """Self-loops are allowed only for role-tagging, not for relational types."""
        disallowed_self_loop = {
            RelationshipType.EVOLVES_FROM,
            RelationshipType.EVOLVES_TO,
            RelationshipType.SEARCHES_FOR,
            RelationshipType.SEARCHED_BY,
            RelationshipType.HEALS,
            RelationshipType.COUNTERS,
        }
        for e in graph.all_edges():
            if e.source == e.target and e.relationship_type in disallowed_self_loop:
                report.issues.append(ValidationIssue(
                    category="invalid_self_loop",
                    card_id=e.source,
                    detail=f"self-loop with disallowed type {e.relationship_type.value}",
                    severity="warning",
                ))

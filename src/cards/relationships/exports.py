"""
Graph export utilities.

Supports NetworkX, GraphML, JSON, and CSV edge/node list formats.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import networkx as nx
from loguru import logger

from src.cards.relationships.graph import CardGraph


def to_networkx(graph: CardGraph) -> nx.MultiDiGraph:
    """Return the underlying NetworkX graph (read-only view)."""
    return graph.nx_graph


def to_dict(graph: CardGraph) -> dict[str, Any]:
    """Serialise the graph to a JSON-compatible dictionary."""
    nodes = []
    for node in graph.all_nodes():
        d: dict[str, Any] = {
            "card_id": node.card_id,
            "name": node.name,
            "card_super_type": node.card_super_type.value,
        }
        if node.pokemon_type:
            d["pokemon_type"] = node.pokemon_type.value
        if node.stage:
            d["stage"] = node.stage.value
        if node.hp is not None:
            d["hp"] = node.hp
        if node.trainer_type:
            d["trainer_type"] = node.trainer_type.value
        if node.energy_type:
            d["energy_type"] = node.energy_type.value
        nodes.append(d)

    edges = []
    for edge in graph.all_edges():
        edges.append({
            "source": edge.source,
            "target": edge.target,
            "relationship_type": edge.relationship_type.value,
            "weight": edge.weight,
            "confidence": edge.confidence,
            "reason": edge.reason,
            "evidence": list(edge.evidence),
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "stats": {
            "node_count": graph.node_count,
            "edge_count": graph.edge_count,
            "relationship_counts": graph.relationship_counts(),
        },
    }


def to_json(graph: CardGraph, *, indent: int = 2) -> str:
    """Return a JSON string of the full graph."""
    return json.dumps(to_dict(graph), ensure_ascii=False, indent=indent)


def write_json(graph: CardGraph, path: Path | str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(to_json(graph), encoding="utf-8")
    logger.info("Graph written to JSON: {}", p)


def to_graphml(graph: CardGraph) -> str:
    """Return a GraphML string."""
    ug = _simple_digraph(graph)
    import io
    buf = io.BytesIO()
    nx.write_graphml(ug, buf)
    return buf.getvalue().decode("utf-8")


def write_graphml(graph: CardGraph, path: Path | str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(to_graphml(graph), encoding="utf-8")
    logger.info("Graph written to GraphML: {}", p)


def to_csv_edges(graph: CardGraph) -> str:
    """CSV edge list with header."""
    lines = ["source,target,relationship_type,weight,confidence,reason"]
    for e in sorted(graph.all_edges(), key=lambda x: (x.source, x.target)):
        reason_safe = e.reason.replace(",", ";").replace("\n", " ")
        lines.append(
            f"{e.source},{e.target},{e.relationship_type.value},"
            f"{e.weight:.4f},{e.confidence:.4f},{reason_safe}"
        )
    return "\n".join(lines)


def to_csv_nodes(graph: CardGraph) -> str:
    """CSV node list with header."""
    lines = ["card_id,name,card_super_type,pokemon_type,stage,hp,trainer_type,energy_type"]
    for n in sorted(graph.all_nodes(), key=lambda x: x.card_id):
        lines.append(",".join([
            n.card_id, n.name.replace(",", ";"),
            n.card_super_type.value,
            n.pokemon_type.value if n.pokemon_type else "",
            n.stage.value if n.stage else "",
            str(n.hp) if n.hp is not None else "",
            n.trainer_type.value if n.trainer_type else "",
            n.energy_type.value if n.energy_type else "",
        ]))
    return "\n".join(lines)


def write_csv(graph: CardGraph, edges_path: Path | str, nodes_path: Path | str) -> None:
    ep, np_ = Path(edges_path), Path(nodes_path)
    ep.parent.mkdir(parents=True, exist_ok=True)
    np_.parent.mkdir(parents=True, exist_ok=True)
    ep.write_text(to_csv_edges(graph), encoding="utf-8")
    np_.write_text(to_csv_nodes(graph), encoding="utf-8")
    logger.info("Graph written to CSV: edges={}, nodes={}", ep, np_)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _simple_digraph(graph: CardGraph) -> nx.DiGraph:
    """Convert to simple DiGraph for GraphML (keep highest-weight edge per pair)."""
    dg = nx.DiGraph()
    for node in graph.all_nodes():
        dg.add_node(
            node.card_id,
            name=node.name,
            card_super_type=node.card_super_type.value,
        )
    # Keep the highest-weight edge per (source, target) pair
    best: dict[tuple[str, str], Any] = {}
    for edge in graph.all_edges():
        key = (edge.source, edge.target)
        if key not in best or edge.weight > best[key].weight:
            best[key] = edge
    for edge in best.values():
        dg.add_edge(
            edge.source, edge.target,
            relationship_type=edge.relationship_type.value,
            weight=edge.weight,
            confidence=edge.confidence,
            reason=edge.reason[:200],
        )
    return dg

"""Curriculum knowledge graph and dependency-risk hypotheses."""

from __future__ import annotations

import math

import networkx as nx
import pandas as pd
from sklearn.metrics import matthews_corrcoef

from app.analytics.methodology import KNOWLEDGE_GRAPH, METHODOLOGY_VERSION

INFERENCE_MIN_STUDENTS = 40
INFERENCE_PHI = 0.25


def build_graph(
    topics: list[dict],
    edges: list[dict],
    diagnostics: dict | None = None,
) -> dict:
    graph = nx.DiGraph()
    performance = {row["topic_id"]: row for row in (diagnostics or {}).get("topics", [])}
    for topic in topics:
        topic_id = topic.get("topic_id") or topic.get("external_id")
        graph.add_node(
            topic_id,
            label=topic.get("topic_name") or topic.get("name") or topic_id,
            grade_level=topic.get("grade_level"),
        )
    ignored = []
    for edge in edges:
        source = edge.get("prerequisite_topic_id") or edge.get("source")
        target = edge.get("dependent_topic_id") or edge.get("target")
        status = (edge.get("relation_status") or edge.get("status") or "verified").lower()
        if status not in {"verified", "inferred"}:
            status = "verified"
        if not source or not target or source == target:
            ignored.append({"edge": edge, "reason": "invalid_endpoints"})
            continue
        graph.add_node(source)
        graph.add_node(target)
        graph.add_edge(
            source,
            target,
            status=status,
            source_kind=edge.get("source") or edge.get("source_kind") or "supplied",
            confidence=edge.get("confidence"),
            notes=edge.get("notes") or "",
        )

    cycles = [list(cycle) for cycle in nx.simple_cycles(graph)]
    acyclic = len(cycles) == 0
    depths: dict[str, int | None] = {}
    if acyclic and graph.number_of_nodes():
        for node in graph.nodes:
            if graph.in_degree(node) == 0:
                depths[node] = 0
        for node in nx.topological_sort(graph):
            parents = list(graph.predecessors(node))
            if not parents:
                depths[node] = 0
            else:
                parent_depths = [depths.get(parent, 0) or 0 for parent in parents]
                depths[node] = 1 + max(parent_depths)
    else:
        depths = {node: None for node in graph.nodes}

    nodes = []
    for node, attrs in graph.nodes(data=True):
        perf = performance.get(node, {})
        descendants = nx.descendants(graph, node) if acyclic else set()
        ancestors = nx.ancestors(graph, node) if acyclic else set()
        verified_in = [u for u, _, data in graph.in_edges(node, data=True) if data.get("status") == "verified"]
        inferred_in = [u for u, _, data in graph.in_edges(node, data=True) if data.get("status") == "inferred"]
        nodes.append(
            {
                "id": node,
                "label": attrs.get("label") or node,
                "grade_level": attrs.get("grade_level"),
                "depth": depths.get(node),
                "in_degree": graph.in_degree(node),
                "out_degree": graph.out_degree(node),
                "ancestor_count": len(ancestors),
                "descendant_count": len(descendants),
                "importance": 1 + len(descendants),
                "verified_prerequisites": verified_in,
                "inferred_prerequisites": inferred_in,
                "dependents": list(graph.successors(node)),
                "accuracy": perf.get("accuracy"),
                "n_students": perf.get("n_students"),
                "status": perf.get("status"),
                "flags": perf.get("flags") or [],
            }
        )

    export_edges = [
        {
            "source": source,
            "target": target,
            "status": data.get("status"),
            "source_kind": data.get("source_kind"),
            "confidence": data.get("confidence"),
            "notes": data.get("notes") or "",
            "established": data.get("status") == "verified",
            "note": (
                "Human-asserted curriculum relationship. Not an experimental proof."
                if data.get("status") == "verified"
                else "Inferred from co-failure. Not curriculum truth until a methodologist confirms it."
            ),
        }
        for source, target, data in graph.edges(data=True)
    ]
    risks = identify_risks(nodes, export_edges) if acyclic else []
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "status": "ok" if graph.number_of_nodes() else "empty",
        "acyclic": acyclic,
        "cycles": cycles,
        "ignored_edges": ignored,
        "node_count": graph.number_of_nodes(),
        "edge_count": graph.number_of_edges(),
        "verified_edge_count": sum(1 for edge in export_edges if edge["status"] == "verified"),
        "inferred_edge_count": sum(1 for edge in export_edges if edge["status"] == "inferred"),
        "nodes": nodes,
        "edges": export_edges,
        "risks": risks,
        "frontend_graph": {"nodes": nodes, "edges": export_edges},
        "limitations": [
            KNOWLEDGE_GRAPH,
            "A dependency risk is a review hypothesis. It is not evidence that the prerequisite caused later failure.",
        ],
    }


def identify_risks(nodes: list[dict], edges: list[dict]) -> list[dict]:
    by_id = {node["id"]: node for node in nodes}
    verified = {(edge["source"], edge["target"]) for edge in edges if edge["status"] == "verified"}
    risks = []
    for node in nodes:
        if node.get("status") != "weak":
            continue
        weak_prereqs = []
        for source, target in verified:
            if target != node["id"]:
                continue
            parent = by_id.get(source)
            if parent and parent.get("status") == "weak":
                weak_prereqs.append(source)
        descendant_count = node.get("descendant_count") or 0
        accuracy = node.get("accuracy")
        weakness = 0.0 if accuracy is None else max(0.0, 0.75 - accuracy)
        downstream_risk = round(weakness * descendant_count, 4)
        reasons = [
            f"{node['id']} is classified weak on {node.get('n_students')} students "
            f"with mean credit {accuracy}."
        ]
        if weak_prereqs:
            reasons.append(
                "Verified prerequisites also classified weak: " + ", ".join(weak_prereqs) + ". "
                "This is consistent with an upstream gap hypothesis and does not prove it."
            )
        else:
            reasons.append("No verified prerequisite is currently classified weak. Look beyond prerequisite gaps.")
        if descendant_count:
            reasons.append(
                f"The topic reaches {descendant_count} later topics in the supplied graph, "
                "so a gap here is a downstream review priority, not a measured spillover effect."
            )
        risks.append(
            {
                "topic_id": node["id"],
                "topic_name": node.get("label"),
                "observation": "weak_topic",
                "upstream_gap_hypothesis": bool(weak_prereqs),
                "weak_verified_prerequisites": weak_prereqs,
                "descendant_count": descendant_count,
                "downstream_risk_index": downstream_risk,
                "reasoning": " ".join(reasons),
                "claim_level": "hypothesis",
            }
        )
    risks.sort(key=lambda row: row["downstream_risk_index"], reverse=True)
    return risks


def infer_dependencies(
    responses: pd.DataFrame,
    topics: list[dict] | None = None,
    existing_edges: list[dict] | None = None,
    *,
    min_students: int = INFERENCE_MIN_STUDENTS,
    min_phi: float = INFERENCE_PHI,
) -> dict:
    """Propose inferred edges. Does not write them."""
    if responses is None or responses.empty:
        return {"status": "insufficient_data", "candidates": [], "limitations": [KNOWLEDGE_GRAPH]}
    frame = responses.copy()
    student = frame.groupby(["student_id", "topic_id"])["credit"].mean().reset_index()
    failed = student.assign(failed=student["credit"] < 0.5)
    wide = failed.pivot(index="student_id", columns="topic_id", values="failed")
    grades = {}
    for topic in topics or []:
        grades[topic.get("topic_id") or topic.get("external_id")] = topic.get("grade_level")
    existing = {
        (
            edge.get("prerequisite_topic_id") or edge.get("source"),
            edge.get("dependent_topic_id") or edge.get("target"),
        )
        for edge in existing_edges or []
    }
    candidates = []
    columns = list(wide.columns)
    for left in columns:
        for right in columns:
            if left == right or (left, right) in existing:
                continue
            pair = wide[[left, right]].dropna()
            n = int(len(pair))
            if n < min_students:
                continue
            if pair[left].nunique() < 2 or pair[right].nunique() < 2:
                continue
            phi = float(matthews_corrcoef(pair[left].astype(int), pair[right].astype(int)))
            if math.isnan(phi) or phi < min_phi:
                continue
            left_grade = grades.get(left)
            right_grade = grades.get(right)
            if left_grade is not None and right_grade is not None and left_grade > right_grade:
                continue
            candidates.append(
                {
                    "prerequisite_topic_id": left,
                    "dependent_topic_id": right,
                    "relation_status": "inferred",
                    "source": "cofailure_phi",
                    "confidence": round(phi, 4),
                    "n_students": n,
                    "notes": (
                        f"Phi/Matthews correlation of student-level failure is {phi:.3f} on {n} students. "
                        "This is a candidate association, not a verified prerequisite."
                    ),
                }
            )
    candidates.sort(key=lambda row: row["confidence"], reverse=True)
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "status": "ok",
        "min_students": min_students,
        "min_phi": min_phi,
        "candidates": candidates,
        "limitations": [
            "Inferred edges are co-failure associations. Shared difficulty, the same test day, or a weak school can produce them without a prerequisite relationship.",
            KNOWLEDGE_GRAPH,
        ],
    }

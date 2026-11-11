import pandas as pd

from app.analytics.curriculum_optimizer.engine import optimize_allocation
from app.analytics.knowledge_graph.engine import build_graph, infer_dependencies


def test_graph_upstream_hypothesis_and_cycle():
    topics = [
        {"topic_id": "T04", "topic_name": "Expressions", "grade_level": 7},
        {"topic_id": "T06", "topic_name": "Factoring", "grade_level": 8},
        {"topic_id": "T12", "topic_name": "Quadratics", "grade_level": 9},
    ]
    edges = [
        {"prerequisite_topic_id": "T04", "dependent_topic_id": "T06", "relation_status": "verified"},
        {"prerequisite_topic_id": "T06", "dependent_topic_id": "T12", "relation_status": "verified"},
    ]
    diagnostics = {
        "topics": [
            {"topic_id": "T04", "status": "strong", "accuracy": 0.9, "n_students": 80},
            {"topic_id": "T06", "status": "weak", "accuracy": 0.4, "n_students": 80},
            {"topic_id": "T12", "status": "weak", "accuracy": 0.42, "n_students": 80},
        ]
    }
    graph = build_graph(topics, edges, diagnostics)
    assert graph["acyclic"] is True
    quadratics = next(node for node in graph["nodes"] if node["id"] == "T12")
    assert quadratics["importance"] >= 1
    risk = next(row for row in graph["risks"] if row["topic_id"] == "T12")
    assert risk["upstream_gap_hypothesis"] is True
    assert risk["claim_level"] == "hypothesis"
    assert "T06" in risk["weak_verified_prerequisites"]

    cyclic = build_graph(topics, edges + [{"prerequisite_topic_id": "T12", "dependent_topic_id": "T04", "relation_status": "verified"}])
    assert cyclic["acyclic"] is False
    assert cyclic["cycles"]


def test_missing_prerequisites_do_not_invent_edges():
    graph = build_graph([{"topic_id": "T12", "topic_name": "Quadratics"}], [])
    assert graph["edge_count"] == 0
    assert graph["risks"] == []


def test_inference_requires_sample_size_and_is_labeled():
    rows = []
    for index in range(50):
        failed = index < 30
        rows.append({"student_id": f"S{index}", "topic_id": "T06", "credit": 0.2 if failed else 0.9})
        rows.append({"student_id": f"S{index}", "topic_id": "T12", "credit": 0.2 if failed else 0.9})
    result = infer_dependencies(pd.DataFrame(rows), [{"topic_id": "T06", "grade_level": 8}, {"topic_id": "T12", "grade_level": 9}])
    assert result["candidates"]
    assert result["candidates"][0]["relation_status"] == "inferred"
    small = infer_dependencies(pd.DataFrame(rows).head(10))
    assert small["candidates"] == []


def test_optimizer_moves_hours_and_is_reproducible():
    topics = [
        {"topic_id": "T06", "hours": 8, "min_hours": 4, "max_hours": 20, "importance_weight": 1.4},
        {"topic_id": "T11", "hours": 12, "min_hours": 4, "max_hours": 20, "importance_weight": 0.8},
    ]
    diagnostics = {
        "topics": [
            {"topic_id": "T06", "status": "weak", "accuracy": 0.4, "n_students": 100},
            {"topic_id": "T11", "status": "strong", "accuracy": 0.9, "n_students": 100},
        ]
    }
    first = optimize_allocation(topics, diagnostics=diagnostics, total_hours=20)
    second = optimize_allocation(topics, diagnostics=diagnostics, total_hours=20)
    assert first["status"] == "ok"
    assert first == second
    hours = {item["topic_id"]: item["hours"] for item in next(s for s in first["scenarios"] if s["name"] == "nl_diminishing_returns")["hours"]}
    assert hours["T06"] > 8
    assert abs(sum(hours.values()) - 20) < 1e-4
    assert first["assumptions"]["learning_response_estimated_from_data"] is False


def test_impossible_constraints():
    topics = [
        {"topic_id": "T06", "hours": 8, "min_hours": 12, "max_hours": 20},
        {"topic_id": "T11", "hours": 8, "min_hours": 12, "max_hours": 20},
    ]
    result = optimize_allocation(topics, total_hours=10)
    assert result["status"] == "infeasible"
    assert result["scenarios"] == []


def test_empty_allocation():
    result = optimize_allocation([])
    assert result["status"] == "insufficient_data"

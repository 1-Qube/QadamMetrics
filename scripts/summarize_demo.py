"""Print descriptive findings from the synthetic demo. Does not invent metrics."""

from app.analytics.diagnostics.engine import diagnose
from app.analytics.knowledge_graph.engine import build_graph
from app.analytics.curriculum_optimizer.engine import optimize_allocation
from app.demo.generator import generate_demo


def main() -> None:
    bundle = generate_demo()
    frame = bundle.responses.copy()
    frame["credit"] = frame["score"].astype(float)
    diagnostics = diagnose(frame, bundle.topics, evidence_class="synthetic")
    edges = bundle.prerequisites.rename(columns={"relation_status": "relation_status"}).to_dict(orient="records")
    topics = bundle.topics.to_dict(orient="records")
    graph = build_graph(topics, edges, diagnostics)
    allocations = bundle.allocations.to_dict(orient="records")
    plan = optimize_allocation(
        allocations,
        diagnostics={**diagnostics, "graph_nodes": graph["nodes"]},
        edges=edges,
        total_hours=100,
    )
    print("students", diagnostics["overview"]["students"], "responses", diagnostics["overview"]["responses"])
    for row in diagnostics["topics"]:
        if row.get("status") in {"weak", "strong", "insufficient_data", "not_assessed"}:
            print(row["topic_id"], row.get("status"), row.get("accuracy"), row.get("n_students"), row.get("flags"))
    print("risks", [(row["topic_id"], row["upstream_gap_hypothesis"]) for row in graph["risks"]])
    print("optimizer", plan["status"], plan.get("sensitivity_note"))
    for scenario in plan.get("scenarios", []):
        if scenario["name"] == "nl_diminishing_returns":
            moves = [item for item in scenario["hours"] if abs(item["delta_from_current"]) >= 1]
            print("nl moves", moves)


if __name__ == "__main__":
    main()

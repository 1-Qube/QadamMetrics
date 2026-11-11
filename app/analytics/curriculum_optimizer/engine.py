"""Hour-allocation explorer. Hypothetical objectives, explicit constraints."""

from __future__ import annotations

import math

import numpy as np
from scipy.optimize import linprog, minimize

from app.analytics.methodology import METHODOLOGY_VERSION, OPTIMIZATION


def _weakness(topic_status: str | None, accuracy: float | None, target: float) -> float:
    if topic_status in {None, "insufficient_data", "not_assessed"} or accuracy is None:
        return 0.0
    return max(0.0, target - float(accuracy))


def optimize_allocation(
    topics: list[dict],
    *,
    diagnostics: dict | None = None,
    edges: list[dict] | None = None,
    total_hours: float | None = None,
    beta: float = 0.15,
    transfer_tau: float = 0.25,
    target_accuracy: float = 0.75,
    max_change_hours: float | None = None,
    proposed_hours: dict[str, float] | None = None,
) -> dict:
    assumptions = {
        "label": "hypothetical",
        "beta": beta,
        "transfer_tau": transfer_tau,
        "target_accuracy": target_accuracy,
        "max_change_hours": max_change_hours,
        "learning_response_estimated_from_data": False,
        "statement": (
            "No empirical hour-to-learning curve is fitted. "
            "Objective values are not predicted test-score gains."
        ),
    }
    if not topics:
        return _empty("No hour allocations were provided.", assumptions)

    performance = {row["topic_id"]: row for row in (diagnostics or {}).get("topics", [])}
    graph_nodes = {row.get("id") or row.get("topic_id"): row for row in (diagnostics or {}).get("graph_nodes", [])}
    weak_topics = {
        row["topic_id"]
        for row in (diagnostics or {}).get("topics", [])
        if row.get("status") == "weak"
    }
    verified_children: dict[str, list[str]] = {}
    for edge in edges or []:
        if (edge.get("relation_status") or edge.get("status") or "verified") != "verified":
            continue
        source = edge.get("prerequisite_topic_id") or edge.get("source")
        target = edge.get("dependent_topic_id") or edge.get("target")
        verified_children.setdefault(source, []).append(target)

    records = []
    for topic in topics:
        topic_id = topic.get("topic_id")
        current = float(topic["hours"])
        lower = float(topic.get("min_hours", 0))
        upper = float(topic.get("max_hours", current))
        if max_change_hours is not None:
            lower = max(lower, current - max_change_hours)
            upper = min(upper, current + max_change_hours)
        perf = performance.get(topic_id, {})
        descendants = graph_nodes.get(topic_id, {}).get("descendant_count")
        if descendants is None:
            descendants = topic.get("descendant_count", 0)
        upstream_need = 1.0 if any(child in weak_topics for child in verified_children.get(topic_id, [])) or (
            topic_id in weak_topics and any(
                (edge.get("dependent_topic_id") or edge.get("target")) == topic_id
                and (edge.get("prerequisite_topic_id") or edge.get("source")) in weak_topics
                and (edge.get("relation_status") or edge.get("status") or "verified") == "verified"
                for edge in edges or []
            )
        ) else 0.0
        # upstream_need should be 1 if THIS topic is a weak prerequisite of something weak,
        # or if the topic itself has a weak prerequisite. The second case is for the topic's own hours.
        has_weak_prereq = any(
            (edge.get("dependent_topic_id") or edge.get("target")) == topic_id
            and (edge.get("prerequisite_topic_id") or edge.get("source")) in weak_topics
            and (edge.get("relation_status") or edge.get("status") or "verified") == "verified"
            for edge in edges or []
        )
        supports_weak_dependent = any(child in weak_topics for child in verified_children.get(topic_id, []))
        records.append(
            {
                "topic_id": topic_id,
                "topic_name": topic.get("topic_name") or perf.get("topic_name") or topic_id,
                "current": current,
                "min_hours": lower,
                "max_hours": upper,
                "importance": float(topic.get("importance_weight", topic.get("importance", 1.0))),
                "accuracy": perf.get("accuracy"),
                "status": perf.get("status"),
                "n_students": perf.get("n_students"),
                "descendants": int(descendants or 0),
                "weakness": _weakness(perf.get("status"), perf.get("accuracy"), target_accuracy),
                "upstream_need": 1.0 if has_weak_prereq or supports_weak_dependent else 0.0,
            }
        )

    total = float(total_hours) if total_hours is not None else float(sum(row["current"] for row in records))
    feasibility = _feasibility(records, total)
    if not feasibility["feasible"]:
        return {
            "methodology_version": METHODOLOGY_VERSION,
            "status": "infeasible",
            "assumptions": assumptions,
            "total_hours": total,
            "message": feasibility["message"],
            "details": feasibility,
            "scenarios": [],
            "comparison": [],
            "limitations": [OPTIMIZATION],
        }

    max_desc = max((row["descendants"] for row in records), default=0) or 1
    weights = np.array(
        [
            row["importance"] * row["weakness"] * (1 + row["descendants"] / max_desc)
            for row in records
        ],
        dtype=float,
    )
    current = np.array([row["current"] for row in records], dtype=float)
    bounds = [(row["min_hours"], row["max_hours"]) for row in records]
    lp_hours, lp_status = _solve_lp(weights, bounds, total)
    nl_hours, nl_status = _solve_nl(records, bounds, total, current, beta, transfer_tau)

    scenarios = [
        _scenario("current", current, records, weights, beta, transfer_tau, "supplied plan"),
    ]
    if lp_hours is not None:
        scenarios.append(_scenario("lp_priority", lp_hours, records, weights, beta, transfer_tau, lp_status))
    if nl_hours is not None:
        scenarios.append(
            _scenario("nl_diminishing_returns", nl_hours, records, weights, beta, transfer_tau, nl_status)
        )
    if proposed_hours:
        proposed = np.array([float(proposed_hours.get(row["topic_id"], row["current"])) for row in records])
        proposed_check = _check_proposed(records, proposed, total)
        if proposed_check["ok"]:
            scenarios.append(
                _scenario("user_proposed", proposed, records, weights, beta, transfer_tau, "methodologist proposal")
            )
        else:
            scenarios.append(
                {
                    "name": "user_proposed",
                    "status": "rejected",
                    "message": proposed_check["message"],
                    "hours": [],
                }
            )

    comparison = _compare(records, scenarios)
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "status": "ok",
        "assumptions": assumptions,
        "total_hours": total,
        "solver": {"linear": "scipy.optimize.linprog/highs", "nonlinear": "scipy.optimize.minimize/SLSQP"},
        "topics": [
            {
                "topic_id": row["topic_id"],
                "topic_name": row["topic_name"],
                "accuracy": row["accuracy"],
                "diagnostic_status": row["status"],
                "n_students": row["n_students"],
                "weakness_used": round(row["weakness"], 4),
                "importance": row["importance"],
                "descendants": row["descendants"],
                "priority_weight": round(float(weight), 4),
                "upstream_need": row["upstream_need"],
                "drives_reallocation": row["weakness"] > 0,
            }
            for row, weight in zip(records, weights, strict=True)
        ],
        "scenarios": scenarios,
        "comparison": comparison,
        "chart": {
            "topics": [row["topic_id"] for row in records],
            "series": [
                {"name": scenario["name"], "hours": [item["hours"] for item in scenario.get("hours", [])]}
                for scenario in scenarios
                if scenario.get("hours")
            ],
        },
        "sensitivity_note": _sensitivity_note(comparison),
        "decision": "The methodologist decides. The solver only explores stated objectives and constraints.",
        "limitations": [OPTIMIZATION],
    }


def _feasibility(records: list[dict], total: float) -> dict:
    problems = []
    for row in records:
        if row["min_hours"] > row["max_hours"] + 1e-9:
            problems.append(f"{row['topic_id']} has min_hours above max_hours.")
        if row["current"] < 0:
            problems.append(f"{row['topic_id']} has negative current hours.")
    min_sum = sum(row["min_hours"] for row in records)
    max_sum = sum(row["max_hours"] for row in records)
    if min_sum - total > 1e-6:
        problems.append(f"Sum of minimum hours ({min_sum}) exceeds total hours ({total}).")
    if total - max_sum > 1e-6:
        problems.append(f"Sum of maximum hours ({max_sum}) is below total hours ({total}).")
    return {
        "feasible": not problems,
        "message": " ".join(problems) if problems else "Constraints can contain the hour budget.",
        "min_sum": min_sum,
        "max_sum": max_sum,
        "problems": problems,
    }


def _solve_lp(weights: np.ndarray, bounds: list[tuple[float, float]], total: float) -> tuple[np.ndarray | None, str]:
    size = len(weights)
    result = linprog(
        -weights,
        A_eq=np.ones((1, size)),
        b_eq=np.array([total]),
        bounds=bounds,
        method="highs",
    )
    if not result.success:
        return None, f"Linear program failed: {result.message}"
    return np.array(result.x, dtype=float), "Optimal for the linear priority objective. Corner solutions are expected."


def _nl_objective(hours: np.ndarray, records: list[dict], beta: float, tau: float) -> float:
    value = 0.0
    for hour, row in zip(hours, records, strict=True):
        reference = max(row["current"], 1.0)
        gain = row["importance"] * row["weakness"] * (1 - math.exp(-beta * hour / reference))
        gain *= 1 + tau * row["upstream_need"]
        value += gain
    return -value


def _solve_nl(
    records: list[dict],
    bounds: list[tuple[float, float]],
    total: float,
    start: np.ndarray,
    beta: float,
    tau: float,
) -> tuple[np.ndarray | None, str]:
    constraints = [{"type": "eq", "fun": lambda hours: float(np.sum(hours) - total)}]
    result = minimize(
        _nl_objective,
        start,
        args=(records, beta, tau),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-12, "disp": False},
    )
    if not result.success:
        return None, f"Nonlinear program failed: {result.message}"
    return np.array(result.x, dtype=float), "Local optimum of the hypothetical diminishing-returns objective from the current plan."


def _objective_values(hours: np.ndarray, records: list[dict], weights: np.ndarray, beta: float, tau: float) -> dict:
    linear = float(np.dot(weights, hours))
    nonlinear = -_nl_objective(hours, records, beta, tau)
    return {"linear_priority": round(linear, 6), "hypothetical_diminishing_returns": round(nonlinear, 6)}


def _scenario(name: str, hours: np.ndarray, records: list[dict], weights: np.ndarray, beta: float, tau: float, note: str) -> dict:
    return {
        "name": name,
        "status": "ok",
        "note": note,
        "objective": _objective_values(hours, records, weights, beta, tau),
        "hours": [
            {
                "topic_id": row["topic_id"],
                "topic_name": row["topic_name"],
                "hours": round(float(hour), 4),
                "delta_from_current": round(float(hour - row["current"]), 4),
            }
            for row, hour in zip(records, hours, strict=True)
        ],
    }


def _check_proposed(records: list[dict], proposed: np.ndarray, total: float) -> dict:
    if abs(float(proposed.sum()) - total) > 1e-4:
        return {"ok": False, "message": "Proposed hours do not sum to the total hour budget."}
    for row, hour in zip(records, proposed, strict=True):
        if hour < row["min_hours"] - 1e-6 or hour > row["max_hours"] + 1e-6:
            return {"ok": False, "message": f"Proposed hours for {row['topic_id']} violate bounds."}
    return {"ok": True, "message": "ok"}


def _compare(records: list[dict], scenarios: list[dict]) -> list[dict]:
    by_name = {scenario["name"]: scenario for scenario in scenarios if scenario.get("hours")}
    current = {item["topic_id"]: item["hours"] for item in by_name.get("current", {}).get("hours", [])}
    rows = []
    topic_ids = [row["topic_id"] for row in records]
    for topic_id in topic_ids:
        row = {"topic_id": topic_id, "current": current.get(topic_id)}
        directions = []
        for name, scenario in by_name.items():
            hours = {item["topic_id"]: item["hours"] for item in scenario["hours"]}
            row[name] = hours.get(topic_id)
            if name != "current" and topic_id in hours and topic_id in current:
                delta = hours[topic_id] - current[topic_id]
                directions.append(np.sign(delta) if abs(delta) >= 0.5 else 0)
        nonzero = [direction for direction in directions if direction != 0]
        row["objective_sensitive"] = len(set(nonzero)) > 1
        rows.append(row)
    return rows


def _sensitivity_note(comparison: list[dict]) -> str:
    sensitive = [row["topic_id"] for row in comparison if row.get("objective_sensitive")]
    if not sensitive:
        return "Linear and nonlinear scenarios do not move any topic in opposite directions by 0.5 hours or more."
    return (
        "These topics move in opposite directions under the linear and nonlinear objectives: "
        + ", ".join(sensitive)
        + ". Treat that shift as sensitive to the chosen hypothetical objective."
    )


def _empty(message: str, assumptions: dict) -> dict:
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "status": "insufficient_data",
        "message": message,
        "assumptions": assumptions,
        "scenarios": [],
        "comparison": [],
        "limitations": [OPTIMIZATION],
    }

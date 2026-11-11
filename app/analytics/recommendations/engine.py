"""Rule-based recommendations grounded in engine output."""

from __future__ import annotations

from app.analytics.methodology import METHODOLOGY_VERSION, RECOMMENDATIONS


def recommend(
    diagnostics: dict | None = None,
    graph: dict | None = None,
    optimization: dict | None = None,
    textbook: dict | None = None,
    causal: dict | None = None,
    *,
    evidence_class: str = "uploaded",
) -> dict:
    items: list[dict] = []
    topics = {row["topic_id"]: row for row in (diagnostics or {}).get("topics", [])}
    risks = {row["topic_id"]: row for row in (graph or {}).get("risks", [])}

    for topic_id, topic in topics.items():
        status = topic.get("status")
        if status in {"insufficient_data", "not_assessed"}:
            items.append(_rec(
                rule_id="coverage",
                topic_ids=[topic_id],
                issue=f"{topic.get('topic_name', topic_id)} does not have enough assessment evidence for a performance label.",
                observation="Sample size is below the classification threshold or the topic was not assessed.",
                evidence={"n_students": topic.get("n_students"), "status": status},
                possible_explanations=["The topic may be unassessed, newly added, or present only in a small pilot."],
                action="Collect more student-level evidence before changing hours or materials for this topic.",
                impact_direction="more_evidence",
                evidence_confidence="insufficient",
            ))
            continue
        if status != "weak":
            continue
        risk = risks.get(topic_id, {})
        weak_prereqs = risk.get("weak_verified_prerequisites") or []
        evidence = {
            "accuracy": topic.get("accuracy"),
            "ci_low": topic.get("ci_low"),
            "ci_high": topic.get("ci_high"),
            "n_students": topic.get("n_students"),
            "weak_verified_prerequisites": weak_prereqs,
        }
        if weak_prereqs:
            items.append(_rec(
                rule_id="upstream_gap_hypothesis",
                topic_ids=[topic_id, *weak_prereqs],
                issue=f"Students show low credit on {topic.get('topic_name', topic_id)}, and verified prerequisites are also low.",
                observation=(
                    f"Mean student credit is {topic.get('accuracy')} "
                    f"(95% CI {topic.get('ci_low')} to {topic.get('ci_high')}, n={topic.get('n_students')})."
                ),
                evidence=evidence,
                possible_explanations=[
                    "Students may be meeting the later topic without a secure prerequisite. This is a hypothesis.",
                    "Both topics may be hard for a shared reason, such as assessment design or missed instructional time.",
                ],
                action=(
                    "Review time and practice on "
                    + ", ".join(weak_prereqs)
                    + " before adding more of the later topic. Compare that review with the hour scenarios; do not treat it as a proven fix."
                ),
                impact_direction="uncertain",
                evidence_confidence=_evidence_confidence(topic),
            ))
        else:
            items.append(_rec(
                rule_id="isolated_weak_topic",
                topic_ids=[topic_id],
                issue=f"Students show low credit on {topic.get('topic_name', topic_id)} without a weak verified prerequisite.",
                observation=(
                    f"Mean student credit is {topic.get('accuracy')} "
                    f"(95% CI {topic.get('ci_low')} to {topic.get('ci_high')}, n={topic.get('n_students')})."
                ),
                evidence=evidence,
                possible_explanations=[
                    "Instruction, materials, or the assessment itself may not match the topic.",
                    "A prerequisite gap may exist but is not in the supplied graph.",
                ],
                action="Review alignment between the assessment, the textbook treatment, and the taught sequence for this topic.",
                impact_direction="uncertain",
                evidence_confidence=_evidence_confidence(topic),
            ))
        if "inconsistent_across_schools" in (topic.get("flags") or []):
            items.append(_rec(
                rule_id="school_disparity",
                topic_ids=[topic_id],
                issue=f"School means differ substantially on {topic.get('topic_name', topic_id)}.",
                observation="The inconsistent-across-schools flag fired. It compares school means; it does not estimate a school effect.",
                evidence={"flags": topic.get("flags"), "n_students": topic.get("n_students")},
                possible_explanations=["Implementation, student intake, or assessment conditions may differ by school."],
                action="Look at school-level implementation before making a single curriculum-hour change for every school.",
                impact_direction="uncertain",
                evidence_confidence="low",
            ))

    if optimization and optimization.get("status") == "ok":
        items.extend(_optimization_recs(optimization))
    elif optimization and optimization.get("status") == "infeasible":
        items.append(_rec(
            rule_id="infeasible_hours",
            topic_ids=[],
            issue="The requested hour constraints cannot be satisfied.",
            observation=optimization.get("message", "Infeasible constraints."),
            evidence={"details": optimization.get("details")},
            possible_explanations=["Minimum hours sum above the budget, or maximum hours sum below it."],
            action="Relax a bound or change the total hours. No alternative plan was invented.",
            impact_direction="not_applicable",
            evidence_confidence="high",
        ))

    if textbook:
        items.append(_rec(
            rule_id="textbook_structure",
            topic_ids=[],
            issue="Textbook texts can be compared structurally, separate from outcomes.",
            observation=textbook.get("structural_statement", "Structural comparison available."),
            evidence={
                "highest_structural_coverage": textbook.get("highest_structural_coverage"),
                "materials": [
                    {"material_id": row.get("material_id"), "curriculum_coverage_ratio": row.get("curriculum_coverage_ratio")}
                    for row in textbook.get("structural_comparison", [])
                ],
            },
            possible_explanations=["Differences in exercises or coverage may or may not matter for learning."],
            action="Use structural gaps to decide what to read closely. Do not rank textbooks as more effective from structure alone.",
            impact_direction="uncertain",
            evidence_confidence="low",
        ))

    if causal:
        items.append(_rec(
            rule_id="causal_guardrail",
            topic_ids=[],
            issue="Material outcome differences need an explicit claim level.",
            observation=causal.get("message") or causal.get("claim_level", "not run"),
            evidence={
                "claim_level": causal.get("claim_level"),
                "causal_conclusion": causal.get("causal_conclusion"),
                "association": causal.get("association"),
            },
            possible_explanations=["Prior achievement, school, teacher, and hours can produce the same outcome gap."],
            action="Report the claim level next to any material comparison. Do not convert it into a causal conclusion.",
            impact_direction="uncertain",
            evidence_confidence="moderate" if causal.get("claim_level") else "low",
        ))

    limitations = [RECOMMENDATIONS]
    if evidence_class == "synthetic":
        limitations.insert(0, "Recommendations on this dataset illustrate the rules. They are not advice about real students.")
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "evidence_class": evidence_class,
        "status": "ok",
        "count": len(items),
        "recommendations": items,
        "limitations": limitations,
    }


def _evidence_confidence(topic: dict) -> str:
    n = topic.get("n_students") or 0
    low = topic.get("ci_low")
    high = topic.get("ci_high")
    width = None if low is None or high is None else high - low
    if n >= 100 and width is not None and width < 0.15:
        return "moderate"
    if n >= 30:
        return "low"
    return "insufficient"


def _optimization_recs(optimization: dict) -> list[dict]:
    scenarios = {row["name"]: row for row in optimization.get("scenarios", []) if row.get("hours")}
    current = {item["topic_id"]: item["hours"] for item in scenarios.get("current", {}).get("hours", [])}
    nonlinear = {item["topic_id"]: item for item in scenarios.get("nl_diminishing_returns", {}).get("hours", [])}
    sensitive = {row["topic_id"] for row in optimization.get("comparison", []) if row.get("objective_sensitive")}
    moves = []
    for topic_id, item in nonlinear.items():
        delta = item["hours"] - current.get(topic_id, item["hours"])
        if abs(delta) >= 2:
            moves.append((topic_id, round(delta, 2), topic_id in sensitive))
    if not moves:
        return []
    increases = [f"{topic_id} ({delta:+.1f}h)" for topic_id, delta, _ in moves if delta > 0]
    decreases = [f"{topic_id} ({delta:+.1f}h)" for topic_id, delta, _ in moves if delta < 0]
    sensitive_topics = [topic_id for topic_id, _, flag in moves if flag]
    action = (
        "Explore the hypothetical diminishing-returns scenario in a curriculum review. "
        "It is not a prediction that scores will rise."
    )
    if sensitive_topics:
        action += " Topics with objective-sensitive shifts should not be changed on this evidence alone: " + ", ".join(sensitive_topics) + "."
    return [_rec(
        rule_id="hypothetical_hour_shift",
        topic_ids=[topic_id for topic_id, _, _ in moves],
        issue="Under a labeled hypothetical objective, the hour plan moves by at least 2 hours on some topics.",
        observation=(
            "Increases: " + (", ".join(increases) or "none")
            + ". Decreases: " + (", ".join(decreases) or "none") + "."
        ),
        evidence={"moves": [{"topic_id": t, "delta_hours": d, "objective_sensitive": s} for t, d, s in moves]},
        possible_explanations=["The shift follows the chosen weights, weakness gate, and diminishing-returns formula."],
        action=action,
        impact_direction="hypothetical_positive_on_objective",
        evidence_confidence="low",
    )]


def _rec(
    *,
    rule_id: str,
    topic_ids: list[str],
    issue: str,
    observation: str,
    evidence: dict,
    possible_explanations: list[str],
    action: str,
    impact_direction: str,
    evidence_confidence: str,
) -> dict:
    return {
        "id": rule_id + ":" + ",".join(topic_ids),
        "rule_id": rule_id,
        "issue": issue,
        "confirmed_observation": observation,
        "possible_explanations": possible_explanations,
        "evidence": evidence,
        "topics": topic_ids,
        "recommended_action": action,
        "expected_impact_direction": impact_direction,
        "evidence_confidence": evidence_confidence,
        "intervention_confidence": "not_estimated",
        "not_a_proven_intervention": True,
        "additional_information_needed": [
            "Teacher implementation notes",
            "Prior attainment measured before the current course",
            "Whether the assessment matches the taught curriculum",
        ],
        "explanation": (
            f"{observation} Possible explanations are separated from that observation. "
            f"Suggested review: {action}"
        ),
    }

"""Topic-level diagnostic intelligence.

Classification is deliberately conservative. Small samples are not given the
same label as large samples with the same point estimate.
"""

from __future__ import annotations

import math
from statistics import mean

import pandas as pd
from scipy import stats

from app.analytics.methodology import (
    CONFIDENCE_LEVEL,
    DIAGNOSTICS,
    INCONSISTENT_RANGE,
    INCONSISTENT_SCHOOL_MIN_N,
    METHODOLOGY_VERSION,
    MIN_STUDENTS_DEFAULT,
    STRONG_CI_LOWER,
    WEAK_CI_UPPER,
)

PRIOR_STRENGTH = 10.0


def wilson_interval(successes: int, n: int, z: float = 1.96) -> tuple[float | None, float | None]:
    if n <= 0:
        return None, None
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return max(0.0, center - margin), min(1.0, center + margin)


def student_t_interval(values: list[float], level: float = CONFIDENCE_LEVEL) -> tuple[float | None, float | None]:
    n = len(values)
    if n == 0:
        return None, None
    center = float(mean(values))
    if n == 1:
        return center, center
    se = float(pd.Series(values).std(ddof=1)) / math.sqrt(n)
    if se == 0:
        return center, center
    critical = float(stats.t.ppf(1 - (1 - level) / 2, n - 1))
    return center - critical * se, center + critical * se


def _round(value: float | None, digits: int = 4) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    return round(float(value), digits)


def _classify(n_students: int, ci_low: float | None, ci_high: float | None, min_students: int) -> str:
    if n_students < min_students or ci_low is None or ci_high is None:
        return "insufficient_data"
    if ci_high < WEAK_CI_UPPER:
        return "weak"
    if ci_low >= STRONG_CI_LOWER:
        return "strong"
    return "inconclusive"


def _topic_frame(student_means: pd.Series, item_credit: pd.Series, min_students: int) -> dict:
    values = [float(value) for value in student_means.tolist()]
    n_students = len(values)
    accuracy = float(mean(values)) if values else None
    ci_low, ci_high = student_t_interval(values)
    status = _classify(n_students, ci_low, ci_high, min_students)
    binary_successes = int((item_credit >= 0.5).sum()) if len(item_credit) else 0
    n_items = int(len(item_credit))
    wilson_low, wilson_high = wilson_interval(binary_successes, n_items)
    shrunk = None
    if n_items:
        shrunk = (float(item_credit.sum()) + PRIOR_STRENGTH * 0.5) / (n_items + PRIOR_STRENGTH)
    tdi = None if accuracy is None else 1 - accuracy
    interpretable = status != "insufficient_data"
    return {
        "n_students": n_students,
        "n_items": n_items,
        "n_correct_binary": binary_successes,
        "n_incorrect_binary": n_items - binary_successes,
        "accuracy": _round(accuracy),
        "ci_low": _round(ci_low),
        "ci_high": _round(ci_high),
        "ci_method": "student_t_mean_of_student_means",
        "confidence_level": CONFIDENCE_LEVEL,
        "wilson_item_low": _round(wilson_low),
        "wilson_item_high": _round(wilson_high),
        "wilson_note": "Item-level Wilson interval assumes independent items and is supplementary.",
        "status": status,
        "difficulty_index": _round(tdi),
        "difficulty_interpretable": interpretable,
        "shrunk_credit": _round(shrunk),
        "shrunk_difficulty": None if shrunk is None else _round(1 - shrunk),
    }


def diagnose(
    responses: pd.DataFrame,
    topics: pd.DataFrame | None = None,
    *,
    min_students: int = MIN_STUDENTS_DEFAULT,
    evidence_class: str = "uploaded",
) -> dict:
    limitations = [
        "Results describe the uploaded assessments. They do not identify why a topic is difficult.",
        "The confidence interval does not adjust for school clustering.",
        "Topics below the minimum student count are not labeled weak or strong.",
        DIAGNOSTICS,
    ]
    if evidence_class == "synthetic":
        limitations.insert(0, "This dataset is synthetic. It demonstrates the software. It is not evidence about real students.")

    if responses is None or responses.empty:
        catalog = []
        if topics is not None and not topics.empty:
            for record in topics.to_dict(orient="records"):
                catalog.append(
                    {
                        "topic_id": record.get("topic_id") or record.get("external_id"),
                        "topic_name": record.get("topic_name") or record.get("name"),
                        "status": "not_assessed",
                        "n_students": 0,
                        "accuracy": None,
                    }
                )
        return {
            "methodology_version": METHODOLOGY_VERSION,
            "evidence_class": evidence_class,
            "status": "insufficient_data",
            "min_students": min_students,
            "overview": {"responses": 0, "students": 0, "topics_assessed": 0},
            "topics": catalog,
            "by_school": [],
            "by_grade": [],
            "over_time": [],
            "distribution": [],
            "coverage": {"assessed_topics": 0, "topics_meeting_minimum_n": 0},
            "limitations": limitations,
        }

    frame = responses.copy()
    frame["credit"] = pd.to_numeric(frame["credit"], errors="coerce")
    frame = frame.dropna(subset=["credit", "topic_id", "student_id"])
    if "school_id" not in frame.columns:
        frame["school_id"] = "unknown"
    if "grade_level" not in frame.columns:
        frame["grade_level"] = None
    if "assessment_date" not in frame.columns:
        frame["assessment_date"] = None
    if "topic_name" not in frame.columns:
        frame["topic_name"] = frame["topic_id"]

    student_topic = (
        frame.groupby(["topic_id", "student_id"], dropna=False)["credit"].mean().reset_index(name="student_credit")
    )
    topic_rows = []
    school_rows = []
    grade_rows = []
    time_rows = []
    distribution = []

    names = frame.groupby("topic_id")["topic_name"].agg(lambda s: next((v for v in s if v), ""))
    grades = frame.groupby("topic_id")["grade_level"].agg(lambda s: sorted({int(v) for v in s.dropna().unique()}))

    for topic_id, group in student_topic.groupby("topic_id"):
        items = frame.loc[frame["topic_id"] == topic_id, "credit"]
        metrics = _topic_frame(group["student_credit"], items, min_students)
        schools = frame.loc[frame["topic_id"] == topic_id, "school_id"].nunique()
        questions = frame.loc[frame["topic_id"] == topic_id, "question_id"].nunique() if "question_id" in frame.columns else None
        flags: list[str] = []
        school_detail = _school_breakdown(frame, student_topic, topic_id, min_students)
        if _is_inconsistent(school_detail, metrics["n_students"], min_students):
            flags.append("inconsistent_across_schools")
        explanation = _explain(str(names.get(topic_id, topic_id)), metrics, flags)
        topic_rows.append(
            {
                "topic_id": topic_id,
                "topic_name": names.get(topic_id, topic_id),
                "grade_levels": grades.get(topic_id, []),
                "n_schools": int(schools),
                "n_questions": None if questions is None else int(questions),
                "flags": flags,
                "explanation": explanation,
                **metrics,
            }
        )
        for row in school_detail:
            school_rows.append({"topic_id": topic_id, **row})
        for row in _grade_breakdown(frame, topic_id):
            grade_rows.append({"topic_id": topic_id, **row})
        for row in _time_breakdown(frame, topic_id):
            time_rows.append({"topic_id": topic_id, **row})
        distribution.append({"topic_id": topic_id, "bins": _histogram(group["student_credit"])})

    assessed_ids = {row["topic_id"] for row in topic_rows}
    if topics is not None and not topics.empty:
        id_col = "topic_id" if "topic_id" in topics.columns else "external_id"
        name_col = "topic_name" if "topic_name" in topics.columns else "name"
        for record in topics.to_dict(orient="records"):
            topic_id = record.get(id_col)
            if topic_id not in assessed_ids:
                topic_rows.append(
                    {
                        "topic_id": topic_id,
                        "topic_name": record.get(name_col, topic_id),
                        "status": "not_assessed",
                        "n_students": 0,
                        "n_items": 0,
                        "accuracy": None,
                        "flags": ["not_assessed"],
                        "difficulty_interpretable": False,
                        "explanation": "This topic is in the catalog but has no accepted assessment rows.",
                    }
                )

    topic_rows.sort(key=lambda row: (row.get("accuracy") is None, row.get("accuracy") if row.get("accuracy") is not None else 0))
    meeting = sum(1 for row in topic_rows if row.get("n_students", 0) >= min_students)
    weak = [row for row in topic_rows if row.get("status") == "weak"]
    strong = [row for row in topic_rows if row.get("status") == "strong"]
    insufficient = [row for row in topic_rows if row.get("status") in {"insufficient_data", "not_assessed"}]
    dates_present = frame["assessment_date"].notna().any() and (frame["assessment_date"] != "").any()
    if not dates_present:
        limitations.append("Assessment dates are missing, so performance over time is unavailable.")

    return {
        "methodology_version": METHODOLOGY_VERSION,
        "evidence_class": evidence_class,
        "status": "ok",
        "min_students": min_students,
        "thresholds": {
            "weak_if_ci_upper_below": WEAK_CI_UPPER,
            "strong_if_ci_lower_at_least": STRONG_CI_LOWER,
            "inconsistent_school_range": INCONSISTENT_RANGE,
        },
        "overview": {
            "responses": int(len(frame)),
            "students": int(frame["student_id"].nunique()),
            "schools": int(frame["school_id"].nunique()),
            "topics_assessed": int(frame["topic_id"].nunique()),
            "mean_student_topic_credit": _round(float(student_topic["student_credit"].mean())),
            "weak_topics": len(weak),
            "strong_topics": len(strong),
            "insufficient_or_unassessed": len(insufficient),
        },
        "topics": topic_rows,
        "by_school": school_rows,
        "by_grade": grade_rows,
        "over_time": time_rows,
        "distribution": distribution,
        "coverage": {
            "assessed_topics": int(frame["topic_id"].nunique()),
            "catalog_topics": None if topics is None else int(len(topics)),
            "topics_meeting_minimum_n": meeting,
            "questions": int(frame["question_id"].nunique()) if "question_id" in frame.columns else None,
        },
        "limitations": limitations,
    }


def _school_breakdown(frame: pd.DataFrame, student_topic: pd.DataFrame, topic_id: str, min_students: int) -> list[dict]:
    subset = student_topic[student_topic["topic_id"] == topic_id]
    school_of = frame.drop_duplicates("student_id").set_index("student_id")["school_id"]
    rows = []
    merged = subset.join(school_of, on="student_id")
    for school_id, group in merged.groupby("school_id"):
        values = group["student_credit"].tolist()
        low, high = student_t_interval(values)
        rows.append(
            {
                "school_id": school_id,
                "n_students": len(values),
                "accuracy": _round(float(mean(values))) if values else None,
                "ci_low": _round(low),
                "ci_high": _round(high),
                "meets_school_minimum": len(values) >= INCONSISTENT_SCHOOL_MIN_N,
                "label_allowed": len(values) >= min_students,
            }
        )
    return rows


def _is_inconsistent(school_detail: list[dict], n_students: int, min_students: int) -> bool:
    eligible = [row for row in school_detail if row["n_students"] >= INCONSISTENT_SCHOOL_MIN_N and row["accuracy"] is not None]
    if n_students < min_students or len(eligible) < 2:
        return False
    accuracies = [row["accuracy"] for row in eligible]
    return max(accuracies) - min(accuracies) >= INCONSISTENT_RANGE


def _grade_breakdown(frame: pd.DataFrame, topic_id: str) -> list[dict]:
    subset = frame[frame["topic_id"] == topic_id]
    rows = []
    for grade, group in subset.groupby("grade_level"):
        student_means = group.groupby("student_id")["credit"].mean()
        rows.append(
            {
                "grade_level": None if pd.isna(grade) else int(grade),
                "n_students": int(student_means.shape[0]),
                "accuracy": _round(float(student_means.mean())) if len(student_means) else None,
            }
        )
    return rows


def _time_breakdown(frame: pd.DataFrame, topic_id: str) -> list[dict]:
    subset = frame[frame["topic_id"] == topic_id]
    subset = subset[subset["assessment_date"].notna() & (subset["assessment_date"] != "")]
    rows = []
    for date, group in subset.groupby("assessment_date"):
        student_means = group.groupby("student_id")["credit"].mean()
        low, high = student_t_interval(student_means.tolist())
        rows.append(
            {
                "assessment_date": str(date),
                "n_students": int(len(student_means)),
                "accuracy": _round(float(student_means.mean())) if len(student_means) else None,
                "ci_low": _round(low),
                "ci_high": _round(high),
            }
        )
    rows.sort(key=lambda row: row["assessment_date"])
    return rows


def _histogram(student_credit: pd.Series) -> list[dict]:
    bins = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0001]
    labels = ["0.0-0.2", "0.2-0.4", "0.4-0.6", "0.6-0.8", "0.8-1.0"]
    counts = [0] * 5
    for value in student_credit.tolist():
        for index in range(5):
            if bins[index] <= float(value) < bins[index + 1] or (index == 4 and float(value) == 1):
                counts[index] += 1
                break
    total = sum(counts) or 1
    return [{"bin": label, "students": count, "share": round(count / total, 4)} for label, count in zip(labels, counts, strict=True)]


def _explain(name: str, metrics: dict, flags: list[str]) -> str:
    if metrics["accuracy"] is None:
        return f"{name}: no scored responses."
    text = (
        f"{name}: mean student credit {metrics['accuracy']} "
        f"from {metrics['n_students']} students and {metrics['n_items']} item responses. "
        f"95% CI [{metrics['ci_low']}, {metrics['ci_high']}]. "
        f"Classification: {metrics['status']}."
    )
    if "inconsistent_across_schools" in flags:
        text += " School means differ by at least 0.25 among schools with enough students. That is a disparity flag, not a school effect."
    if metrics["status"] == "insufficient_data":
        text += " The sample is too small for a weak or strong label."
    return text

"""Synthetic secondary-mathematics dataset.

The data-generating process is explicit. Numbers are not hand-tuned after the
fact to impress a dashboard. See docs/SYNTHETIC_DATA.md.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

TOPICS = [
    {"topic_id": "T01", "topic_name": "Integers and operations", "grade_level": 7, "prerequisites": []},
    {"topic_id": "T02", "topic_name": "Fractions and decimals", "grade_level": 7, "prerequisites": ["T01"]},
    {"topic_id": "T03", "topic_name": "Ratios and proportions", "grade_level": 7, "prerequisites": ["T02"]},
    {"topic_id": "T04", "topic_name": "Algebraic expressions", "grade_level": 7, "prerequisites": ["T01"]},
    {"topic_id": "T05", "topic_name": "Linear equations", "grade_level": 8, "prerequisites": ["T04", "T02"]},
    {"topic_id": "T06", "topic_name": "Factoring", "grade_level": 8, "prerequisites": ["T04"]},
    {"topic_id": "T07", "topic_name": "Systems of linear equations", "grade_level": 8, "prerequisites": ["T05"]},
    {"topic_id": "T08", "topic_name": "Functions introduction", "grade_level": 8, "prerequisites": ["T05"]},
    {"topic_id": "T09", "topic_name": "Geometry angles and triangles", "grade_level": 8, "prerequisites": []},
    {"topic_id": "T10", "topic_name": "Pythagorean theorem", "grade_level": 8, "prerequisites": ["T09", "T04"]},
    {"topic_id": "T11", "topic_name": "Descriptive statistics", "grade_level": 8, "prerequisites": ["T02"]},
    {"topic_id": "T12", "topic_name": "Quadratic equations", "grade_level": 9, "prerequisites": ["T05", "T06"]},
    {"topic_id": "T13", "topic_name": "Quadratic functions", "grade_level": 9, "prerequisites": ["T12", "T08"]},
    {"topic_id": "T14", "topic_name": "Inequalities", "grade_level": 9, "prerequisites": ["T05"]},
    {"topic_id": "T15", "topic_name": "Probability", "grade_level": 9, "prerequisites": ["T03", "T11"]},
    {"topic_id": "T16", "topic_name": "Similarity and congruence", "grade_level": 9, "prerequisites": ["T09"]},
    {"topic_id": "T17", "topic_name": "Introduction to trigonometry", "grade_level": 9, "prerequisites": ["T10", "T09"]},
]

ASSESSED = {
    7: ["T01", "T02", "T03", "T04"],
    8: ["T04", "T05", "T06", "T07", "T08", "T09", "T10", "T11"],
    9: ["T05", "T06", "T12", "T13", "T14", "T15", "T16", "T17"],
}

SCHOOLS = [
    {"school_id": "SCH_NORTH", "school_name": "North Secondary", "ability_mean": 0.25},
    {"school_id": "SCH_EAST", "school_name": "East Secondary", "ability_mean": 0.05},
    {"school_id": "SCH_SOUTH", "school_name": "South Secondary", "ability_mean": -0.15},
    {"school_id": "SCH_WEST", "school_name": "West Secondary", "ability_mean": 0.00},
]

DIFFICULTY = {
    # Chosen so the demonstration contains both secure and weak topics.
    # These are generator settings, not estimated item parameters.
    "T01": -1.8, "T02": -1.0, "T03": -0.15, "T04": -1.0, "T05": 0.05, "T06": 0.2,
    "T07": 0.15, "T08": 0.0, "T09": -0.35, "T10": 0.1, "T11": -1.5, "T12": 0.3,
    "T13": 0.35, "T14": 0.05, "T15": 0.1, "T16": 0.05, "T17": 0.35,
}

PERIODS = ["2024-10-15", "2025-03-20"]
ORDER = ["T01", "T02", "T03", "T04", "T05", "T06", "T09", "T07", "T08", "T10", "T11", "T12", "T14", "T16", "T13", "T15", "T17"]


def school_topic_shift(school_id: str, topic_id: str) -> float:
    if school_id == "SCH_NORTH" and topic_id == "T06":
        return -1.15
    if school_id == "SCH_SOUTH" and topic_id in {"T09", "T16", "T17"}:
        return -0.85
    return 0.0


@dataclass
class DemoBundle:
    responses: pd.DataFrame
    topics: pd.DataFrame
    prerequisites: pd.DataFrame
    allocations: pd.DataFrame
    textbooks: dict[str, str]
    meta: dict


def generate_demo(*, students_per_school_grade: int = 24, questions_per_topic: int = 4, seed: int = 7) -> DemoBundle:
    rng = np.random.default_rng(seed)
    topic_by_id = {topic["topic_id"]: topic for topic in TOPICS}
    rows = []
    student_index = 0
    for school in SCHOOLS:
        for grade in (7, 8, 9):
            for _ in range(students_per_school_grade):
                student_index += 1
                student_id = f"STU_{student_index:04d}"
                ability = float(rng.normal(school["ability_mean"], 0.45))
                material = "TB_ALPHA" if rng.random() < 1 / (1 + np.exp(-0.8 * ability)) else "TB_BETA"
                latent = _latent(ability, school["school_id"], material)
                for period_index, date in enumerate(PERIODS):
                    practice = 0.15 if period_index == 1 else 0.0
                    for topic_id in ASSESSED[grade]:
                        if topic_id == "T15" and not (school["school_id"] == "SCH_WEST" and student_index % 17 == 0):
                            continue
                        question_count = 1 if topic_id == "T15" else questions_per_topic
                        shift = 0.05 if school["school_id"] == "SCH_NORTH" and topic_id == "T06" and period_index == 1 else practice
                        for question_index in range(question_count):
                            question_id = f"{topic_id}_Q{question_index + 1}"
                            logit = latent[topic_id] + shift + float(rng.normal(0, 0.25))
                            credit = 1.0 if rng.random() < 1 / (1 + np.exp(-logit)) else 0.0
                            rows.append(
                                {
                                    "student_id": student_id,
                                    "school_id": school["school_id"],
                                    "school_name": school["school_name"],
                                    "grade_level": grade,
                                    "subject_id": "MATH",
                                    "subject_name": "Mathematics",
                                    "topic_id": topic_id,
                                    "topic_name": topic_by_id[topic_id]["topic_name"],
                                    "assessment_id": f"MATH_{date}_{grade}",
                                    "assessment_name": f"Mathematics check {date}",
                                    "assessment_date": date,
                                    "question_id": f"{question_id}_{date}",
                                    "is_correct": "true" if credit == 1 else "false",
                                    "score": credit,
                                    "max_score": 1,
                                    "material_id": material,
                                    "answer_text": "",
                                }
                            )
    responses = pd.DataFrame(rows)
    topics = pd.DataFrame(
        [
            {
                "topic_id": topic["topic_id"],
                "topic_name": topic["topic_name"],
                "subject_id": "MATH",
                "subject_name": "Mathematics",
                "grade_level": topic["grade_level"],
                "description": "Synthetic curriculum topic for the demonstration dataset.",
            }
            for topic in TOPICS
        ]
    )
    prerequisites = pd.DataFrame(
        [
            {
                "prerequisite_topic_id": prereq,
                "dependent_topic_id": topic["topic_id"],
                "relation_status": "verified",
                "source": "synthetic_curriculum_map",
                "notes": "Asserted by the demo curriculum map. Not an experimental finding.",
                "confidence": "",
            }
            for topic in TOPICS
            for prereq in topic["prerequisites"]
        ]
    )
    allocations = pd.DataFrame(
        [
            {"topic_id": "T04", "subject_id": "MATH", "hours": 8, "min_hours": 4, "max_hours": 16, "importance_weight": 1.0},
            {"topic_id": "T05", "subject_id": "MATH", "hours": 12, "min_hours": 6, "max_hours": 18, "importance_weight": 1.1},
            {"topic_id": "T06", "subject_id": "MATH", "hours": 8, "min_hours": 4, "max_hours": 18, "importance_weight": 1.4},
            {"topic_id": "T07", "subject_id": "MATH", "hours": 8, "min_hours": 4, "max_hours": 14, "importance_weight": 1.0},
            {"topic_id": "T08", "subject_id": "MATH", "hours": 8, "min_hours": 4, "max_hours": 14, "importance_weight": 1.0},
            {"topic_id": "T09", "subject_id": "MATH", "hours": 10, "min_hours": 4, "max_hours": 16, "importance_weight": 1.0},
            {"topic_id": "T10", "subject_id": "MATH", "hours": 6, "min_hours": 3, "max_hours": 12, "importance_weight": 1.0},
            {"topic_id": "T11", "subject_id": "MATH", "hours": 6, "min_hours": 3, "max_hours": 12, "importance_weight": 0.8},
            {"topic_id": "T12", "subject_id": "MATH", "hours": 14, "min_hours": 6, "max_hours": 20, "importance_weight": 1.3},
            {"topic_id": "T13", "subject_id": "MATH", "hours": 8, "min_hours": 4, "max_hours": 14, "importance_weight": 1.1},
            {"topic_id": "T14", "subject_id": "MATH", "hours": 6, "min_hours": 3, "max_hours": 12, "importance_weight": 1.0},
            {"topic_id": "T15", "subject_id": "MATH", "hours": 6, "min_hours": 2, "max_hours": 10, "importance_weight": 0.9},
        ]
    )
    return DemoBundle(
        responses=responses,
        topics=topics,
        prerequisites=prerequisites,
        allocations=allocations,
        textbooks={"TB_ALPHA": TEXTBOOK_ALPHA, "TB_BETA": TEXTBOOK_BETA},
        meta={
            "seed": seed,
            "students_per_school_grade": students_per_school_grade,
            "is_synthetic": True,
            "evidence_class": "synthetic",
            "dgp": "latent ability, school-topic shifts, prerequisite penalty, small material log-odds, two periods",
        },
    )


def _latent(ability: float, school_id: str, material: str) -> dict[str, float]:
    latent: dict[str, float] = {}
    material_bonus = 0.12 if material == "TB_ALPHA" else 0.0
    for topic_id in ORDER:
        topic = next(item for item in TOPICS if item["topic_id"] == topic_id)
        penalty = 0.0
        for prereq in topic["prerequisites"]:
            penalty += max(0.0, -latent[prereq]) * 0.55
        latent[topic_id] = ability + school_topic_shift(school_id, topic_id) - DIFFICULTY[topic_id] - penalty + material_bonus
    return latent


def frames_to_csv_bytes(bundle: DemoBundle) -> dict[str, bytes]:
    return {
        "responses.csv": bundle.responses.to_csv(index=False).encode("utf-8"),
        "topics.csv": bundle.topics.to_csv(index=False).encode("utf-8"),
        "prerequisites.csv": bundle.prerequisites.to_csv(index=False).encode("utf-8"),
        "allocations.csv": bundle.allocations.to_csv(index=False).encode("utf-8"),
    }


TEXTBOOK_ALPHA = """
Chapter 1 Algebraic expressions
Definition: An algebraic expression is a combination of numbers, variables, and operations.
Explanation: Students rewrite expressions by combining like terms before they solve equations.
Example: 3x + 2x = 5x.
Exercise 1. Simplify 4a + 7a.
Exercise 2. Identify the variable in 6y + 1.

Chapter 2 Factoring
Definition: Factoring writes an expression as a product.
Explanation: Factoring algebraic expressions prepares students for quadratic equations. Common factors are removed first, then simple trinomials.
Example: x^2 + 5x + 6 = (x + 2)(x + 3).
Exercise 1. Factor x^2 + 7x + 12.
Exercise 2. Factor x^2 + 5x + 6.
Exercise 3. Compare x^2 + 5x + 6 with x^2 + 7x + 12 and explain the pattern.
Exercise 4. Solve x^2 + 5x + 6 = 0 by factoring.
Question: Justify why (x + 2) and (x + 3) are factors of x^2 + 5x + 6.

Chapter 3 Quadratic equations
Definition: A quadratic equation has the form ax^2 + bx + c = 0.
Explanation: This chapter uses factoring before the quadratic formula.
Example: x^2 - 9 = (x - 3)(x + 3).
Exercise 1. Solve x^2 - 9 = 0.
Exercise 2. Calculate the roots of x^2 + 5x + 6 = 0.
"""

TEXTBOOK_BETA = """
Chapter 1 Expressions
Definition: An expression contains symbols.
Example: x + x = 2x.
Exercise 1. Simplify x + x.

Chapter 2 Quadratic equations
Definition: Use the quadratic formula.
Explanation: The formula can be applied immediately.
Example: For x^2 + 5x + 6 = 0, substitute a, b, and c.
Exercise 1. Solve x^2 + 5x + 6 = 0 with the formula.
"""

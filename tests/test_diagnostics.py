import pandas as pd

from app.analytics.diagnostics.engine import diagnose, student_t_interval, wilson_interval


def _frame(n, credit, topic="T12"):
    return pd.DataFrame(
        {
            "student_id": [f"S{i}" for i in range(n)],
            "school_id": ["SCH"] * n,
            "topic_id": [topic] * n,
            "topic_name": ["Quadratic equations"] * n,
            "question_id": ["Q1"] * n,
            "credit": [credit] * n,
            "grade_level": [9] * n,
            "assessment_date": ["2025-03-20"] * n,
        }
    )


def test_small_sample_is_not_labeled_like_a_large_sample():
    small = diagnose(_frame(3, 0.3), min_students=30)
    large = diagnose(_frame(200, 0.3), min_students=30)
    assert small["topics"][0]["status"] == "insufficient_data"
    assert large["topics"][0]["status"] == "weak"
    assert large["topics"][0]["accuracy"] == 0.3


def test_wilson_known_value_and_empty_interval():
    low, high = wilson_interval(0, 0)
    assert low is None and high is None
    low, high = wilson_interval(50, 100)
    assert 0.40 < low < 0.45
    assert 0.55 < high < 0.60


def test_t_interval_widens_for_uncertain_students():
    tight = student_t_interval([0.8, 0.82, 0.79, 0.81] * 10)
    wide = student_t_interval([0.1, 0.9] * 5)
    assert tight[1] - tight[0] < wide[1] - wide[0]


def test_empty_dataset():
    result = diagnose(pd.DataFrame(), pd.DataFrame([{"topic_id": "T15", "topic_name": "Probability"}]))
    assert result["status"] == "insufficient_data"
    assert result["topics"][0]["status"] == "not_assessed"


def test_inconsistent_schools_flag():
    rows = []
    for index in range(40):
        rows.append({"student_id": f"A{index}", "school_id": "A", "topic_id": "T09", "topic_name": "Angles", "question_id": "Q", "credit": 0.9, "grade_level": 8, "assessment_date": "2024-10-15"})
    for index in range(40):
        rows.append({"student_id": f"B{index}", "school_id": "B", "topic_id": "T09", "topic_name": "Angles", "question_id": "Q", "credit": 0.4, "grade_level": 8, "assessment_date": "2024-10-15"})
    result = diagnose(pd.DataFrame(rows), min_students=30)
    assert "inconsistent_across_schools" in result["topics"][0]["flags"]

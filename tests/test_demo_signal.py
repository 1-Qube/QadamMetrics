from app.analytics.diagnostics.engine import diagnose
from app.demo.generator import generate_demo


def test_synthetic_generator_is_labeled_and_reproducible():
    first = generate_demo(students_per_school_grade=6, seed=7)
    second = generate_demo(students_per_school_grade=6, seed=7)
    assert first.meta["is_synthetic"] is True
    assert first.responses.equals(second.responses)
    assert set(first.textbooks) == {"TB_ALPHA", "TB_BETA"}


def test_factoring_is_weaker_than_expressions_in_the_dgp():
    bundle = generate_demo(students_per_school_grade=30, questions_per_topic=3, seed=7)
    frame = bundle.responses.rename(columns={"is_correct": "correct_text"})
    frame["credit"] = frame["score"].astype(float)
    result = diagnose(frame, bundle.topics.rename(columns={})[["topic_id", "topic_name", "grade_level"]], min_students=30, evidence_class="synthetic")
    by_id = {row["topic_id"]: row for row in result["topics"]}
    assert by_id["T15"]["status"] in {"insufficient_data", "not_assessed"}
    assert by_id["T04"]["accuracy"] > by_id["T06"]["accuracy"]
    assert result["evidence_class"] == "synthetic"

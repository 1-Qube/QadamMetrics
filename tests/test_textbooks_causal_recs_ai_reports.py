import pandas as pd

from app.ai.copilot import Copilot, unexpected_numbers
from app.analytics.causal_analysis.engine import analyze_textbook_contrast
from app.analytics.recommendations.engine import recommend
from app.analytics.textbook_intelligence.engine import compare_textbooks, extract_structure, extract_text_from_pdf
from app.demo.generator import TEXTBOOK_ALPHA, TEXTBOOK_BETA
from app.reporting.engine import build_report_payload, write_csv_zip, write_pdf


def test_textbook_extraction_and_structural_difference():
    topics = [{"topic_id": "T06", "topic_name": "Factoring"}, {"topic_id": "T12", "topic_name": "Quadratic equations"}]
    alpha = extract_structure(TEXTBOOK_ALPHA, topics)
    beta = extract_structure(TEXTBOOK_BETA, topics)
    assert alpha["chapter_count"] >= 2
    assert alpha["counts"]["exercise"] > beta["counts"]["exercise"]
    assert alpha["expressions"]
    comparison = compare_textbooks(
        [
            {"material_id": "TB_ALPHA", "title": "Alpha", "raw_text": TEXTBOOK_ALPHA, "is_synthetic": True},
            {"material_id": "TB_BETA", "title": "Beta", "raw_text": TEXTBOOK_BETA, "is_synthetic": True},
        ],
        topics,
        [{"material_id": "TB_ALPHA", "n_students": 40, "mean_credit": 0.7, "confounded": True}],
    )
    assert comparison["claim_level"] == "structural_description"
    assert "not a textbook effect" in comparison["outcome_association"][0]["note"].lower()


def test_pdf_roundtrip(tmp_path):
    from reportlab.pdfgen import canvas

    path = tmp_path / "book.pdf"
    pdf = canvas.Canvas(str(path))
    pdf.drawString(72, 720, "Chapter 1 Factoring")
    pdf.drawString(72, 700, "Definition: Factoring writes a product.")
    pdf.drawString(72, 680, "Exercise 1. Factor x^2 + 5x + 6.")
    pdf.save()
    text = extract_text_from_pdf(path.read_bytes())
    structure = extract_structure(text, [{"topic_id": "T06", "topic_name": "Factoring"}])
    assert "Factoring" in text
    assert structure["counts"]["definition"] >= 1 or structure["counts"]["exercise"] >= 1


def test_causal_refuses_nested_treatment_and_small_arms():
    nested = pd.DataFrame(
        {
            "student_id": [f"S{i}" for i in range(40)],
            "treatment": ["A" if i < 20 else "B" for i in range(40)],
            "outcome": [0.8 if i < 20 else 0.4 for i in range(40)],
            "school_id": ["SCH1" if i < 20 else "SCH2" for i in range(40)],
            "prior_score": [0.6] * 40,
        }
    )
    result = analyze_textbook_contrast(nested, confounder_cols=["prior_score", "school_id"], n_bootstrap=0)
    assert result["claim_level"] == "association_only"
    assert result["causal_conclusion"] == "not_claimed"
    assert result["estimated_effect"] is None

    small = nested.head(10).copy()
    small["school_id"] = "SCH"
    small["treatment"] = ["A", "B"] * 5
    small_result = analyze_textbook_contrast(small, confounder_cols=["prior_score"], n_bootstrap=0)
    assert small_result["claim_level"] == "association_only"


def test_causal_overlap_returns_estimate_without_causal_certainty():
    rows = []
    for index in range(80):
        prior = (index % 10) / 10
        treatment = "A" if index % 2 == 0 else "B"
        outcome = 0.4 + 0.3 * prior + (0.05 if treatment == "A" else 0)
        rows.append({"student_id": f"S{index}", "treatment": treatment, "outcome": outcome, "prior_score": prior, "grade_level": 9, "school_id": "SCH" + str(index % 3)})
    result = analyze_textbook_contrast(pd.DataFrame(rows), confounder_cols=["prior_score", "grade_level", "school_id"], n_bootstrap=25)
    assert result["causal_conclusion"] == "not_claimed"
    assert result["claim_level"] == "estimated_effect_under_untestable_assumptions"
    assert "ipw_ate" in result["estimated_effect"]
    assert result["association"]["claim_level"] == "association"


def test_recommendations_do_not_claim_a_proven_fix():
    diagnostics = {
        "topics": [
            {"topic_id": "T06", "topic_name": "Factoring", "status": "weak", "accuracy": 0.4, "ci_low": 0.35, "ci_high": 0.45, "n_students": 120, "flags": []},
            {"topic_id": "T15", "topic_name": "Probability", "status": "insufficient_data", "n_students": 4, "flags": []},
        ]
    }
    graph = {"risks": [{"topic_id": "T06", "weak_verified_prerequisites": [], "reasoning": "weak topic"}]}
    result = recommend(diagnostics, graph, evidence_class="synthetic")
    assert all(item["not_a_proven_intervention"] for item in result["recommendations"])
    assert any(item["rule_id"] == "coverage" for item in result["recommendations"])
    assert result["evidence_class"] == "synthetic"


def test_ai_missing_key_and_invented_numbers(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "")
    from app.core.config import get_settings

    get_settings.cache_clear()
    result = Copilot().explain("diagnostics", {"overview": {"students": 10}, "topics": []})
    assert result["used_fallback"] is True
    assert result["provider"] == "deterministic_fallback"
    assert unexpected_numbers("Accuracy was 99.9 percent.", {0.4, 10}) 


def test_report_has_no_student_rows(tmp_path):
    payload = build_report_payload(
        dataset={"id": "d", "name": "Demo", "evidence_class": "synthetic", "is_synthetic": True, "summary": {}},
        diagnostics={"overview": {"students": 3}, "coverage": {}, "topics": [{"topic_id": "T01", "topic_name": "Integers", "status": "insufficient_data", "accuracy": 0.5, "ci_low": 0.2, "ci_high": 0.8, "n_students": 3, "n_items": 3, "difficulty_index": 0.5}], "by_grade": [], "by_school": [], "limitations": ["test"]},
        graph={"risks": [], "edge_count": 0, "cycles": [], "limitations": []},
        recommendations={"recommendations": [], "limitations": []},
    )
    assert "student_id" not in str(payload)
    pdf = tmp_path / "r.pdf"
    archive = tmp_path / "r.zip"
    write_pdf(pdf, payload)
    write_csv_zip(archive, payload)
    assert pdf.stat().st_size > 500
    assert archive.stat().st_size > 50

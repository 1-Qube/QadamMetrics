"""Aggregate reports. Individual student rows are not included."""

from __future__ import annotations

import csv
import io
import zipfile
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.analytics.methodology import METHODOLOGY_VERSION, methodology_catalog

_FONT = "Helvetica"
_FONT_READY = False


def _ensure_font() -> str:
    global _FONT, _FONT_READY
    if _FONT_READY:
        return _FONT
    arial = Path("C:/Windows/Fonts/arial.ttf")
    if arial.exists():
        pdfmetrics.registerFont(TTFont("Arial", str(arial)))
        _FONT = "Arial"
    _FONT_READY = True
    return _FONT


def build_report_payload(
    *,
    dataset: dict,
    diagnostics: dict,
    graph: dict,
    textbook: dict | None = None,
    optimization: dict | None = None,
    causal: dict | None = None,
    recommendations: dict | None = None,
) -> dict:
    return {
        "title": f"QadamMetrics analysis: {dataset.get('name', dataset.get('id'))}",
        "methodology_version": METHODOLOGY_VERSION,
        "evidence_class": dataset.get("evidence_class"),
        "is_synthetic": dataset.get("is_synthetic", False),
        "sections": {
            "dataset_overview": {"dataset": _public_dataset(dataset), "overview": diagnostics.get("overview"), "coverage": diagnostics.get("coverage")},
            "assessment_performance": {"by_grade": diagnostics.get("by_grade"), "by_school_count": len(diagnostics.get("by_school") or [])},
            "topic_analysis": diagnostics.get("topics"),
            "knowledge_dependencies": {"risks": graph.get("risks"), "edge_count": graph.get("edge_count"), "cycles": graph.get("cycles")},
            "textbook_comparison": textbook or {"status": "not_requested"},
            "curriculum_allocation": optimization or {"status": "not_requested"},
            "causal_analysis": causal or {"status": "not_requested", "causal_conclusion": "not_claimed"},
            "recommendations": (recommendations or {}).get("recommendations", []),
            "limitations": _limitations(dataset, diagnostics, graph, textbook, optimization, causal, recommendations),
            "methodology": methodology_catalog(),
        },
    }


def _public_dataset(dataset: dict) -> dict:
    return {
        "id": dataset.get("id"),
        "name": dataset.get("name"),
        "evidence_class": dataset.get("evidence_class"),
        "is_synthetic": dataset.get("is_synthetic"),
        "summary": dataset.get("summary"),
    }


def _limitations(*parts: dict | None) -> list[str]:
    notes = [
        "This report contains aggregates only. It is not a student ranking.",
        "Descriptive findings are not causal claims.",
        "Optimization scenarios are hypothetical unless an empirical learning-response model is supplied, which this version does not fit.",
    ]
    for part in parts:
        if not part:
            continue
        for item in part.get("limitations") or []:
            if item not in notes:
                notes.append(str(item)[:500])
    return notes


def write_json(path: Path, payload: dict) -> None:
    path.write_text(__import__("json").dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_csv_zip(path: Path, payload: dict) -> None:
    sections = payload["sections"]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("topics.csv", _table_csv(sections.get("topic_analysis") or [], [
            "topic_id", "topic_name", "status", "accuracy", "ci_low", "ci_high", "n_students", "n_items", "difficulty_index",
        ]))
        archive.writestr("recommendations.csv", _table_csv(sections.get("recommendations") or [], [
            "rule_id", "issue", "recommended_action", "evidence_confidence", "intervention_confidence", "expected_impact_direction",
        ]))
        risks = (sections.get("knowledge_dependencies") or {}).get("risks") or []
        archive.writestr("dependency_risks.csv", _table_csv(risks, [
            "topic_id", "upstream_gap_hypothesis", "descendant_count", "downstream_risk_index", "claim_level", "reasoning",
        ]))
        hours = []
        allocation = sections.get("curriculum_allocation") or {}
        for scenario in allocation.get("scenarios") or []:
            for row in scenario.get("hours") or []:
                hours.append({"scenario": scenario.get("name"), **row})
        archive.writestr("hour_scenarios.csv", _table_csv(hours, ["scenario", "topic_id", "hours", "delta_from_current"]))
        archive.writestr("limitations.csv", _table_csv([{"limitation": item} for item in sections.get("limitations") or []], ["limitation"]))
    path.write_bytes(buffer.getvalue())


def _csv_safe(value: object) -> str:
    text = "" if value is None else str(value)
    if text.startswith(("=", "+", "-", "@")):
        return "'" + text
    return text


def _table_csv(rows: list[dict], columns: list[str]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({column: _csv_safe(row.get(column)) for column in columns})
    return buffer.getvalue()


def write_pdf(path: Path, payload: dict) -> None:
    font = _ensure_font()
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="BodyUnicode", parent=styles["Normal"], fontName=font, fontSize=9, leading=12))
    styles.add(ParagraphStyle(name="HeadingUnicode", parent=styles["Heading2"], fontName=font, fontSize=13, leading=16))
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=1.6 * cm, rightMargin=1.6 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm)
    story = [
        Paragraph(_xml(payload["title"]), styles["HeadingUnicode"]),
        Spacer(1, 8),
        Paragraph(_xml(f"Evidence class: {payload.get('evidence_class')}. Methodology {payload.get('methodology_version')}."), styles["BodyUnicode"]),
        Spacer(1, 8),
    ]
    if payload.get("is_synthetic"):
        story.append(Paragraph("SYNTHETIC DATA. This report is a software demonstration, not evidence about real students.", styles["BodyUnicode"]))
        story.append(Spacer(1, 8))
    sections = payload["sections"]
    overview = sections["dataset_overview"].get("overview") or {}
    story.append(Paragraph("1. Dataset overview", styles["HeadingUnicode"]))
    story.append(Paragraph(_xml(", ".join(f"{key}: {value}" for key, value in overview.items())), styles["BodyUnicode"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("2-3. Topic analysis", styles["HeadingUnicode"]))
    table_data = [["Topic", "Status", "Accuracy", "CI", "Students"]]
    for row in (sections.get("topic_analysis") or [])[:20]:
        table_data.append([
            str(row.get("topic_name") or row.get("topic_id"))[:40],
            str(row.get("status")),
            "" if row.get("accuracy") is None else str(row.get("accuracy")),
            f"{row.get('ci_low')}–{row.get('ci_high')}" if row.get("ci_low") is not None else "",
            str(row.get("n_students")),
        ])
    table = Table(table_data, repeatRows=1)
    table.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, -1), font),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f4e79")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(table)
    story.append(Spacer(1, 10))
    story.append(Paragraph("4. Knowledge dependency findings", styles["HeadingUnicode"]))
    risks = (sections.get("knowledge_dependencies") or {}).get("risks") or []
    if not risks:
        story.append(Paragraph("No dependency risks were identified from the supplied graph and diagnostics.", styles["BodyUnicode"]))
    for risk in risks[:8]:
        story.append(Paragraph(_xml(risk.get("reasoning", "")), styles["BodyUnicode"]))
        story.append(Spacer(1, 4))
    story.append(Paragraph("5-7. Materials, hours, and contrasts", styles["HeadingUnicode"]))
    story.append(Paragraph(_xml(_short_json(sections.get("textbook_comparison"))), styles["BodyUnicode"]))
    story.append(Spacer(1, 4))
    story.append(Paragraph(_xml(_optimization_blurb(sections.get("curriculum_allocation") or {})), styles["BodyUnicode"]))
    story.append(Spacer(1, 4))
    causal = sections.get("causal_analysis") or {}
    story.append(Paragraph(_xml(f"Causal conclusion: {causal.get('causal_conclusion', 'not_claimed')}. {causal.get('message', '')}"), styles["BodyUnicode"]))
    story.append(Spacer(1, 8))
    story.append(Paragraph("8. Recommendations", styles["HeadingUnicode"]))
    for rec in sections.get("recommendations") or []:
        story.append(Paragraph(_xml(f"{rec.get('rule_id')}: {rec.get('recommended_action')}"), styles["BodyUnicode"]))
        story.append(Spacer(1, 3))
    story.append(Paragraph("9. Limitations", styles["HeadingUnicode"]))
    for item in (sections.get("limitations") or [])[:8]:
        story.append(Paragraph(_xml("• " + item), styles["BodyUnicode"]))
        story.append(Spacer(1, 3))
    story.append(Paragraph("10. Methodology", styles["HeadingUnicode"]))
    story.append(Paragraph("Full methodology is included in the JSON report and at GET /api/methodology. Custom indexes are descriptive. Optimization is hypothetical. Causal conclusions are not claimed.", styles["BodyUnicode"]))
    doc.build(story)


def _xml(text: str) -> str:
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


def _short_json(value: dict | None) -> str:
    if not value:
        return "Not requested."
    return f"Textbook comparison status: {value.get('status', 'ok')}. {value.get('structural_statement', '')} {value.get('outcome_statement', '')}"


def _optimization_blurb(value: dict) -> str:
    if value.get("status") != "ok":
        return f"Curriculum allocation status: {value.get('status', 'not_requested')}. {value.get('message', '')}"
    names = [scenario.get("name") for scenario in value.get("scenarios", [])]
    return "Hour scenarios computed: " + ", ".join(names) + ". " + value.get("sensitivity_note", "") + " " + value.get("decision", "")

"""HTTP routes. Business logic stays in services and analytical engines."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.methodology import methodology_catalog
from app.core.access import assert_can_read, current_owner, new_owner_token
from app.core.config import get_settings
from app.core.errors import AppError, NotFoundError
from app.data_ingestion.csv_loader import (
    parse_allocations_csv,
    parse_prerequisites_csv,
    parse_responses_csv,
    parse_topics_csv,
)
from app.data_ingestion.service import delete_dataset, get_dataset, ingest_parsed, summarize_dataset
from app.database.session import get_db
from app.demo.generator import frames_to_csv_bytes, generate_demo
from app.models.entities import Artifact, ImportIssue, ImportJob, Report
from app.reporting.engine import build_report_payload, write_csv_zip, write_json, write_pdf
from app.services.analytics_service import (
    load_allocations,
    load_edges,
    load_topics,
    require_dataset,
    run_causal,
    run_diagnostics,
    run_graph,
    run_inference,
    run_optimization,
    run_recommendations,
    run_textbook_comparison,
    save_material_text,
)
from app.ai.copilot import Copilot
from app.textbook_ingest import ingest_upload

router = APIRouter()
copilot = Copilot()


class EdgeIn(BaseModel):
    prerequisite_topic_id: str
    dependent_topic_id: str
    relation_status: str = "verified"
    notes: str = ""
    confidence: float | None = None


class OptimizeIn(BaseModel):
    dataset_id: str
    total_hours: float | None = None
    beta: float = 0.15
    transfer_tau: float = 0.25
    target_accuracy: float = 0.75
    max_change_hours: float | None = None
    proposed_hours: dict[str, float] | None = None
    topics: list[dict] | None = None


class CausalIn(BaseModel):
    dataset_id: str
    material_a: str | None = None
    material_b: str | None = None
    n_bootstrap: int = Field(default=200, ge=0, le=1000)


class ExplainIn(BaseModel):
    dataset_id: str | None = None
    task: str = "diagnostics"
    question: str | None = None
    facts: dict | None = None


class ReportIn(BaseModel):
    dataset_id: str
    title: str | None = None


def _read_upload(upload: UploadFile, suffixes: tuple[str, ...] = (".csv", ".txt", ".pdf")) -> bytes:
    settings = get_settings()
    name = (upload.filename or "").lower()
    if suffixes and not name.endswith(suffixes):
        raise AppError("invalid_file_type", "Upload must be one of: " + ", ".join(suffixes), 415)
    payload = upload.file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(payload) > settings.max_upload_mb * 1024 * 1024:
        raise AppError("payload_too_large", f"Upload exceeds {settings.max_upload_mb} MB.", 413)
    return payload


def _upload_owner() -> tuple[str | None, str]:
    token = current_owner()
    if get_settings().environment == "production":
        token = token or new_owner_token()
        return token, "private"
    return token, "private" if token else "public"


@router.get("/methodology")
def methodology() -> dict:
    return methodology_catalog()


@router.get("/datasets")
def list_datasets(session: Session = Depends(get_db)) -> dict:
    from app.models.entities import Dataset

    from app.core.access import can_read

    rows = [row for row in session.scalars(select(Dataset).order_by(Dataset.created_at.desc())).all() if can_read(row)]
    return {
        "data": [
            {
                "id": row.id,
                "name": row.name,
                "evidence_class": row.evidence_class,
                "is_synthetic": row.is_synthetic,
                "status": row.status,
                "visibility": row.visibility,
                "created_at": row.created_at.isoformat(),
                "summary": row.summary,
            }
            for row in rows
        ]
    }


@router.post("/datasets/import")
def import_dataset(
    name: str = Form(...),
    description: str = Form(""),
    is_synthetic: bool = Form(False),
    responses: UploadFile = File(...),
    topics: UploadFile | None = File(default=None),
    prerequisites: UploadFile | None = File(default=None),
    allocations: UploadFile | None = File(default=None),
    session: Session = Depends(get_db),
) -> dict:
    owner, visibility = _upload_owner()
    parsed_responses = parse_responses_csv(_read_upload(responses, (".csv",)), responses.filename or "responses.csv")
    parsed_topics = parse_topics_csv(_read_upload(topics)) if topics is not None else None
    parsed_prereq = parse_prerequisites_csv(_read_upload(prerequisites)) if prerequisites is not None else None
    parsed_alloc = parse_allocations_csv(_read_upload(allocations)) if allocations is not None else None
    result = ingest_parsed(
        session,
        name=name,
        description=description,
        responses=parsed_responses,
        topics=parsed_topics,
        prerequisites=parsed_prereq,
        allocations=parsed_alloc,
        is_synthetic=is_synthetic,
        visibility=visibility,
        owner_token=owner,
    )
    result["visibility"] = visibility
    return {"data": result}


@router.post("/datasets/demo")
def load_demo(
    students_per_school_grade: int = Query(default=24, ge=5, le=80),
    session: Session = Depends(get_db),
) -> dict:
    bundle = generate_demo(students_per_school_grade=students_per_school_grade)
    files = frames_to_csv_bytes(bundle)
    result = ingest_parsed(
        session,
        name="Synthetic mathematics demonstration",
        description="Generated by app.demo.generator. Not real student evidence.",
        responses=parse_responses_csv(files["responses.csv"], "responses.csv"),
        topics=parse_topics_csv(files["topics.csv"]),
        prerequisites=parse_prerequisites_csv(files["prerequisites.csv"]),
        allocations=parse_allocations_csv(files["allocations.csv"]),
        is_synthetic=True,
        source_type="synthetic_demo",
        visibility="public",
        owner_token=None,
    )
    for external_id, text in bundle.textbooks.items():
        save_material_text(
            session,
            result["dataset_id"],
            external_id,
            "Synthetic textbook " + external_id,
            text,
            external_id + ".txt",
            is_synthetic=True,
        )
    result["textbooks_loaded"] = list(bundle.textbooks)
    result["generator"] = bundle.meta
    return {"data": result}


@router.get("/datasets/{dataset_id}")
def dataset_detail(dataset_id: str, session: Session = Depends(get_db)) -> dict:
    dataset = get_dataset(session, dataset_id)
    assert_can_read(dataset)
    return {
        "data": {
            "id": dataset.id,
            "name": dataset.name,
            "description": dataset.description,
            "evidence_class": dataset.evidence_class,
            "is_synthetic": dataset.is_synthetic,
            "status": dataset.status,
            "summary": summarize_dataset(session, dataset_id),
        }
    }


@router.get("/datasets/{dataset_id}/summary")
def dataset_summary(dataset_id: str, session: Session = Depends(get_db)) -> dict:
    require_dataset(session, dataset_id)
    return {"data": summarize_dataset(session, dataset_id)}


@router.get("/datasets/{dataset_id}/imports")
def dataset_imports(dataset_id: str, session: Session = Depends(get_db)) -> dict:
    require_dataset(session, dataset_id)
    jobs = session.scalars(select(ImportJob).where(ImportJob.dataset_id == dataset_id)).all()
    return {
        "data": [
            {
                "id": job.id,
                "filename": job.filename,
                "status": job.status,
                "rows_read": job.rows_read,
                "rows_accepted": job.rows_accepted,
                "rows_rejected": job.rows_rejected,
                "rows_duplicate": job.rows_duplicate,
                "encoding": job.encoding,
                "created_at": job.created_at.isoformat(),
            }
            for job in jobs
        ]
    }


@router.get("/datasets/{dataset_id}/issues")
def dataset_issues(dataset_id: str, limit: int = Query(default=100, le=500), session: Session = Depends(get_db)) -> dict:
    require_dataset(session, dataset_id)
    issues = session.scalars(select(ImportIssue).where(ImportIssue.dataset_id == dataset_id).limit(limit)).all()
    return {
        "data": [
            {
                "row_number": issue.row_number,
                "severity": issue.severity,
                "code": issue.code,
                "message": issue.message,
            }
            for issue in issues
        ]
    }


@router.delete("/datasets/{dataset_id}")
def remove_dataset(dataset_id: str, session: Session = Depends(get_db)) -> dict:
    assert_can_read(get_dataset(session, dataset_id))
    if not delete_dataset(session, dataset_id):
        raise NotFoundError("Dataset was not found.")
    return {"data": {"deleted": True, "dataset_id": dataset_id}}


@router.get("/assessments")
def assessments(dataset_id: str, session: Session = Depends(get_db)) -> dict:
    from app.models.entities import Assessment

    require_dataset(session, dataset_id)
    rows = session.scalars(select(Assessment).where(Assessment.dataset_id == dataset_id)).all()
    return {"data": [{"id": row.external_id, "name": row.name, "assessment_date": row.assessment_date} for row in rows]}


@router.get("/analytics/overview")
def analytics_overview(dataset_id: str, min_students: int = 30, session: Session = Depends(get_db)) -> dict:
    result = run_diagnostics(session, dataset_id, min_students=min_students)
    return {"data": {"overview": result["overview"], "coverage": result["coverage"], "evidence_class": result["evidence_class"], "limitations": result["limitations"]}}


@router.get("/analytics/topics")
def analytics_topics(dataset_id: str, min_students: int = 30, session: Session = Depends(get_db)) -> dict:
    return {"data": run_diagnostics(session, dataset_id, min_students=min_students)}


@router.get("/analytics/topics/{topic_id}")
def analytics_topic(topic_id: str, dataset_id: str, min_students: int = 30, session: Session = Depends(get_db)) -> dict:
    result = run_diagnostics(session, dataset_id, min_students=min_students)
    match = next((row for row in result["topics"] if row["topic_id"] == topic_id), None)
    if match is None:
        raise NotFoundError("Topic was not found in this dataset.")
    return {
        "data": {
            "topic": match,
            "by_school": [row for row in result["by_school"] if row["topic_id"] == topic_id],
            "by_grade": [row for row in result["by_grade"] if row["topic_id"] == topic_id],
            "over_time": [row for row in result["over_time"] if row["topic_id"] == topic_id],
            "distribution": next((row for row in result["distribution"] if row["topic_id"] == topic_id), None),
            "evidence_class": result["evidence_class"],
        }
    }


@router.get("/topics")
def topics(dataset_id: str, session: Session = Depends(get_db)) -> dict:
    require_dataset(session, dataset_id)
    return {"data": load_topics(session, dataset_id)}


@router.get("/knowledge-graph")
def knowledge_graph(dataset_id: str, min_students: int = 30, session: Session = Depends(get_db)) -> dict:
    return {"data": run_graph(session, dataset_id, min_students=min_students)}


@router.get("/knowledge-graph/risks")
def knowledge_risks(dataset_id: str, session: Session = Depends(get_db)) -> dict:
    graph = run_graph(session, dataset_id)
    return {"data": {"risks": graph["risks"], "limitations": graph["limitations"]}}


@router.get("/knowledge-graph/export")
def knowledge_export(dataset_id: str, session: Session = Depends(get_db)) -> dict:
    graph = run_graph(session, dataset_id)
    return {"data": graph["frontend_graph"]}


@router.post("/knowledge-graph/edges")
def add_edge(dataset_id: str, body: EdgeIn, session: Session = Depends(get_db)) -> dict:
    from app.data_ingestion.csv_loader import ParseResult
    import pandas as pd

    require_dataset(session, dataset_id)
    existing = load_edges(session, dataset_id)
    existing.append(body.model_dump())
    frame = pd.DataFrame(
        [
            {
                "prerequisite_topic_id": edge["prerequisite_topic_id"],
                "dependent_topic_id": edge["dependent_topic_id"],
                "relation_status": edge.get("relation_status") or edge.get("status") or "verified",
                "source": edge.get("source") or "manual",
                "notes": edge.get("notes") or "",
                "confidence": edge.get("confidence"),
            }
            for edge in existing
        ]
    )
    from app.data_ingestion.service import _replace_prerequisites

    _replace_prerequisites(session, dataset_id, frame)
    session.commit()
    return {"data": run_graph(session, dataset_id)}


@router.post("/knowledge-graph/infer")
def infer_edges(dataset_id: str, session: Session = Depends(get_db)) -> dict:
    return {"data": run_inference(session, dataset_id)}


@router.post("/textbooks/ingest")
def ingest_textbook(
    dataset_id: str = Form(...),
    material_id: str = Form(...),
    title: str = Form(""),
    upload: UploadFile = File(...),
    session: Session = Depends(get_db),
) -> dict:
    payload = _read_upload(upload, (".txt", ".pdf"))
    text = ingest_upload(payload, upload.filename or "textbook.txt")
    result = save_material_text(session, dataset_id, material_id, title or material_id, text, upload.filename or "")
    return {"data": result}


@router.get("/textbooks")
def list_textbooks(dataset_id: str, session: Session = Depends(get_db)) -> dict:
    from app.models.entities import Material

    require_dataset(session, dataset_id)
    rows = session.scalars(select(Material).where(Material.dataset_id == dataset_id)).all()
    return {
        "data": [
            {
                "material_id": row.external_id,
                "title": row.title,
                "is_synthetic": row.is_synthetic,
                "has_text": bool(row.raw_text),
                "counts": (row.structure or {}).get("counts"),
            }
            for row in rows
        ]
    }


@router.get("/textbooks/{material_id}")
def textbook_detail(material_id: str, dataset_id: str, session: Session = Depends(get_db)) -> dict:
    from app.models.entities import Material

    row = session.scalar(select(Material).where(Material.dataset_id == dataset_id, Material.external_id == material_id))
    if row is None:
        raise NotFoundError("Textbook was not found in this dataset.")
    return {"data": {"material_id": row.external_id, "title": row.title, "structure": row.structure, "is_synthetic": row.is_synthetic}}


@router.post("/textbook-comparison")
def textbook_comparison(dataset_id: str, session: Session = Depends(get_db)) -> dict:
    return {"data": run_textbook_comparison(session, dataset_id)}


@router.get("/curriculum/allocations")
def allocations(dataset_id: str, session: Session = Depends(get_db)) -> dict:
    require_dataset(session, dataset_id)
    return {"data": load_allocations(session, dataset_id)}


@router.post("/optimization/scenarios")
def optimize(body: OptimizeIn, session: Session = Depends(get_db)) -> dict:
    result = run_optimization(
        session,
        body.dataset_id,
        total_hours=body.total_hours,
        beta=body.beta,
        transfer_tau=body.transfer_tau,
        target_accuracy=body.target_accuracy,
        max_change_hours=body.max_change_hours,
        proposed_hours=body.proposed_hours,
        topics=body.topics,
    )
    if result.get("status") == "infeasible":
        raise AppError("infeasible_constraints", result.get("message", "Infeasible constraints."), 422, result)
    return {"data": result}


@router.get("/optimization/scenarios")
def list_optimization(dataset_id: str, session: Session = Depends(get_db)) -> dict:
    require_dataset(session, dataset_id)
    rows = session.scalars(
        select(Artifact).where(Artifact.dataset_id == dataset_id, Artifact.kind == "optimization").order_by(Artifact.created_at.desc())
    ).all()
    return {"data": [{"id": row.id, "created_at": row.created_at.isoformat(), "status": row.payload.get("status")} for row in rows]}


@router.get("/optimization/scenarios/{artifact_id}")
def get_optimization(artifact_id: str, session: Session = Depends(get_db)) -> dict:
    row = session.get(Artifact, artifact_id)
    if row is None or row.kind != "optimization":
        raise NotFoundError("Optimization scenario was not found.")
    return {"data": row.payload, "meta": {"id": row.id, "dataset_id": row.dataset_id}}


@router.post("/causal-analysis")
def causal(body: CausalIn, session: Session = Depends(get_db)) -> dict:
    return {"data": run_causal(session, body.dataset_id, body.material_a, body.material_b, n_bootstrap=body.n_bootstrap)}


@router.post("/recommendations/generate")
def recommendations(dataset_id: str, session: Session = Depends(get_db)) -> dict:
    return {"data": run_recommendations(session, dataset_id)}


@router.get("/recommendations")
def list_recommendations(dataset_id: str, session: Session = Depends(get_db)) -> dict:
    row = session.scalar(
        select(Artifact).where(Artifact.dataset_id == dataset_id, Artifact.kind == "recommendations").order_by(Artifact.created_at.desc())
    )
    if row is None:
        return {"data": run_recommendations(session, dataset_id)}
    return {"data": row.payload}


@router.post("/reports/generate")
def generate_report(body: ReportIn, session: Session = Depends(get_db)) -> dict:
    dataset = require_dataset(session, body.dataset_id)
    diagnostics = run_diagnostics(session, body.dataset_id)
    graph = run_graph(session, body.dataset_id)
    optimization = run_optimization(session, body.dataset_id) if load_allocations(session, body.dataset_id) else None
    textbook = run_textbook_comparison(session, body.dataset_id)
    causal_result = run_causal(session, body.dataset_id, n_bootstrap=30)
    recommendations_result = run_recommendations(session, body.dataset_id)
    payload = build_report_payload(
        dataset={
            "id": dataset.id,
            "name": body.title or dataset.name,
            "evidence_class": dataset.evidence_class,
            "is_synthetic": dataset.is_synthetic,
            "summary": dataset.summary,
        },
        diagnostics=diagnostics,
        graph=graph,
        textbook=textbook,
        optimization=optimization,
        causal=causal_result,
        recommendations=recommendations_result,
    )
    settings = get_settings()
    directory = settings.data_path / "reports"
    directory.mkdir(parents=True, exist_ok=True)
    report = Report(dataset_id=dataset.id, title=payload["title"], summary={"evidence_class": dataset.evidence_class})
    session.add(report)
    session.flush()
    json_path = directory / f"{report.id}.json"
    pdf_path = directory / f"{report.id}.pdf"
    csv_path = directory / f"{report.id}.zip"
    write_json(json_path, payload)
    write_pdf(pdf_path, payload)
    write_csv_zip(csv_path, payload)
    report.json_path = str(json_path)
    report.pdf_path = str(pdf_path)
    report.csv_path = str(csv_path)
    report.summary = payload
    session.commit()
    return {"data": {"report_id": report.id, "title": report.title, "formats": ["json", "pdf", "csv"]}}


@router.get("/reports/{report_id}")
def report_detail(report_id: str, session: Session = Depends(get_db)) -> dict:
    report = _owned_report(session, report_id)
    payload = report.summary or {}
    return {"data": payload, "meta": {"report_id": report.id}}


def _owned_report(session: Session, report_id: str) -> Report:
    report = session.get(Report, report_id)
    if report is None:
        raise NotFoundError("Report was not found.")
    assert_can_read(get_dataset(session, report.dataset_id))
    return report


def _report_bytes(report: Report, format: str) -> tuple[bytes, str, str]:
    payload = report.summary or {}
    if format == "json":
        import json

        return json.dumps(payload, ensure_ascii=False).encode("utf-8"), "application/json", "json"
    settings = get_settings()
    directory = settings.data_path / "reports"
    directory.mkdir(parents=True, exist_ok=True)
    if format == "pdf":
        path = directory / f"{report.id}.pdf"
        if not path.exists():
            write_pdf(path, payload)
        return path.read_bytes(), "application/pdf", "pdf"
    if format == "csv":
        path = directory / f"{report.id}.zip"
        if not path.exists():
            write_csv_zip(path, payload)
        return path.read_bytes(), "application/zip", "zip"
    raise AppError("invalid_format", "format must be pdf, csv, or json.", 400)


@router.get("/reports/{report_id}/download")
def report_download(report_id: str, format: str = "pdf", session: Session = Depends(get_db)):
    report = _owned_report(session, report_id)
    body, media, extension = _report_bytes(report, format)
    return Response(
        content=body,
        media_type=media,
        headers={"Content-Disposition": f'attachment; filename="qadammetrics-{report.id}.{extension}"'},
    )


@router.get("/ai/status")
def ai_status() -> dict:
    return {"data": copilot.status()}


@router.post("/ai/explain")
def ai_explain(body: ExplainIn, session: Session = Depends(get_db)) -> dict:
    facts = body.facts or {}
    if body.dataset_id and not facts:
        dataset = require_dataset(session, body.dataset_id)
        diagnostics = run_diagnostics(session, body.dataset_id)
        graph = run_graph(session, body.dataset_id)
        facts = {
            "evidence_class": dataset.evidence_class,
            "overview": diagnostics.get("overview"),
            "topics": diagnostics.get("topics"),
            "risks": graph.get("risks"),
            "limitations": diagnostics.get("limitations"),
        }
    return {"data": copilot.explain(body.task, facts, body.question)}

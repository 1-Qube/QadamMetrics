"""Load a dataset and run analytical modules. Routes stay thin."""

from __future__ import annotations

import json

import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analytics.causal_analysis.engine import analyze_textbook_contrast
from app.analytics.curriculum_optimizer.engine import optimize_allocation
from app.analytics.diagnostics.engine import diagnose
from app.analytics.knowledge_graph.engine import build_graph, infer_dependencies
from app.analytics.recommendations.engine import recommend
from app.analytics.textbook_intelligence.engine import compare_textbooks, extract_structure
from app.core.errors import NotFoundError
from app.models.entities import Allocation, Artifact, Dataset, Material, Prerequisite, Response, Topic


def require_dataset(session: Session, dataset_id: str) -> Dataset:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        raise NotFoundError(f"Dataset {dataset_id} was not found.")
    return dataset


def load_responses(session: Session, dataset_id: str) -> pd.DataFrame:
    rows = session.execute(
        select(
            Response.student_external_id,
            Response.school_external_id,
            Response.school_name,
            Response.grade_level,
            Response.subject_external_id,
            Response.topic_external_id,
            Response.topic_name,
            Response.assessment_external_id,
            Response.assessment_date,
            Response.question_external_id,
            Response.material_external_id,
            Response.credit,
            Response.extra,
        ).where(Response.dataset_id == dataset_id)
    ).all()
    frame = pd.DataFrame(
        rows,
        columns=[
            "student_id",
            "school_id",
            "school_name",
            "grade_level",
            "subject_id",
            "topic_id",
            "topic_name",
            "assessment_id",
            "assessment_date",
            "question_id",
            "material_id",
            "credit",
            "extra",
        ],
    )
    return frame


def load_topics(session: Session, dataset_id: str) -> list[dict]:
    topics = session.scalars(select(Topic).where(Topic.dataset_id == dataset_id)).all()
    return [
        {
            "topic_id": topic.external_id,
            "topic_name": topic.name,
            "grade_level": topic.grade_level,
            "description": topic.description,
        }
        for topic in topics
    ]


def load_edges(session: Session, dataset_id: str) -> list[dict]:
    edges = session.scalars(select(Prerequisite).where(Prerequisite.dataset_id == dataset_id)).all()
    return [
        {
            "prerequisite_topic_id": edge.prerequisite_external_id,
            "dependent_topic_id": edge.dependent_external_id,
            "relation_status": edge.status,
            "source": edge.source,
            "confidence": edge.confidence,
            "notes": edge.notes,
        }
        for edge in edges
    ]


def load_allocations(session: Session, dataset_id: str) -> list[dict]:
    rows = session.scalars(
        select(Allocation).where(Allocation.dataset_id == dataset_id, Allocation.scenario_name == "current")
    ).all()
    return [
        {
            "topic_id": row.topic_external_id,
            "hours": row.hours,
            "min_hours": row.min_hours,
            "max_hours": row.max_hours,
            "importance_weight": row.importance_weight,
            "subject_id": row.subject_external_id,
        }
        for row in rows
    ]


def run_diagnostics(session: Session, dataset_id: str, min_students: int = 30) -> dict:
    dataset = require_dataset(session, dataset_id)
    topics = pd.DataFrame(load_topics(session, dataset_id))
    result = jsonable(diagnose(
        load_responses(session, dataset_id),
        topics if not topics.empty else None,
        min_students=min_students,
        evidence_class=dataset.evidence_class,
    ))
    _store(session, dataset_id, "diagnostics", result)
    return result


def run_graph(session: Session, dataset_id: str, min_students: int = 30) -> dict:
    diagnostics = run_diagnostics(session, dataset_id, min_students=min_students)
    result = jsonable(build_graph(load_topics(session, dataset_id), load_edges(session, dataset_id), diagnostics))
    _store(session, dataset_id, "graph", result)
    return result


def run_inference(session: Session, dataset_id: str) -> dict:
    require_dataset(session, dataset_id)
    return jsonable(infer_dependencies(load_responses(session, dataset_id), load_topics(session, dataset_id), load_edges(session, dataset_id)))


def run_optimization(session: Session, dataset_id: str, **kwargs) -> dict:
    dataset = require_dataset(session, dataset_id)
    diagnostics = run_diagnostics(session, dataset_id)
    graph = build_graph(load_topics(session, dataset_id), load_edges(session, dataset_id), diagnostics)
    diagnostics = {**diagnostics, "graph_nodes": graph["nodes"]}
    topics = kwargs.pop("topics", None) or load_allocations(session, dataset_id)
    result = optimize_allocation(topics, diagnostics=diagnostics, edges=load_edges(session, dataset_id), **kwargs)
    result["evidence_class"] = dataset.evidence_class
    result = jsonable(result)
    _store(session, dataset_id, "optimization", result)
    return result


def run_causal(session: Session, dataset_id: str, material_a: str | None = None, material_b: str | None = None, n_bootstrap: int = 200) -> dict:
    dataset = require_dataset(session, dataset_id)
    frame = load_responses(session, dataset_id)
    students = _student_causal_frame(frame, material_a, material_b)
    confounders = ["prior_score", "grade_level", "school_id"]
    result = analyze_textbook_contrast(students, confounder_cols=confounders, n_bootstrap=n_bootstrap)
    result["evidence_class"] = dataset.evidence_class
    if dataset.is_synthetic:
        result.setdefault("limitations", []).insert(0, "Synthetic rows follow a known data-generating process. A real upload would not.")
    result = jsonable(result)
    _store(session, dataset_id, "causal", result)
    return result


def _student_causal_frame(frame: pd.DataFrame, material_a: str | None, material_b: str | None) -> pd.DataFrame:
    if frame.empty or "material_id" not in frame.columns:
        return pd.DataFrame()
    work = frame.dropna(subset=["material_id"]).copy()
    if work.empty:
        return pd.DataFrame()
    materials = sorted(work["material_id"].dropna().unique().tolist())
    if material_a and material_b:
        work = work[work["material_id"].isin([material_a, material_b])]
    elif len(materials) > 2:
        work = work[work["material_id"].isin(materials[:2])]
    dates = sorted({value for value in work["assessment_date"].dropna().tolist() if value})
    if len(dates) >= 2:
        prior_date, outcome_date = dates[0], dates[-1]
        prior = work[work["assessment_date"] == prior_date].groupby("student_id")["credit"].mean()
        outcome = work[work["assessment_date"] == outcome_date].groupby("student_id")["credit"].mean()
    else:
        prior = pd.Series(dtype=float)
        outcome = work.groupby("student_id")["credit"].mean()
    meta = work.groupby("student_id").agg(
        treatment=("material_id", "first"),
        school_id=("school_id", "first"),
        grade_level=("grade_level", "first"),
    )
    table = meta.join(outcome.rename("outcome"), how="inner")
    if not prior.empty:
        table = table.join(prior.rename("prior_score"), how="left")
    return table.reset_index()


def run_textbook_comparison(session: Session, dataset_id: str) -> dict:
    dataset = require_dataset(session, dataset_id)
    materials = session.scalars(select(Material).where(Material.dataset_id == dataset_id)).all()
    topics = load_topics(session, dataset_id)
    payloads = []
    for material in materials:
        structure = material.structure or {}
        if material.raw_text and not structure:
            structure = extract_structure(material.raw_text, topics)
            material.structure = structure
        payloads.append(
            {
                "material_id": material.external_id,
                "title": material.title,
                "is_synthetic": material.is_synthetic or dataset.is_synthetic,
                "raw_text": material.raw_text,
                "structure": structure,
            }
        )
    outcomes = _material_outcomes(load_responses(session, dataset_id))
    result = compare_textbooks(payloads, topics, outcomes)
    result["evidence_class"] = dataset.evidence_class
    result = jsonable(result)
    session.commit()
    _store(session, dataset_id, "textbook_comparison", result)
    return result


def _material_outcomes(frame: pd.DataFrame) -> list[dict]:
    if frame.empty or frame["material_id"].dropna().empty:
        return []
    rows = []
    student = frame.dropna(subset=["material_id"]).groupby(["material_id", "student_id"])["credit"].mean().reset_index()
    school = frame.dropna(subset=["material_id"]).groupby(["material_id", "school_id"]).size().reset_index(name="n")
    schools_per_material = school.groupby("material_id")["school_id"].nunique()
    materials_per_school = frame.dropna(subset=["material_id"]).groupby("school_id")["material_id"].nunique()
    confounded = bool(len(materials_per_school) and (materials_per_school == 1).all())
    for material_id, group in student.groupby("material_id"):
        rows.append(
            {
                "material_id": material_id,
                "n_students": int(group["student_id"].nunique()),
                "mean_credit": round(float(group["credit"].mean()), 4),
                "n_schools": int(schools_per_material.get(material_id, 0)),
                "confounded": confounded,
            }
        )
    return rows


def run_recommendations(session: Session, dataset_id: str) -> dict:
    dataset = require_dataset(session, dataset_id)
    diagnostics = run_diagnostics(session, dataset_id)
    graph = build_graph(load_topics(session, dataset_id), load_edges(session, dataset_id), diagnostics)
    optimization = None
    if load_allocations(session, dataset_id):
        optimization = run_optimization(session, dataset_id)
    textbook = None
    if session.scalars(select(Material).where(Material.dataset_id == dataset_id, Material.raw_text != "")).first():
        textbook = run_textbook_comparison(session, dataset_id)
    causal = None
    responses = load_responses(session, dataset_id)
    if not responses.empty and responses["material_id"].nunique(dropna=True) >= 2:
        causal = run_causal(session, dataset_id, n_bootstrap=40)
    result = jsonable(recommend(
        diagnostics,
        graph,
        optimization,
        textbook,
        causal,
        evidence_class=dataset.evidence_class,
    ))
    _store(session, dataset_id, "recommendations", result)
    return result


def save_material_text(session: Session, dataset_id: str, external_id: str, title: str, text: str, filename: str, is_synthetic: bool = False) -> dict:
    require_dataset(session, dataset_id)
    topics = load_topics(session, dataset_id)
    structure = extract_structure(text, topics)
    material = session.scalar(select(Material).where(Material.dataset_id == dataset_id, Material.external_id == external_id))
    if material is None:
        material = Material(dataset_id=dataset_id, external_id=external_id, title=title)
        session.add(material)
    material.title = title or material.title
    material.raw_text = text
    material.structure = structure
    material.source_filename = filename
    material.is_synthetic = is_synthetic
    session.commit()
    return jsonable({"material_id": external_id, "title": material.title, "structure": structure})


def jsonable(value):
    """Convert NumPy scalars before JSON columns are written."""

    def default(item):
        if hasattr(item, "item"):
            return item.item()
        raise TypeError(f"Object of type {type(item).__name__} is not JSON serializable")

    return json.loads(json.dumps(value, default=default))


def _store(session: Session, dataset_id: str, kind: str, payload: dict) -> Artifact:
    artifact = Artifact(dataset_id=dataset_id, kind=kind, payload=jsonable(payload))
    session.add(artifact)
    session.commit()
    return artifact

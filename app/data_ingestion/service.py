"""Persist validated educational records. Datasets are isolated by dataset_id."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.data_ingestion.csv_loader import Issue, ParseResult
from app.models.entities import (
    Allocation,
    Artifact,
    Assessment,
    Dataset,
    ImportIssue,
    ImportJob,
    Material,
    Prerequisite,
    Question,
    Report,
    Response,
    School,
    Student,
    Subject,
    Topic,
    new_id,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def create_dataset(
    session: Session,
    *,
    name: str,
    description: str = "",
    source_type: str = "csv_upload",
    is_synthetic: bool = False,
    visibility: str = "private",
    owner_token: str | None = None,
) -> Dataset:
    dataset = Dataset(
        name=name,
        description=description,
        source_type=source_type,
        is_synthetic=is_synthetic,
        evidence_class="synthetic" if is_synthetic else "uploaded",
        status="importing",
        visibility=visibility,
        owner_token=owner_token,
    )
    session.add(dataset)
    session.flush()
    return dataset


def _save_issues(session: Session, dataset_id: str, job_id: str, issues: list[Issue]) -> None:
    session.add_all(
        [
            ImportIssue(
                import_job_id=job_id,
                dataset_id=dataset_id,
                row_number=issue.row_number,
                severity=issue.severity,
                code=issue.code,
                message=issue.message,
                raw=issue.raw,
            )
            for issue in issues
        ]
    )


def _get_or_create_map(session: Session, model, dataset_id: str, external_ids: list[str], factory) -> dict[str, str]:
    existing = {
        row.external_id: row
        for row in session.scalars(select(model).where(model.dataset_id == dataset_id)).all()
    }
    for external_id in external_ids:
        if external_id and external_id not in existing:
            obj = factory(external_id)
            session.add(obj)
            session.flush()
            existing[external_id] = obj
    return {key: value.id for key, value in existing.items()}


def ingest_parsed(
    session: Session,
    *,
    name: str,
    responses: ParseResult,
    prerequisites: ParseResult | None = None,
    allocations: ParseResult | None = None,
    topics: ParseResult | None = None,
    description: str = "",
    is_synthetic: bool = False,
    source_type: str = "csv_upload",
    visibility: str = "private",
    owner_token: str | None = None,
) -> dict:
    dataset = create_dataset(
        session,
        name=name,
        description=description,
        source_type=source_type,
        is_synthetic=is_synthetic,
        visibility=visibility,
        owner_token=owner_token,
    )
    job = ImportJob(
        dataset_id=dataset.id,
        filename=responses.filename,
        encoding=responses.encoding,
        rows_read=responses.rows_read,
        rows_accepted=responses.rows_accepted,
        rows_rejected=responses.rows_rejected,
        rows_duplicate=responses.rows_duplicate,
    )
    session.add(job)
    session.flush()
    all_issues = list(responses.issues)
    for extra in (prerequisites, allocations, topics):
        if extra is not None:
            all_issues.extend(extra.issues)

    frame = responses.frame
    if not frame.empty:
        school_ids = _get_or_create_map(
            session,
            School,
            dataset.id,
            sorted(frame["school_id"].unique()),
            lambda external_id: School(
                dataset_id=dataset.id,
                external_id=external_id,
                name=str(frame.loc[frame["school_id"] == external_id, "school_name"].iloc[0]),
            ),
        )
        subject_ids = _get_or_create_map(
            session,
            Subject,
            dataset.id,
            sorted(frame["subject_id"].unique()),
            lambda external_id: Subject(
                dataset_id=dataset.id,
                external_id=external_id,
                name=str(frame.loc[frame["subject_id"] == external_id, "subject_name"].iloc[0]),
            ),
        )
        topic_names = (
            frame.groupby("topic_id")["topic_name"].agg(lambda series: next(v for v in series if v)).to_dict()
            if not frame.empty
            else {}
        )
        topic_subjects = frame.groupby("topic_id")["subject_id"].first().to_dict()
        topic_ids = _get_or_create_map(
            session,
            Topic,
            dataset.id,
            sorted(frame["topic_id"].unique()),
            lambda external_id: Topic(
                dataset_id=dataset.id,
                external_id=external_id,
                name=str(topic_names.get(external_id, external_id)),
                subject_id=subject_ids.get(topic_subjects.get(external_id, "")),
            ),
        )
        student_ids = _get_or_create_map(
            session,
            Student,
            dataset.id,
            sorted(frame["student_id"].unique()),
            lambda external_id: Student(
                dataset_id=dataset.id,
                external_id=external_id,
                school_id=school_ids.get(str(frame.loc[frame["student_id"] == external_id, "school_id"].iloc[0])),
                grade_level=int(frame.loc[frame["student_id"] == external_id, "grade_level"].iloc[0]),
            ),
        )
        assessment_ids = _get_or_create_map(
            session,
            Assessment,
            dataset.id,
            sorted(frame["assessment_id"].unique()),
            lambda external_id: Assessment(
                dataset_id=dataset.id,
                external_id=external_id,
                name=str(frame.loc[frame["assessment_id"] == external_id, "assessment_name"].iloc[0]),
                subject_id=subject_ids.get(str(frame.loc[frame["assessment_id"] == external_id, "subject_id"].iloc[0])),
                assessment_date=_first_date(frame, external_id),
            ),
        )
        question_ids = _get_or_create_map(
            session,
            Question,
            dataset.id,
            sorted(frame["question_id"].unique()),
            lambda external_id: Question(
                dataset_id=dataset.id,
                external_id=external_id,
                assessment_id=assessment_ids.get(
                    str(frame.loc[frame["question_id"] == external_id, "assessment_id"].iloc[0])
                ),
                topic_id=topic_ids.get(str(frame.loc[frame["question_id"] == external_id, "topic_id"].iloc[0])),
                max_score=_first_optional_float(frame, "question_id", external_id, "max_score"),
            ),
        )
        material_values = sorted({value for value in frame["material_id"].dropna().unique() if value})
        material_ids = _get_or_create_map(
            session,
            Material,
            dataset.id,
            material_values,
            lambda external_id: Material(
                dataset_id=dataset.id,
                external_id=external_id,
                title=external_id,
                is_synthetic=is_synthetic,
            ),
        )
        payload = []
        for record in frame.to_dict(orient="records"):
            payload.append(
                {
                    "id": new_id(),
                    "dataset_id": dataset.id,
                    "duplicate_key": record["duplicate_key"],
                    "student_id": student_ids.get(record["student_id"]),
                    "school_id": school_ids.get(record["school_id"]),
                    "question_id": question_ids.get(record["question_id"]),
                    "assessment_id": assessment_ids.get(record["assessment_id"]),
                    "topic_id": topic_ids.get(record["topic_id"]),
                    "material_id": material_ids.get(record["material_id"]) if record["material_id"] else None,
                    "student_external_id": record["student_id"],
                    "school_external_id": record["school_id"],
                    "school_name": record["school_name"],
                    "grade_level": int(record["grade_level"]),
                    "subject_external_id": record["subject_id"],
                    "subject_name": record["subject_name"],
                    "topic_external_id": record["topic_id"],
                    "topic_name": record["topic_name"],
                    "assessment_external_id": record["assessment_id"],
                    "assessment_name": record["assessment_name"],
                    "assessment_date": record["assessment_date"],
                    "question_external_id": record["question_id"],
                    "material_external_id": record["material_id"],
                    "credit": float(record["credit"]),
                    "score": record["score"],
                    "max_score": record["max_score"],
                    "answer_text": record["answer_text"] or "",
                    "source_row": record["source_row"],
                    "extra": record["extra"] or {},
                }
            )
        session.bulk_insert_mappings(Response, payload)

    if topics is not None and not topics.frame.empty:
        _upsert_topic_catalog(session, dataset.id, topics.frame)
    if prerequisites is not None and not prerequisites.frame.empty:
        _replace_prerequisites(session, dataset.id, prerequisites.frame)
    if allocations is not None and not allocations.frame.empty:
        _replace_allocations(session, dataset.id, allocations.frame)

    summary = summarize_dataset(session, dataset.id)
    dataset.summary = summary
    dataset.status = "ready" if responses.rows_accepted else "imported_with_no_rows"
    job.status = "completed" if responses.rows_rejected == 0 else "completed_with_errors"
    if responses.rows_accepted == 0:
        job.status = "failed"
    job.finished_at = _now()
    job.summary = summary
    _save_issues(session, dataset.id, job.id, all_issues)
    session.commit()
    return {
        "dataset_id": dataset.id,
        "import_id": job.id,
        "status": job.status,
        "rows_read": job.rows_read,
        "rows_accepted": job.rows_accepted,
        "rows_rejected": job.rows_rejected,
        "rows_duplicate": job.rows_duplicate,
        "encoding": job.encoding,
        "issues_preview": [issue.as_dict() for issue in all_issues[:50]],
        "issue_count": len(all_issues),
        "summary": summary,
        "evidence_class": dataset.evidence_class,
    }


def _first_date(frame: pd.DataFrame, assessment_id: str) -> str | None:
    series = frame.loc[frame["assessment_id"] == assessment_id, "assessment_date"].dropna()
    values = [value for value in series.tolist() if value]
    return values[0] if values else None


def _first_optional_float(frame: pd.DataFrame, key: str, external_id: str, column: str) -> float | None:
    series = frame.loc[frame[key] == external_id, column].dropna()
    if series.empty:
        return None
    try:
        return float(series.iloc[0])
    except (TypeError, ValueError):
        return None


def _upsert_topic_catalog(session: Session, dataset_id: str, frame: pd.DataFrame) -> None:
    for record in frame.to_dict(orient="records"):
        topic = session.scalar(
            select(Topic).where(Topic.dataset_id == dataset_id, Topic.external_id == record["topic_id"])
        )
        subject = session.scalar(
            select(Subject).where(Subject.dataset_id == dataset_id, Subject.external_id == record["subject_id"])
        )
        if subject is None and record.get("subject_id"):
            subject = Subject(dataset_id=dataset_id, external_id=record["subject_id"], name=record.get("subject_name") or record["subject_id"])
            session.add(subject)
            session.flush()
        if topic is None:
            session.add(
                Topic(
                    dataset_id=dataset_id,
                    external_id=record["topic_id"],
                    name=record.get("topic_name") or record["topic_id"],
                    subject_id=subject.id if subject else None,
                    grade_level=record.get("grade_level"),
                    description=record.get("description") or "",
                )
            )
        else:
            topic.name = record.get("topic_name") or topic.name
            topic.grade_level = record.get("grade_level") or topic.grade_level
            topic.description = record.get("description") or topic.description


def _replace_prerequisites(session: Session, dataset_id: str, frame: pd.DataFrame) -> None:
    session.flush()
    session.execute(delete(Prerequisite).where(Prerequisite.dataset_id == dataset_id))
    topics = {
        topic.external_id: topic.id
        for topic in session.scalars(select(Topic).where(Topic.dataset_id == dataset_id)).all()
    }
    for record in frame.to_dict(orient="records"):
        for external_id in (record["prerequisite_topic_id"], record["dependent_topic_id"]):
            if external_id not in topics:
                topic = Topic(dataset_id=dataset_id, external_id=external_id, name=external_id)
                session.add(topic)
                session.flush()
                topics[external_id] = topic.id
        session.add(
            Prerequisite(
                dataset_id=dataset_id,
                prerequisite_topic_id=topics[record["prerequisite_topic_id"]],
                dependent_topic_id=topics[record["dependent_topic_id"]],
                prerequisite_external_id=record["prerequisite_topic_id"],
                dependent_external_id=record["dependent_topic_id"],
                status=record["relation_status"],
                source=record.get("source") or "import",
                confidence=record.get("confidence"),
                notes=record.get("notes") or "",
            )
        )


def _replace_allocations(session: Session, dataset_id: str, frame: pd.DataFrame) -> None:
    session.flush()
    session.execute(delete(Allocation).where(Allocation.dataset_id == dataset_id, Allocation.scenario_name == "current"))
    topics = {
        topic.external_id: topic.id
        for topic in session.scalars(select(Topic).where(Topic.dataset_id == dataset_id)).all()
    }
    for record in frame.to_dict(orient="records"):
        external_id = record["topic_id"]
        if external_id not in topics:
            topic = Topic(dataset_id=dataset_id, external_id=external_id, name=external_id)
            session.add(topic)
            session.flush()
            topics[external_id] = topic.id
        session.add(
            Allocation(
                dataset_id=dataset_id,
                scenario_name="current",
                topic_id=topics[external_id],
                topic_external_id=external_id,
                subject_external_id=record.get("subject_id") or "",
                hours=float(record["hours"]),
                min_hours=float(record["min_hours"]),
                max_hours=float(record["max_hours"]),
                importance_weight=float(record["importance_weight"]),
            )
        )


def summarize_dataset(session: Session, dataset_id: str) -> dict:
    responses = session.scalar(select(func.count()).select_from(Response).where(Response.dataset_id == dataset_id)) or 0
    students = session.scalar(
        select(func.count(func.distinct(Response.student_external_id))).where(Response.dataset_id == dataset_id)
    ) or 0
    schools = session.scalar(
        select(func.count(func.distinct(Response.school_external_id))).where(Response.dataset_id == dataset_id)
    ) or 0
    topics = session.scalar(select(func.count()).select_from(Topic).where(Topic.dataset_id == dataset_id)) or 0
    questions = session.scalar(select(func.count()).select_from(Question).where(Question.dataset_id == dataset_id)) or 0
    edges = session.scalar(select(func.count()).select_from(Prerequisite).where(Prerequisite.dataset_id == dataset_id)) or 0
    mean_credit = session.scalar(select(func.avg(Response.credit)).where(Response.dataset_id == dataset_id))
    return {
        "responses": int(responses),
        "students": int(students),
        "schools": int(schools),
        "topics": int(topics),
        "questions": int(questions),
        "prerequisite_edges": int(edges),
        "mean_credit": None if mean_credit is None else round(float(mean_credit), 4),
    }


def get_dataset(session: Session, dataset_id: str) -> Dataset | None:
    return session.get(Dataset, dataset_id)


def delete_dataset(session: Session, dataset_id: str) -> bool:
    dataset = session.get(Dataset, dataset_id)
    if dataset is None:
        return False
    for model in (ImportIssue, ImportJob, Response, Question, Assessment, Prerequisite, Allocation, Material, Student, Topic, Subject, School, Artifact, Report):
        session.execute(delete(model).where(model.dataset_id == dataset_id))
    session.delete(dataset)
    session.commit()
    return True

"""Relational model for educational datasets.

Identifiers that come from schools are stored as external ids and scoped by
dataset_id so two uploads cannot see each other's students. Surrogate ids are
hex UUIDs so the same schema works on SQLite and PostgreSQL.
"""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def new_id() -> str:
    return uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    source_type: Mapped[str] = mapped_column(String(64), default="csv_upload")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    evidence_class: Mapped[str] = mapped_column(String(32), default="uploaded")
    status: Mapped[str] = mapped_column(String(32), default="ready")
    visibility: Mapped[str] = mapped_column(String(16), default="public", index=True)
    owner_token: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)

    imports: Mapped[list["ImportJob"]] = relationship(back_populates="dataset")


class ImportJob(Base):
    __tablename__ = "import_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255), default="")
    status: Mapped[str] = mapped_column(String(32), default="running")
    rows_read: Mapped[int] = mapped_column(Integer, default=0)
    rows_accepted: Mapped[int] = mapped_column(Integer, default=0)
    rows_rejected: Mapped[int] = mapped_column(Integer, default=0)
    rows_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    encoding: Mapped[str] = mapped_column(String(32), default="utf-8")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[dict] = mapped_column(JSON, default=dict)

    dataset: Mapped[Dataset] = relationship(back_populates="imports")
    issues: Mapped[list["ImportIssue"]] = relationship(back_populates="job")


class ImportIssue(Base):
    __tablename__ = "import_issues"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    import_job_id: Mapped[str] = mapped_column(ForeignKey("import_jobs.id", ondelete="CASCADE"), index=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    row_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    severity: Mapped[str] = mapped_column(String(16))
    code: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    raw: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    job: Mapped[ImportJob] = relationship(back_populates="issues")


class School(Base):
    __tablename__ = "schools"
    __table_args__ = (UniqueConstraint("dataset_id", "external_id", name="uq_school_ext"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255), default="")
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class Student(Base):
    __tablename__ = "students"
    __table_args__ = (UniqueConstraint("dataset_id", "external_id", name="uq_student_ext"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(128))
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)
    grade_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (UniqueConstraint("dataset_id", "external_id", name="uq_subject_ext"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255), default="")


class Topic(Base):
    __tablename__ = "topics"
    __table_args__ = (UniqueConstraint("dataset_id", "external_id", name="uq_topic_ext"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255), default="")
    subject_id: Mapped[str | None] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    grade_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class Prerequisite(Base):
    __tablename__ = "prerequisites"
    __table_args__ = (
        UniqueConstraint(
            "dataset_id",
            "prerequisite_external_id",
            "dependent_external_id",
            name="uq_prereq_pair",
        ),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    prerequisite_topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), nullable=True)
    dependent_topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), nullable=True)
    prerequisite_external_id: Mapped[str] = mapped_column(String(128))
    dependent_external_id: Mapped[str] = mapped_column(String(128))
    status: Mapped[str] = mapped_column(String(16), default="verified")
    source: Mapped[str] = mapped_column(String(64), default="import")
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")


class Material(Base):
    __tablename__ = "materials"
    __table_args__ = (UniqueConstraint("dataset_id", "external_id", name="uq_material_ext"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(String(255), default="")
    kind: Mapped[str] = mapped_column(String(32), default="textbook")
    language: Mapped[str] = mapped_column(String(16), default="en")
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_text: Mapped[str] = mapped_column(Text, default="")
    structure: Mapped[dict] = mapped_column(JSON, default=dict)
    source_filename: Mapped[str] = mapped_column(String(255), default="")


class Assessment(Base):
    __tablename__ = "assessments"
    __table_args__ = (UniqueConstraint("dataset_id", "external_id", name="uq_assessment_ext"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(128))
    name: Mapped[str] = mapped_column(String(255), default="")
    subject_id: Mapped[str | None] = mapped_column(ForeignKey("subjects.id", ondelete="SET NULL"), nullable=True)
    assessment_date: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (UniqueConstraint("dataset_id", "external_id", name="uq_question_ext"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    external_id: Mapped[str] = mapped_column(String(128))
    assessment_id: Mapped[str | None] = mapped_column(ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    prompt: Mapped[str] = mapped_column(Text, default="")
    cognitive_level: Mapped[str | None] = mapped_column(String(32), nullable=True)


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (
        UniqueConstraint("dataset_id", "duplicate_key", name="uq_response_dup"),
        Index("ix_response_dataset_topic", "dataset_id", "topic_external_id"),
        Index("ix_response_dataset_student", "dataset_id", "student_external_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    duplicate_key: Mapped[str] = mapped_column(String(512))
    student_id: Mapped[str | None] = mapped_column(ForeignKey("students.id", ondelete="SET NULL"), nullable=True)
    school_id: Mapped[str | None] = mapped_column(ForeignKey("schools.id", ondelete="SET NULL"), nullable=True)
    question_id: Mapped[str | None] = mapped_column(ForeignKey("questions.id", ondelete="SET NULL"), nullable=True)
    assessment_id: Mapped[str | None] = mapped_column(ForeignKey("assessments.id", ondelete="SET NULL"), nullable=True)
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    material_id: Mapped[str | None] = mapped_column(ForeignKey("materials.id", ondelete="SET NULL"), nullable=True)
    student_external_id: Mapped[str] = mapped_column(String(128))
    school_external_id: Mapped[str] = mapped_column(String(128))
    school_name: Mapped[str] = mapped_column(String(255), default="")
    grade_level: Mapped[int] = mapped_column(Integer)
    subject_external_id: Mapped[str] = mapped_column(String(128))
    subject_name: Mapped[str] = mapped_column(String(255), default="")
    topic_external_id: Mapped[str] = mapped_column(String(128))
    topic_name: Mapped[str] = mapped_column(String(255), default="")
    assessment_external_id: Mapped[str] = mapped_column(String(128))
    assessment_name: Mapped[str] = mapped_column(String(255), default="")
    assessment_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    question_external_id: Mapped[str] = mapped_column(String(128))
    material_external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    credit: Mapped[float] = mapped_column(Float)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    answer_text: Mapped[str] = mapped_column(Text, default="")
    source_row: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra: Mapped[dict] = mapped_column(JSON, default=dict)


class Allocation(Base):
    __tablename__ = "allocations"
    __table_args__ = (
        UniqueConstraint("dataset_id", "scenario_name", "topic_external_id", name="uq_alloc"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    scenario_name: Mapped[str] = mapped_column(String(64), default="current")
    topic_id: Mapped[str | None] = mapped_column(ForeignKey("topics.id", ondelete="SET NULL"), nullable=True)
    topic_external_id: Mapped[str] = mapped_column(String(128))
    subject_external_id: Mapped[str] = mapped_column(String(128), default="")
    hours: Mapped[float] = mapped_column(Float)
    min_hours: Mapped[float] = mapped_column(Float, default=0.0)
    max_hours: Mapped[float] = mapped_column(Float, default=0.0)
    importance_weight: Mapped[float] = mapped_column(Float, default=1.0)


class Artifact(Base):
    __tablename__ = "artifacts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(64), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    json_path: Mapped[str] = mapped_column(String(500), default="")
    pdf_path: Mapped[str] = mapped_column(String(500), default="")
    csv_path: Mapped[str] = mapped_column(String(500), default="")
    summary: Mapped[dict] = mapped_column(JSON, default=dict)

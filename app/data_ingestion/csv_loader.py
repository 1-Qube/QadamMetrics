"""CSV parsing and row-level validation for assessment uploads.

Problematic rows are reported. They are not silently dropped.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

REQUIRED_RESPONSE_FIELDS = (
    "student_id",
    "school_id",
    "grade_level",
    "subject_id",
    "topic_id",
    "assessment_id",
    "question_id",
)

ALIASES: dict[str, tuple[str, ...]] = {
    "student_id": ("student_id", "student", "learner_id", "ученик"),
    "school_id": ("school_id", "school", "школа"),
    "school_name": ("school_name", "school_title"),
    "grade_level": ("grade_level", "grade", "class", "класс"),
    "subject_id": ("subject_id", "subject", "предмет"),
    "subject_name": ("subject_name",),
    "topic_id": ("topic_id", "topic", "тема"),
    "topic_name": ("topic_name", "topic_title"),
    "assessment_id": ("assessment_id", "test_id", "exam_id"),
    "assessment_name": ("assessment_name", "test_name"),
    "assessment_date": ("assessment_date", "date", "test_date"),
    "question_id": ("question_id", "item_id"),
    "is_correct": ("is_correct", "correct", "верно"),
    "score": ("score", "points", "балл"),
    "max_score": ("max_score", "max_points"),
    "material_id": ("material_id", "textbook_id", "resource_id"),
    "answer_text": ("answer_text", "answer", "response"),
    "prerequisite_topic_id": ("prerequisite_topic_id", "prerequisite_id", "prereq_topic_id", "from_topic"),
    "dependent_topic_id": ("dependent_topic_id", "dependent_id", "to_topic"),
    "relation_status": ("relation_status", "status", "edge_status"),
    "source": ("source",),
    "notes": ("notes", "note"),
    "confidence": ("confidence",),
    "hours": ("hours", "teaching_hours"),
    "min_hours": ("min_hours", "minimum_hours"),
    "max_hours": ("max_hours", "maximum_hours"),
    "importance_weight": ("importance_weight", "importance", "weight"),
    "title": ("title", "name"),
    "kind": ("kind", "type"),
    "language": ("language", "lang"),
    "text": ("text", "body", "raw_text"),
    "description": ("description",),
}

TRUE_VALUES = {"1", "true", "t", "yes", "y", "correct", "верно"}
FALSE_VALUES = {"0", "false", "f", "no", "n", "incorrect", "неверно"}
FORMULA_PREFIXES = ("=", "+", "-", "@")


@dataclass
class Issue:
    row_number: int | None
    severity: str
    code: str
    message: str
    raw: dict | None = None

    def as_dict(self) -> dict:
        return {
            "row_number": self.row_number,
            "severity": self.severity,
            "code": self.code,
            "message": self.message,
            "raw": self.raw,
        }


@dataclass
class ParseResult:
    frame: pd.DataFrame
    issues: list[Issue] = field(default_factory=list)
    rows_read: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    rows_duplicate: int = 0
    encoding: str = "utf-8"
    filename: str = ""


def decode_bytes(payload: bytes) -> tuple[str, str]:
    for encoding in ("utf-8-sig", "utf-8", "cp1251"):
        try:
            return payload.decode(encoding), encoding
        except UnicodeDecodeError:
            continue
    return payload.decode("latin-1"), "latin-1"


def _canonicalize(columns: list[str]) -> dict[str, str]:
    lookup = {str(column).strip().lower(): column for column in columns}
    mapping: dict[str, str] = {}
    used: set[str] = set()
    for canonical, aliases in ALIASES.items():
        for alias in aliases:
            original = lookup.get(alias.lower())
            if original is not None and original not in used:
                mapping[canonical] = original
                used.add(original)
                break
    return mapping


def read_csv_frame(payload: bytes) -> tuple[pd.DataFrame, str]:
    text, encoding = decode_bytes(payload)
    if not text.strip():
        return pd.DataFrame(), encoding
    frame = pd.read_csv(io.StringIO(text), dtype=str)
    frame.columns = [str(column).strip() for column in frame.columns]
    frame = frame.fillna("")
    return frame, encoding


def _cell(row: pd.Series, mapping: dict[str, str], name: str) -> str:
    source = mapping.get(name)
    if source is None:
        return ""
    value = row.get(source, "")
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def parse_bool(value: str) -> bool | None:
    token = value.strip().lower()
    if token in TRUE_VALUES:
        return True
    if token in FALSE_VALUES:
        return False
    return None


def parse_date(value: str) -> str | None:
    token = value.strip()
    if not token:
        return None
    patterns = ("%Y-%m-%d", "%Y/%m/%d", "%d.%m.%Y", "%Y-%m-%dT%H:%M:%S")
    for pattern in patterns:
        try:
            return datetime.strptime(token[:19], pattern).date().isoformat()
        except ValueError:
            continue
    return None


def _number(value: str) -> float | None:
    token = value.strip().replace(",", ".")
    if not token:
        return None
    try:
        return float(token)
    except ValueError:
        return None


def _formula_warning(field_name: str, value: str) -> str | None:
    if value.startswith(FORMULA_PREFIXES):
        return f"{field_name} starts with a spreadsheet formula prefix and was stored as text, not evaluated."
    return None


def parse_responses_csv(payload: bytes, filename: str = "responses.csv") -> ParseResult:
    frame, encoding = read_csv_frame(payload)
    result = ParseResult(frame=pd.DataFrame(), encoding=encoding, filename=filename, rows_read=len(frame))
    if frame.empty and not len(frame.columns):
        result.issues.append(Issue(None, "error", "EMPTY_FILE", "The CSV file is empty."))
        return result
    mapping = _canonicalize(list(frame.columns))
    missing = [name for name in REQUIRED_RESPONSE_FIELDS if name not in mapping]
    has_outcome = "is_correct" in mapping or "score" in mapping
    if missing or not has_outcome:
        needed = list(missing)
        if not has_outcome:
            needed.append("is_correct or score")
        result.issues.append(
            Issue(
                None,
                "error",
                "MISSING_COLUMNS",
                "Required columns are missing: " + ", ".join(needed),
            )
        )
        result.rows_rejected = len(frame)
        return result

    accepted: list[dict] = []
    seen: set[str] = set()
    known = set(mapping.values())
    extra_columns = [column for column in frame.columns if column not in known]

    for offset, row in frame.iterrows():
        row_number = int(offset) + 2  # header is line 1
        raw = {str(k): str(v) for k, v in row.to_dict().items()}
        errors: list[Issue] = []
        warnings: list[Issue] = []
        values = {name: _cell(row, mapping, name) for name in ALIASES}

        for name in REQUIRED_RESPONSE_FIELDS:
            if not values[name]:
                errors.append(Issue(row_number, "error", "MISSING_REQUIRED", f"{name} is empty.", raw))

        grade: int | None = None
        if values["grade_level"]:
            try:
                grade = int(float(values["grade_level"]))
            except ValueError:
                errors.append(Issue(row_number, "error", "INVALID_GRADE", "grade_level is not an integer.", raw))
            else:
                if grade < 1 or grade > 13:
                    errors.append(
                        Issue(row_number, "error", "INVALID_GRADE", "grade_level must be between 1 and 13.", raw)
                    )

        is_correct = parse_bool(values["is_correct"]) if values["is_correct"] else None
        if values["is_correct"] and is_correct is None:
            errors.append(
                Issue(
                    row_number,
                    "error",
                    "INVALID_BOOLEAN",
                    "is_correct must be true/false, 1/0, or correct/incorrect.",
                    raw,
                )
            )
        score = _number(values["score"]) if values["score"] else None
        max_score = _number(values["max_score"]) if values["max_score"] else None
        if values["score"] and score is None:
            errors.append(Issue(row_number, "error", "INVALID_NUMBER", "score is not a number.", raw))
        if values["max_score"] and max_score is None:
            errors.append(Issue(row_number, "error", "INVALID_NUMBER", "max_score is not a number.", raw))
        if score is not None and max_score is not None and max_score <= 0:
            errors.append(Issue(row_number, "error", "INVALID_NUMBER", "max_score must be positive.", raw))

        credit: float | None = None
        if is_correct is not None:
            credit = 1.0 if is_correct else 0.0
        elif score is not None and max_score is not None:
            credit = min(1.0, max(0.0, score / max_score))
            if 0 < credit < 1:
                warnings.append(
                    Issue(
                        row_number,
                        "warning",
                        "PARTIAL_CREDIT",
                        "Partial credit was stored as score/max_score. Binary correctness was not supplied.",
                        None,
                    )
                )
        elif score is not None and 0.0 <= score <= 1.0:
            credit = score
            warnings.append(
                Issue(
                    row_number,
                    "warning",
                    "SCORE_ASSUMED_CREDIT",
                    "score is in [0, 1] and max_score is missing, so score was used as credit.",
                    None,
                )
            )
        elif not errors:
            errors.append(
                Issue(
                    row_number,
                    "error",
                    "MISSING_OUTCOME",
                    "Provide is_correct, or score with max_score.",
                    raw,
                )
            )

        assessment_date = None
        if values["assessment_date"]:
            assessment_date = parse_date(values["assessment_date"])
            if assessment_date is None:
                errors.append(
                    Issue(
                        row_number,
                        "error",
                        "INVALID_DATE",
                        "assessment_date must be YYYY-MM-DD, YYYY/MM/DD, or DD.MM.YYYY.",
                        raw,
                    )
                )
        else:
            warnings.append(
                Issue(row_number, "warning", "MISSING_DATE", "assessment_date is empty. Time trends cannot use this row.", None)
            )

        for field_name in ("student_id", "school_id", "topic_id", "question_id"):
            note = _formula_warning(field_name, values[field_name])
            if note:
                warnings.append(Issue(row_number, "warning", "CSV_FORMULA_PREFIX", note, None))

        duplicate_key = "|".join(
            [
                values["student_id"],
                values["assessment_id"],
                values["question_id"],
                assessment_date or "",
            ]
        )
        if not errors and duplicate_key in seen:
            result.rows_duplicate += 1
            result.rows_rejected += 1
            result.issues.append(
                Issue(
                    row_number,
                    "error",
                    "DUPLICATE_RESPONSE",
                    "Duplicate of an earlier row with the same student, assessment, question, and date. The first row was kept.",
                    raw,
                )
            )
            continue
        if errors:
            result.rows_rejected += 1
            result.issues.extend(errors)
            continue

        seen.add(duplicate_key)
        extra = {}
        for column in extra_columns:
            token = str(row.get(column, "")).strip()
            if token:
                extra[column] = token
        accepted.append(
            {
                "student_id": values["student_id"],
                "school_id": values["school_id"],
                "school_name": values["school_name"] or values["school_id"],
                "grade_level": grade,
                "subject_id": values["subject_id"],
                "subject_name": values["subject_name"] or values["subject_id"],
                "topic_id": values["topic_id"],
                "topic_name": values["topic_name"] or values["topic_id"],
                "assessment_id": values["assessment_id"],
                "assessment_name": values["assessment_name"] or values["assessment_id"],
                "assessment_date": assessment_date,
                "question_id": values["question_id"],
                "credit": credit,
                "score": score,
                "max_score": max_score,
                "material_id": values["material_id"] or None,
                "answer_text": values["answer_text"],
                "duplicate_key": duplicate_key,
                "source_row": row_number,
                "extra": extra,
            }
        )
        result.issues.extend(warnings)

    result.frame = pd.DataFrame(accepted)
    result.rows_accepted = len(accepted)
    return result


def parse_prerequisites_csv(payload: bytes) -> ParseResult:
    frame, encoding = read_csv_frame(payload)
    result = ParseResult(frame=pd.DataFrame(), encoding=encoding, filename="prerequisites.csv", rows_read=len(frame))
    if frame.empty:
        result.issues.append(Issue(None, "warning", "EMPTY_FILE", "Prerequisite file is empty."))
        return result
    mapping = _canonicalize(list(frame.columns))
    if "prerequisite_topic_id" not in mapping or "dependent_topic_id" not in mapping:
        result.issues.append(
            Issue(None, "error", "MISSING_COLUMNS", "Prerequisites need prerequisite_topic_id and dependent_topic_id.")
        )
        result.rows_rejected = len(frame)
        return result
    rows = []
    seen: set[tuple[str, str]] = set()
    for offset, row in frame.iterrows():
        row_number = int(offset) + 2
        source = _cell(row, mapping, "prerequisite_topic_id")
        target = _cell(row, mapping, "dependent_topic_id")
        if not source or not target:
            result.rows_rejected += 1
            result.issues.append(Issue(row_number, "error", "MISSING_REQUIRED", "Prerequisite endpoints are empty."))
            continue
        if source == target:
            result.rows_rejected += 1
            result.issues.append(Issue(row_number, "error", "INVALID_EDGE", "A topic cannot be its own prerequisite."))
            continue
        status = (_cell(row, mapping, "relation_status") or "verified").lower()
        if status not in {"verified", "inferred"}:
            result.issues.append(
                Issue(row_number, "warning", "STATUS_DEFAULTED", f"Unknown relation status '{status}' stored as verified.")
            )
            status = "verified"
        if (source, target) in seen:
            result.rows_duplicate += 1
            result.rows_rejected += 1
            result.issues.append(Issue(row_number, "error", "DUPLICATE_EDGE", "Duplicate prerequisite edge. First row kept."))
            continue
        seen.add((source, target))
        confidence = _number(_cell(row, mapping, "confidence"))
        rows.append(
            {
                "prerequisite_topic_id": source,
                "dependent_topic_id": target,
                "relation_status": status,
                "source": _cell(row, mapping, "source") or "import",
                "notes": _cell(row, mapping, "notes"),
                "confidence": confidence,
            }
        )
    result.frame = pd.DataFrame(rows)
    result.rows_accepted = len(rows)
    return result


def parse_allocations_csv(payload: bytes) -> ParseResult:
    frame, encoding = read_csv_frame(payload)
    result = ParseResult(frame=pd.DataFrame(), encoding=encoding, filename="allocations.csv", rows_read=len(frame))
    if frame.empty:
        result.issues.append(Issue(None, "warning", "EMPTY_FILE", "Allocation file is empty."))
        return result
    mapping = _canonicalize(list(frame.columns))
    if "topic_id" not in mapping or "hours" not in mapping:
        result.issues.append(Issue(None, "error", "MISSING_COLUMNS", "Allocations need topic_id and hours."))
        result.rows_rejected = len(frame)
        return result
    rows = []
    seen: set[str] = set()
    for offset, row in frame.iterrows():
        row_number = int(offset) + 2
        topic_id = _cell(row, mapping, "topic_id")
        hours = _number(_cell(row, mapping, "hours"))
        if not topic_id or hours is None:
            result.rows_rejected += 1
            result.issues.append(Issue(row_number, "error", "MISSING_REQUIRED", "topic_id and numeric hours are required."))
            continue
        if hours < 0:
            result.rows_rejected += 1
            result.issues.append(Issue(row_number, "error", "INVALID_NUMBER", "hours cannot be negative."))
            continue
        if topic_id in seen:
            result.rows_duplicate += 1
            result.rows_rejected += 1
            result.issues.append(Issue(row_number, "error", "DUPLICATE_ALLOCATION", "Duplicate topic allocation. First row kept."))
            continue
        seen.add(topic_id)
        min_hours = _number(_cell(row, mapping, "min_hours"))
        max_hours = _number(_cell(row, mapping, "max_hours"))
        importance = _number(_cell(row, mapping, "importance_weight"))
        rows.append(
            {
                "topic_id": topic_id,
                "subject_id": _cell(row, mapping, "subject_id"),
                "hours": hours,
                "min_hours": 0.0 if min_hours is None else min_hours,
                "max_hours": hours if max_hours is None else max_hours,
                "importance_weight": 1.0 if importance is None else importance,
            }
        )
    result.frame = pd.DataFrame(rows)
    result.rows_accepted = len(rows)
    return result


def parse_topics_csv(payload: bytes) -> ParseResult:
    frame, encoding = read_csv_frame(payload)
    result = ParseResult(frame=pd.DataFrame(), encoding=encoding, filename="topics.csv", rows_read=len(frame))
    if frame.empty:
        return result
    mapping = _canonicalize(list(frame.columns))
    if "topic_id" not in mapping:
        result.issues.append(Issue(None, "error", "MISSING_COLUMNS", "Topics file needs topic_id."))
        result.rows_rejected = len(frame)
        return result
    rows = []
    for offset, row in frame.iterrows():
        topic_id = _cell(row, mapping, "topic_id")
        if not topic_id:
            result.rows_rejected += 1
            result.issues.append(Issue(int(offset) + 2, "error", "MISSING_REQUIRED", "topic_id is empty."))
            continue
        grade_token = _cell(row, mapping, "grade_level")
        grade = int(float(grade_token)) if grade_token else None
        rows.append(
            {
                "topic_id": topic_id,
                "topic_name": _cell(row, mapping, "topic_name") or _cell(row, mapping, "title") or topic_id,
                "subject_id": _cell(row, mapping, "subject_id") or "math",
                "subject_name": _cell(row, mapping, "subject_name") or "Mathematics",
                "grade_level": grade,
                "description": _cell(row, mapping, "description"),
            }
        )
    result.frame = pd.DataFrame(rows)
    result.rows_accepted = len(rows)
    return result


def issues_to_json(issues: list[Issue]) -> str:
    return json.dumps([issue.as_dict() for issue in issues])

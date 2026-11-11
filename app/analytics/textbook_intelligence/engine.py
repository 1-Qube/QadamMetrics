"""Rule-based textbook structure extraction and structural comparison.

A richer structure is not evidence of better learning.
"""

from __future__ import annotations

import io
import re
from pathlib import Path

from app.analytics.methodology import METHODOLOGY_VERSION, TEXTBOOKS

CHAPTER_RE = re.compile(r"^(chapter|unit|глава|раздел)\s+[\divxlc0-9]+", re.IGNORECASE)
LABELS = {
    "definition": re.compile(r"\b(definition|определение)\b", re.IGNORECASE),
    "explanation": re.compile(r"\b(explanation|explain|пояснение)\b", re.IGNORECASE),
    "example": re.compile(r"\b(example|worked example|пример)\b", re.IGNORECASE),
    "exercise": re.compile(r"\b(exercise|exercises|practice|упражнени[ея])\b", re.IGNORECASE),
    "question": re.compile(r"\b(question|questions|вопрос)\b", re.IGNORECASE),
}
MATH_RE = re.compile(
    r"([A-Za-z0-9]+\s*\^\s*[0-9]+|[A-Za-z]\s*=\s*[^.\n]{1,60}|\([^)\n]{1,30}\)\s*\([^)\n]{1,30}\))"
)
BLOOM = (
    ("create", ("design", "construct", "devise", "compose", "prove")),
    ("evaluate", ("justify", "critique", "evaluate", "judge", "argue")),
    ("analyze", ("compare", "contrast", "analyze", "distinguish", "classify")),
    ("apply", ("calculate", "solve", "compute", "find", "simplify", "factor", "graph")),
    ("understand", ("explain", "describe", "interpret", "summarize")),
    ("remember", ("define", "list", "state", "name", "identify", "recall")),
)


def extract_text_from_pdf(payload: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(payload))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(pages)


def load_document(payload: bytes, filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(payload)
    for encoding in ("utf-8-sig", "utf-8", "cp1251", "latin-1"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("latin-1", errors="replace")


def classify_cognitive_demand(text: str) -> str:
    lowered = text.lower()
    found = "unclassified"
    rank = -1
    for index, (level, words) in enumerate(BLOOM):
        if any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in words):
            if index > rank:
                rank = index
                found = level
    # BLOOM is ordered high to low, so the first match is the highest demand.
    for level, words in BLOOM:
        if any(re.search(rf"\b{re.escape(word)}\b", lowered) for word in words):
            return level
    return found


def extract_structure(text: str, topics: list[dict] | None = None) -> dict:
    lines = [line.strip() for line in text.splitlines()]
    chapters: list[dict] = []
    current = {"title": "Front matter", "line_start": 1, "lines": []}
    blocks = {key: [] for key in ("definition", "explanation", "example", "exercise", "question")}
    expressions = []
    for index, line in enumerate(lines, start=1):
        if not line:
            continue
        if CHAPTER_RE.match(line):
            if current["lines"]:
                chapters.append({"title": current["title"], "line_start": current["line_start"], "text": "\n".join(current["lines"])})
            current = {"title": line, "line_start": index, "lines": []}
            continue
        current["lines"].append(line)
        matched = False
        for label, pattern in LABELS.items():
            if pattern.search(line):
                item = {"line": index, "text": line, "cognitive_demand": classify_cognitive_demand(line)}
                blocks[label].append(item)
                matched = True
                break
        if not matched and line[:3].rstrip(".)").isdigit():
            item = {"line": index, "text": line, "cognitive_demand": classify_cognitive_demand(line)}
            blocks["exercise"].append(item)
        expressions.extend({"line": index, "expression": match.group(0)[:80]} for match in MATH_RE.finditer(line))
    if current["lines"]:
        chapters.append({"title": current["title"], "line_start": current["line_start"], "text": "\n".join(current["lines"])})

    topic_hits = []
    lowered = text.lower()
    for topic in topics or []:
        topic_id = topic.get("topic_id") or topic.get("external_id")
        name = str(topic.get("topic_name") or topic.get("name") or "")
        aliases = [name, topic_id or ""]
        aliases.extend(topic.get("aliases") or [])
        mentions = 0
        for alias in aliases:
            token = str(alias).strip().lower()
            if len(token) < 3:
                continue
            mentions += lowered.count(token)
        if mentions:
            explanation_count = sum(1 for item in blocks["explanation"] + blocks["definition"] if name.lower() in item["text"].lower())
            exercise_count = sum(1 for item in blocks["exercise"] if name.lower() and name.lower() in item["text"].lower())
            topic_hits.append(
                {
                    "topic_id": topic_id,
                    "topic_name": name,
                    "mentions": mentions,
                    "explanation_proxy_count": explanation_count,
                    "exercise_mentions": exercise_count,
                    "covered": mentions > 0,
                }
            )

    cognitive = {}
    for item in blocks["exercise"] + blocks["question"]:
        cognitive[item["cognitive_demand"]] = cognitive.get(item["cognitive_demand"], 0) + 1
    stems = {item["text"][:40].lower() for item in blocks["exercise"]}
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "method": "rule_based_structure_v1",
        "cognitive_method": "rule_based_bloom_keywords_v1",
        "chapter_count": len([chapter for chapter in chapters if chapter["title"] != "Front matter"]),
        "chapters": [{"title": chapter["title"], "line_start": chapter["line_start"]} for chapter in chapters],
        "counts": {key: len(value) for key, value in blocks.items()},
        "definitions": blocks["definition"][:30],
        "explanations": blocks["explanation"][:30],
        "examples": blocks["example"][:30],
        "exercises": blocks["exercise"][:80],
        "questions": blocks["question"][:80],
        "expressions": expressions[:40],
        "topic_coverage": topic_hits,
        "cognitive_demand": cognitive,
        "exercise_variety": len(stems),
        "limitations": [
            "Extraction uses headings and keywords. It misses unlabeled pedagogy and can double-count lines.",
            TEXTBOOKS,
        ],
    }


def compare_textbooks(
    materials: list[dict],
    curriculum_topics: list[dict] | None = None,
    outcome_summary: list[dict] | None = None,
) -> dict:
    structures = []
    for material in materials:
        structure = material.get("structure") or extract_structure(material.get("raw_text") or "", curriculum_topics)
        covered = {row["topic_id"] for row in structure.get("topic_coverage", []) if row.get("covered")}
        curriculum_ids = [topic.get("topic_id") or topic.get("external_id") for topic in curriculum_topics or []]
        coverage_ratio = None
        if curriculum_ids:
            coverage_ratio = round(len(covered.intersection(curriculum_ids)) / len(curriculum_ids), 4)
        structures.append(
            {
                "material_id": material.get("material_id") or material.get("external_id"),
                "title": material.get("title"),
                "is_synthetic": material.get("is_synthetic", False),
                "chapter_count": structure.get("chapter_count"),
                "counts": structure.get("counts"),
                "exercise_variety": structure.get("exercise_variety"),
                "cognitive_demand": structure.get("cognitive_demand"),
                "topics_mentioned": sorted(covered),
                "curriculum_coverage_ratio": coverage_ratio,
                "expression_count": len(structure.get("expressions") or []),
                "explanation_completeness_proxy": _explanation_proxy(structure, curriculum_topics or []),
            }
        )
    structural_winner = None
    if len(structures) >= 2:
        structural_winner = max(structures, key=lambda row: (row["curriculum_coverage_ratio"] or 0, row["counts"].get("exercise", 0)))
    outcomes = []
    for row in outcome_summary or []:
        outcomes.append(
            {
                "material_id": row.get("material_id"),
                "n_students": row.get("n_students"),
                "mean_credit": row.get("mean_credit"),
                "claim_level": "association",
                "note": "Unadjusted mean. Not a textbook effect.",
            }
        )
    fair = _fairness_note(outcome_summary)
    return {
        "methodology_version": METHODOLOGY_VERSION,
        "status": "ok" if structures else "insufficient_data",
        "structural_comparison": structures,
        "highest_structural_coverage": None if structural_winner is None else structural_winner["material_id"],
        "structural_statement": (
            "Structural coverage is a property of the text. It does not establish which textbook helps students learn more."
        ),
        "outcome_association": outcomes,
        "outcome_statement": fair,
        "claim_level": "structural_description",
        "limitations": [TEXTBOOKS],
    }


def _explanation_proxy(structure: dict, topics: list[dict]) -> float | None:
    if not topics:
        return None
    coverage = {row["topic_id"]: row for row in structure.get("topic_coverage", [])}
    scores = []
    for topic in topics:
        topic_id = topic.get("topic_id") or topic.get("external_id")
        count = coverage.get(topic_id, {}).get("explanation_proxy_count", 0)
        scores.append(min(1.0, count / 2))
    return round(sum(scores) / len(scores), 4) if scores else None


def _fairness_note(outcome_summary: list[dict] | None) -> str:
    if not outcome_summary:
        return "No linked student outcomes were supplied, so no effectiveness comparison was made."
    if any(row.get("confounded") for row in outcome_summary):
        return (
            "Outcome means differ by material, but the grouping is confounded or unbalanced. "
            "Do not treat the difference as a textbook effect. Use the causal module, and expect it to refuse a causal conclusion if overlap is poor."
        )
    return (
        "Unadjusted outcome means are reported separately from structure. "
        "They are associations. Confounders such as prior achievement, school, and teacher are not controlled here."
    )

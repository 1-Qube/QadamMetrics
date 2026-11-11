"""Gemini copilot with a deterministic fallback.

Numbers in a model narrative must already exist in the analytical facts.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.analytics.methodology import AI, METHODOLOGY_VERSION
from app.core.config import get_settings

logger = logging.getLogger(__name__)
NUMBER_RE = re.compile(r"(?<![A-Za-z])(-?\d+(?:\.\d+)?)%?")


class Copilot:
    def status(self) -> dict:
        settings = get_settings()
        return {
            "provider": "gemini" if settings.ai_configured else "deterministic_fallback",
            "configured": settings.ai_configured,
            "model": settings.gemini_model if settings.ai_configured else None,
            "required_for_core_analytics": False,
        }

    def explain(self, task: str, facts: dict[str, Any], question: str | None = None) -> dict:
        settings = get_settings()
        allowed = _collect_numbers(facts)
        fallback = deterministic_explanation(task, facts, question)
        if not settings.ai_configured:
            return _result("deterministic_fallback", fallback, used_fallback=True, warnings=["GEMINI_API_KEY is not set."], allowed=allowed)
        try:
            text = _gemini(task, facts, question, settings.gemini_api_key, settings.gemini_model, settings.gemini_timeout_seconds)
        except Exception as exc:
            logger.warning("Gemini call failed: %s", type(exc).__name__)
            return _result(
                "deterministic_fallback",
                fallback,
                used_fallback=True,
                warnings=[f"Gemini request failed ({type(exc).__name__}). Deterministic explanation used."],
                allowed=allowed,
            )
        unexpected = unexpected_numbers(text, allowed)
        if unexpected:
            return _result(
                "deterministic_fallback",
                fallback,
                used_fallback=True,
                warnings=[
                    "The model narrative contained numbers that are not in the analytical facts. It was discarded.",
                    "Unexpected numbers: " + ", ".join(unexpected[:8]),
                ],
                allowed=allowed,
                discarded_text=text,
            )
        return _result("gemini", text, used_fallback=False, warnings=[], allowed=allowed)


def _result(provider: str, text: str, *, used_fallback: bool, warnings: list[str], allowed: set[float], discarded_text: str | None = None) -> dict:
    payload = {
        "methodology_version": METHODOLOGY_VERSION,
        "provider": provider,
        "used_fallback": used_fallback,
        "text": text,
        "warnings": warnings,
        "numeric_validation": "passed" if not used_fallback else "fallback",
        "rules": AI,
    }
    if discarded_text is not None:
        payload["numeric_validation"] = "failed"
        payload["discarded"] = True
    return payload


def _gemini(task: str, facts: dict, question: str | None, api_key: str, model: str, timeout: float) -> str:
    prompt = {
        "task": task,
        "question": question,
        "instructions": [
            "Use only numbers that appear in facts.",
            "Do not invent student performance, textbook effects, or causal claims.",
            "If facts are insufficient, say so.",
            "Distinguish observations from hypotheses.",
            "Return plain prose, under 400 words.",
        ],
        "facts": facts,
    }
    candidate_models = [model]
    for m in ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.1-flash-lite"]:
        if m not in candidate_models:
            candidate_models.append(m)

    last_exc = None
    for cand in candidate_models:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{cand}:generateContent"
        body = {
            "contents": [{"role": "user", "parts": [{"text": json.dumps(prompt, ensure_ascii=False)}]}],
            "generationConfig": {"temperature": 0.2},
        }
        try:
            response = httpx.post(url, params={"key": api_key}, json=body, timeout=timeout)
            response.raise_for_status()
            data = response.json()
            parts = data["candidates"][0]["content"]["parts"]
            return "\n".join(part.get("text", "") for part in parts).strip()
        except Exception as exc:
            logger.warning("Gemini candidate model %s failed: %s", cand, exc)
            last_exc = exc
            continue

    if last_exc:
        raise last_exc
    raise RuntimeError("No candidate Gemini models succeeded")


def deterministic_explanation(task: str, facts: dict, question: str | None = None) -> str:
    lines = [
        "Deterministic explanation from the analytical engine. No language model was used.",
        f"Task: {task}.",
    ]
    if question:
        lines.append(f"Question noted: {question}")
        lines.append("The answer below uses only computed fields. It does not infer missing facts.")
    evidence = facts.get("evidence_class")
    if evidence == "synthetic":
        lines.append("The dataset is synthetic. These sentences demonstrate the software; they are not findings about real students.")
    overview = facts.get("overview") or facts.get("diagnostics", {}).get("overview")
    if overview:
        lines.append(
            "Dataset overview: "
            + ", ".join(f"{key}={value}" for key, value in overview.items() if not isinstance(value, dict))
            + "."
        )
    topics = facts.get("topics") or facts.get("diagnostics", {}).get("topics") or []
    weak = [row for row in topics if row.get("status") == "weak"][:5]
    if weak:
        lines.append("Weak topics under the documented rule:")
        for row in weak:
            lines.append(
                f"- {row.get('topic_name', row.get('topic_id'))}: accuracy {row.get('accuracy')}, "
                f"CI [{row.get('ci_low')}, {row.get('ci_high')}], n={row.get('n_students')}."
            )
    risks = facts.get("risks") or facts.get("graph", {}).get("risks") or []
    for risk in risks[:3]:
        lines.append("Dependency hypothesis: " + risk.get("reasoning", ""))
    if facts.get("claim_level"):
        lines.append(f"Claim level: {facts['claim_level']}. Causal conclusion: {facts.get('causal_conclusion', 'not_claimed')}.")
    if facts.get("message"):
        lines.append(str(facts["message"]))
    recommendations = facts.get("recommendations") or []
    for rec in recommendations[:3]:
        lines.append(f"Recommendation ({rec.get('rule_id')}): {rec.get('recommended_action')}")
    limitations = facts.get("limitations") or []
    if limitations:
        lines.append("Limitation: " + str(limitations[0])[:500])
    if not facts:
        lines.append("No analytical facts were attached. Nothing further was inferred.")
    return "\n".join(lines)


def _collect_numbers(value: Any, found: set[float] | None = None) -> set[float]:
    found = found if found is not None else set()
    if isinstance(value, bool) or value is None:
        return found
    if isinstance(value, (int, float)):
        found.add(round(float(value), 4))
        found.add(round(float(value) * 100, 4))
        return found
    if isinstance(value, str):
        for match in NUMBER_RE.finditer(value):
            found.add(round(float(match.group(1)), 4))
        return found
    if isinstance(value, dict):
        for item in value.values():
            _collect_numbers(item, found)
    elif isinstance(value, (list, tuple)):
        for item in value:
            _collect_numbers(item, found)
    return found


def unexpected_numbers(text: str, allowed: set[float]) -> list[str]:
    unexpected = []
    for match in NUMBER_RE.finditer(text):
        number = round(float(match.group(1)), 4)
        if number in {0.0, 1.0, 2.0, 95.0}:
            continue
        if any(abs(number - item) <= 0.05 for item in allowed):
            continue
        if any(abs(number - item * 100) <= 0.6 for item in allowed if abs(item) <= 1.5):
            continue
        unexpected.append(match.group(0))
    return unexpected

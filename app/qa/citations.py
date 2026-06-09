"""Parse the model's JSON reply into the citation contract (qa.md §6).

The model returns a single JSON object {answer, citations[]}. This module extracts
and parses it tolerantly; the grounding gate (gate.py) then validates each citation.
"""

from __future__ import annotations

import json


def parse_response(text: str) -> dict | None:
    """Parse the model text into {answer, citations}. Return None on failure.

    Tolerant of a stray code fence or surrounding prose: falls back to the widest
    {...} span if a direct parse fails. Returns None if no valid object is found
    or the shape is wrong, so the caller can apply the retry/flag policy.
    """
    if not text:
        return None

    candidate = text.strip()
    # Strip a leading/trailing markdown fence if present.
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        # Drop an optional leading "json" language tag.
        if candidate.lstrip().lower().startswith("json"):
            candidate = candidate.lstrip()[4:]

    obj = _try_load(candidate)
    if obj is None:
        # Fall back to the widest brace span.
        first = text.find("{")
        last = text.rfind("}")
        if first != -1 and last > first:
            obj = _try_load(text[first : last + 1])

    if not isinstance(obj, dict) or "answer" not in obj:
        return None

    answer = obj.get("answer")
    if not isinstance(answer, str):
        return None

    citations = obj.get("citations", [])
    if not isinstance(citations, list):
        citations = []

    return {"answer": answer, "citations": citations}


def _try_load(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None

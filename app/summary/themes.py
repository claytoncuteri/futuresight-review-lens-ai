"""The Haiku 4.5 theme layer (summary.md §5, §7).

Qualitative only, explicitly labeled generated. Inputs are review texts + ratings
(capped at the 50 most recent), never the deterministic metadata — mixing counts in
would invite the model to restate numbers it must not own (the §2 boundary). On any
error or parse failure the layer degrades to absent (empty items + a note); it never
guesses and never blocks the factual core.
"""

from __future__ import annotations

import json
from pathlib import Path

MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 1024
MAX_REVIEWS = 50  # most-recent cap (summary.md §5, §7)
MODEL_LABEL = "haiku-4.5"
UNAVAILABLE_NOTE = "The qualitative theme layer is unavailable; the factual core above is complete."

_PROMPT_FILE = Path(__file__).resolve().parent / "theme_prompt.txt"


def _load_prompt() -> str:
    return _PROMPT_FILE.read_text(encoding="utf-8").strip()


def _make_client():
    import anthropic

    return anthropic.Anthropic()


def _build_input(reviews) -> str:
    """Render up to MAX_REVIEWS recent reviews as rating + text lines."""
    lines = []
    for r in reviews[:MAX_REVIEWS]:
        rating = "N/A" if r.rating is None else str(r.rating)
        lines.append(f"[{rating} stars] {r.text}")
    return "\n".join(lines)


def _extract_text(message) -> str:
    parts = [b.text for b in message.content if getattr(b, "type", None) == "text"]
    return "".join(parts).strip()


def _parse_items(text: str):
    """Parse a JSON array of {label, characterization}. Return list or None."""
    if not text:
        return None
    candidate = text.strip()
    if candidate.startswith("```"):
        candidate = candidate.strip("`")
        if candidate.lstrip().lower().startswith("json"):
            candidate = candidate.lstrip()[4:]
    obj = _try_load(candidate)
    if obj is None:
        first, last = text.find("["), text.rfind("]")
        if first != -1 and last > first:
            obj = _try_load(text[first : last + 1])
    if not isinstance(obj, list):
        return None
    items = []
    for el in obj:
        if isinstance(el, dict) and "label" in el and "characterization" in el:
            items.append(
                {"label": str(el["label"]), "characterization": str(el["characterization"])}
            )
    return items


def _try_load(text: str):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None


def _layer(items: list, note: str | None = None) -> dict:
    layer = {"generated": True, "model": MODEL_LABEL, "items": items}
    if note:
        layer["note"] = note
    return layer


def generate(reviews, client=None) -> dict:
    """Return the theme layer. Degrades to empty items + note on any failure.

    `reviews` is a list of committed Review rows (already recency-ordered by the
    caller). `client` is injectable so tests run without the API key.
    """
    if not reviews:
        return _layer([])  # zero-corpus: no call, empty generated layer (summary.md §7)

    try:
        client = client or _make_client()
        system = _load_prompt()
        user = _build_input(reviews)
        for _attempt in range(2):  # initial try + one retry on parse failure
            message = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            items = _parse_items(_extract_text(message))
            if items is not None:
                return _layer(items)
        return _layer([], UNAVAILABLE_NOTE)  # parse failed twice
    except Exception:
        # Haiku error/timeout: factual core still renders (summary.md §7).
        return _layer([], UNAVAILABLE_NOTE)

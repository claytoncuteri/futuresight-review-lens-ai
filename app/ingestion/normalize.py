"""RawReview -> normalized row (ingestion.md §7).

Shared rules:
- Rating: int in [1,5] or None.
- Date: ISO date string (date only, no time) or None.
- Language: declared value wins; else best-effort detect with langdetect (no model
  download, ingestion.md §7); else 'und'.
- dedup_key: sha1 of normalized (text + rating + ISO date). The original text is
  stored unchanged; only the dedup key uses the normalized form.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, date

# langdetect is non-deterministic by default; seed it so detection (and thus the
# dedup key / language_mix) is reproducible across runs.
from langdetect import detect, DetectorFactory, LangDetectException

DetectorFactory.seed = 0

UNDETERMINED = "und"

# Common non-ISO date formats accepted after an ISO attempt (ingestion.md §6).
_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%B %d, %Y",
    "%b %d, %Y",
    "%d %B %Y",
    "%d %b %Y",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
)

_WHITESPACE = re.compile(r"\s+")


@dataclass
class NormalizedReview:
    """A review normalized and ready to persist (id/ingested_at assigned later)."""

    author: str | None
    rating: int | None
    text: str
    language: str
    published_at: str | None
    dedup_key: str


def coerce_rating(value) -> int | None:
    """Coerce to int in [1,5]; None if absent or out of range/non-numeric.

    For CSV, an out-of-range rating is a row rejection handled by the caller
    *before* normalization; this returns None defensively for any bad value.
    """
    if value is None:
        return None
    if isinstance(value, bool):  # bool is an int subclass; reject explicitly
        return None
    try:
        n = int(str(value).strip())
    except (ValueError, TypeError):
        return None
    return n if 1 <= n <= 5 else None


def parse_date(value) -> str | None:
    """Parse a date tolerantly to an ISO date string (YYYY-MM-DD), else None.

    Stores date only, never time (ingestion.md §7). Accepts RFC3339 timestamps
    (Places `publishTime`) by taking the date portion.
    """
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    # ISO first: handle full RFC3339/ISO timestamps and bare dates.
    iso_candidate = raw.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(iso_candidate).date().isoformat()
    except ValueError:
        pass
    # Bare date portion of a "YYYY-MM-DD ..." or "YYYY-MM-DDT..." string.
    head = re.split(r"[T ]", raw, maxsplit=1)[0]
    try:
        return date.fromisoformat(head).isoformat()
    except ValueError:
        pass
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def detect_language(text: str, declared: str | None) -> str:
    """Declared value wins; else best-effort detect; else 'und' (ingestion.md §7)."""
    if declared:
        d = declared.strip()
        if d:
            return d
    stripped = (text or "").strip()
    if not stripped:
        return UNDETERMINED
    try:
        return detect(stripped)
    except LangDetectException:
        return UNDETERMINED


def _normalize_for_dedup(text: str) -> str:
    """Strip, collapse internal whitespace, casefold (ingestion.md §4)."""
    return _WHITESPACE.sub(" ", (text or "").strip()).casefold()


def compute_dedup_key(text: str, rating: int | None, published_at: str | None) -> str:
    """sha1 over normalized text + rating + ISO date (ingestion.md §4)."""
    basis = "\x1f".join(
        [
            _normalize_for_dedup(text),
            "" if rating is None else str(rating),
            published_at or "",
        ]
    )
    return hashlib.sha1(basis.encode("utf-8")).hexdigest()


def normalize(raw) -> NormalizedReview:
    """Normalize a RawReview. Text is stored verbatim (injection defense is Q&A-side).

    Note: the row-level validation in csv_source rejects rows missing text/rating
    or with out-of-range ratings before reaching here; this function is total and
    coerces defensively so it can also serve the Places path (always valid).
    """
    rating = coerce_rating(raw.rating)
    published_at = parse_date(raw.published_at)
    language = detect_language(raw.text, raw.language)
    author = raw.author.strip() if isinstance(raw.author, str) and raw.author.strip() else None
    return NormalizedReview(
        author=author,
        rating=rating,
        text=raw.text,  # verbatim, unchanged (ingestion.md §9)
        language=language,
        published_at=published_at,
        dedup_key=compute_dedup_key(raw.text, rating, published_at),
    )

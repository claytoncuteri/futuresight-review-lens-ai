"""Deterministic ingestion_run metadata (ingestion.md §7).

Computed in pure Python, never by an LLM. This screen's job is to prove the data
is real (architecture.md §4.5), so every count, distribution, date, and
completeness flag is computed here. The summary plan reads these values
field-for-field and never recomputes them.
"""

from __future__ import annotations

from collections import Counter

GOOGLE_SAMPLE_NOTE = "Google's 5 most relevant reviews, not a representative sample."

# Size bands (ingestion.md §7): tiny < 10, small < 50, ok >= 50.
_TINY = 10
_SMALL = 50


def _pct(numerator: int, denominator: int) -> float:
    """Fraction with a stable rounding; 0.0 for an empty corpus."""
    if denominator == 0:
        return 0.0
    return round(numerator / denominator, 4)


def size_band(count: int) -> str:
    if count < _TINY:
        return "tiny"
    if count < _SMALL:
        return "small"
    return "ok"


def compute_metadata(reviews, source: str) -> dict:
    """Compute the deterministic ingestion_run fields from committed rows.

    `reviews` is a list of NormalizedReview (the rows actually committed). Returns
    a dict with rating_distribution, date_range, language_mix, completeness, and
    review_count, ready for the ingestion_run insert.
    """
    count = len(reviews)

    # Rating distribution: counts per star plus a "null" bucket.
    rating_distribution = {str(star): 0 for star in range(1, 6)}
    rating_distribution["null"] = 0
    for r in reviews:
        key = "null" if r.rating is None else str(r.rating)
        rating_distribution[key] += 1

    # Date range: min/max over parseable dates, plus a missing count.
    dates = [r.published_at for r in reviews if r.published_at]
    missing_dates = count - len(dates)
    date_range = {
        "min": min(dates) if dates else None,
        "max": max(dates) if dates else None,
        "missing": missing_dates,
    }

    # Language mix: counts per language code.
    language_mix = dict(Counter(r.language for r in reviews))

    with_date = len(dates)
    with_author = sum(1 for r in reviews if r.author)
    with_rating = sum(1 for r in reviews if r.rating is not None)

    completeness = {
        "pct_with_date": _pct(with_date, count),
        "pct_with_author": _pct(with_author, count),
        "pct_with_rating": _pct(with_rating, count),
        "size_band": size_band(count),
        "source": source,
        "sample_note": GOOGLE_SAMPLE_NOTE if source == "google_places" else "",
    }

    return {
        "review_count": count,
        "rating_distribution": rating_distribution,
        "date_range": date_range,
        "language_mix": language_mix,
        "completeness": completeness,
    }

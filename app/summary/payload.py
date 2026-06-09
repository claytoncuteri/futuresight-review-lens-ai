"""Assemble the summary payload (summary.md §4, §7).

Reads the deterministic ingestion_run (computed in ingestion.md §7) and shapes the
factual core field-for-field with no transformation and no model. Pulls the theme
layer cache-first. The factual core is independent of the theme layer and always
renders; the theme layer is additive and degrades to absent, never to a fabrication.
"""

from __future__ import annotations

import json

from .. import db
from ..ingestion.base import Review
from . import cache, themes

TOO_SMALL_WARNING = "corpus too small for trend analysis"
EMPTY_WARNING = "no reviews ingested for this entity"


def _latest_run(conn, entity_id: str):
    return conn.execute(
        """
        SELECT * FROM ingestion_run
        WHERE entity_id = ?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (entity_id,),
    ).fetchone()


def _recent_reviews(conn, entity_id: str) -> list[Review]:
    rows = conn.execute(
        """
        SELECT * FROM review
        WHERE entity_id = ?
        ORDER BY (published_at IS NULL), published_at DESC, id
        LIMIT ?
        """,
        (entity_id, themes.MAX_REVIEWS),
    ).fetchall()
    return [Review.from_row(r) for r in rows]


def _build_warnings(factual: dict) -> list[str]:
    warnings: list[str] = []
    completeness = factual["completeness"]
    if factual["review_count"] == 0:
        warnings.append(EMPTY_WARNING)
    elif completeness.get("size_band") == "tiny":
        warnings.append(TOO_SMALL_WARNING)
    sample_note = completeness.get("sample_note")
    if sample_note:
        warnings.append(sample_note)
    return warnings


def build_payload(entity_id: str, theme_client=None) -> dict | None:
    """Return the summary payload, or None if the entity has no ingestion run.

    `theme_client` is injectable so tests run the theme layer without the API key.
    """
    conn = db.get_connection()
    try:
        run = _latest_run(conn, entity_id)
        if run is None:
            return None

        # Factual core: copied from ingestion_run, json-decoded only — no model,
        # no recompute, no rounding (architecture.md §4.5, summary.md §2).
        factual = {
            "review_count": run["review_count"],
            "rating_distribution": json.loads(run["rating_distribution"]),
            "date_range": json.loads(run["date_range"]),
            "language_mix": json.loads(run["language_mix"]),
            "completeness": json.loads(run["completeness"]),
        }

        # Theme layer, cache-first keyed by (entity_id, latest run id).
        run_id = run["id"]
        theme_layer = cache.get(entity_id, run_id)
        if theme_layer is None:
            reviews = _recent_reviews(conn, entity_id)
            theme_layer = themes.generate(reviews, client=theme_client)
            cache.set(entity_id, run_id, theme_layer)

        return {
            "entity_id": entity_id,
            "entity_name": run["entity_name"],
            "source": run["source"],
            "factual": factual,
            "themes": theme_layer,
            "warnings": _build_warnings(factual),
        }
    finally:
        conn.close()

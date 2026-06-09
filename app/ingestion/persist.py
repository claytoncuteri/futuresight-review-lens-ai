"""Transactional persistence: dedup, replace/append/new-entity, caching, atomicity.

A run is all-or-nothing: the review inserts and the ingestion_run insert share one
transaction (ingestion.md §8). A failure rolls back and persists nothing. Dedup is
scoped per entity_id on dedup_key. The 500-row cap (ingestion.md §6) is enforced on
existing + new so an append cannot push an entity over the limit.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from . import metadata as md
from .base import SourceResult
from .normalize import NormalizedReview, normalize

MAX_ROWS = 500  # ingestion.md §6; removed when retrieval lands.

# CSV write modes (ingestion.md §6).
REPLACE = "replace"
APPEND = "append"
NEW_ENTITY = "new-entity"


class RowCapExceeded(Exception):
    """Raised when existing + new valid rows would exceed MAX_ROWS."""

    def __init__(self, attempted: int):
        self.attempted = attempted
        super().__init__(
            f"Upload refused: {attempted} reviews would exceed the {MAX_ROWS}-review "
            f"per-entity cap (the corpus rides in context until retrieval lands)."
        )


@dataclass
class PersistResult:
    entity_id: str
    entity_name: str
    source: str
    run_id: str
    review_count: int
    skipped_duplicates: int


def slug(name: str) -> str:
    """Lowercase, hyphenate; collapse non-alphanumeric runs."""
    s = re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")
    return s or "entity"


def csv_entity_id(name: str) -> str:
    return "csv:" + slug(name)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _existing_count(conn: sqlite3.Connection, entity_id: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM review WHERE entity_id = ?", (entity_id,)
    ).fetchone()
    return row["n"]


def _existing_dedup_keys(conn: sqlite3.Connection, entity_id: str) -> set[str]:
    rows = conn.execute(
        "SELECT dedup_key FROM review WHERE entity_id = ?", (entity_id,)
    ).fetchall()
    return {r["dedup_key"] for r in rows}


def _dedup_within(normalized: list[NormalizedReview]) -> tuple[list[NormalizedReview], int]:
    """Drop in-file duplicates by dedup_key, keeping the first. Returns (kept, dropped)."""
    seen: set[str] = set()
    kept: list[NormalizedReview] = []
    dropped = 0
    for n in normalized:
        if n.dedup_key in seen:
            dropped += 1
            continue
        seen.add(n.dedup_key)
        kept.append(n)
    return kept, dropped


def _next_free_entity_id(conn: sqlite3.Connection, base_entity_id: str) -> str:
    """Suffix the slug (-2, -3, ...) until an unused entity_id is found."""
    candidate = base_entity_id
    suffix = 2
    while _existing_count(conn, candidate) > 0:
        candidate = f"{base_entity_id}-{suffix}"
        suffix += 1
    return candidate


def entity_exists(conn: sqlite3.Connection, entity_id: str) -> bool:
    return _existing_count(conn, entity_id) > 0


def persist(
    conn: sqlite3.Connection,
    result: SourceResult,
    mode: str = REPLACE,
) -> PersistResult:
    """Normalize, dedup, enforce the cap, and write reviews + ingestion_run atomically.

    mode:
      - replace: delete existing rows + runs for the entity, then insert (default;
        also the Places path, where a fetch is authoritative / force-refresh).
      - append: insert only rows whose dedup_key is not already present; cap checked
        against existing + new.
      - new-entity: mint a fresh entity_id by suffixing the slug, ingest there.

    Returns a PersistResult. Raises RowCapExceeded before any write if the cap would
    be breached (no partial work).
    """
    normalized = [normalize(r) for r in result.reviews]
    normalized, in_file_dups = _dedup_within(normalized)

    entity_id = result.entity_id
    skipped = in_file_dups

    if mode == NEW_ENTITY:
        entity_id = _next_free_entity_id(conn, result.entity_id)

    if mode == APPEND:
        existing_keys = _existing_dedup_keys(conn, entity_id)
        before = len(normalized)
        normalized = [n for n in normalized if n.dedup_key not in existing_keys]
        skipped += before - len(normalized)
        projected = _existing_count(conn, entity_id) + len(normalized)
        if projected > MAX_ROWS:
            raise RowCapExceeded(projected)
    else:
        # replace / new-entity: only the incoming valid rows count toward the cap.
        if len(normalized) > MAX_ROWS:
            raise RowCapExceeded(len(normalized))

    run_id = uuid.uuid4().hex
    ingested_at = _now_iso()
    meta = md.compute_metadata(normalized, result.source)

    try:
        with conn:  # one transaction: commit on success, rollback on exception
            if mode == REPLACE:
                conn.execute("DELETE FROM review WHERE entity_id = ?", (entity_id,))
                conn.execute(
                    "DELETE FROM ingestion_run WHERE entity_id = ?", (entity_id,)
                )

            conn.executemany(
                """
                INSERT INTO review
                    (id, entity_id, source, author, rating, text, language,
                     published_at, ingested_at, dedup_key)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        uuid.uuid4().hex,
                        entity_id,
                        result.source,
                        n.author,
                        n.rating,
                        n.text,
                        n.language,
                        n.published_at,
                        ingested_at,
                        n.dedup_key,
                    )
                    for n in normalized
                ],
            )

            conn.execute(
                """
                INSERT INTO ingestion_run
                    (id, entity_id, entity_name, source, review_count,
                     rating_distribution, date_range, language_mix, completeness,
                     created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    entity_id,
                    result.entity_name,
                    result.source,
                    meta["review_count"],
                    json.dumps(meta["rating_distribution"]),
                    json.dumps(meta["date_range"]),
                    json.dumps(meta["language_mix"]),
                    json.dumps(meta["completeness"]),
                    ingested_at,
                ),
            )
    except Exception:
        # `with conn` already rolled back; nothing is persisted (ingestion.md §8).
        raise

    return PersistResult(
        entity_id=entity_id,
        entity_name=result.entity_name,
        source=result.source,
        run_id=run_id,
        review_count=meta["review_count"],
        skipped_duplicates=skipped,
    )

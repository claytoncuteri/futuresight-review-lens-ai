"""The retrieval seam (qa.md §4, architecture.md §4.3, §8).

At MVP `get_context` returns every committed review for the entity and ignores
`question`. This is the single point rag-core swaps in at; the signature does not
change when top-k retrieval lands.
"""

from __future__ import annotations

from .. import db
from ..ingestion.base import Review


def get_context(entity_id: str, question: str) -> list[Review]:
    """Return the full corpus for the entity. `question` is unused at MVP.

    Scale (architecture.md §8): swap the body for rag-core top-k. Signature holds.
    """
    conn = db.get_connection()
    try:
        rows = conn.execute(
            """
            SELECT * FROM review
            WHERE entity_id = ?
            ORDER BY (published_at IS NULL), published_at DESC, id
            """,
            (entity_id,),
        ).fetchall()
    finally:
        conn.close()
    return [Review.from_row(r) for r in rows]


def get_entity_name(entity_id: str) -> str | None:
    """Latest ingestion_run entity_name for the entity, or None if unknown."""
    conn = db.get_connection()
    try:
        row = conn.execute(
            """
            SELECT entity_name FROM ingestion_run
            WHERE entity_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (entity_id,),
        ).fetchone()
    finally:
        conn.close()
    return row["entity_name"] if row else None

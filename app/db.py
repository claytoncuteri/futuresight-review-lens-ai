"""Shared SQLite infrastructure: connection and idempotent schema bootstrap.

`db.py` is shared infra referenced by ingestion, Q&A, and summary. Ingestion owns
the *write shape* (the schema below) because it defines it (ingestion.md §2, §4);
this module only opens connections and creates the tables if absent. Q&A and
summary read these tables, never redefine them.

Schema follows ingestion.md §4: the architecture.md §5 model refined with a
`dedup_key` on `review` and `language_mix` + `completeness` on `ingestion_run`.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

# DB path is configurable so tests can point at a temp file. Default is a
# gitignored file at the repo root (see .gitignore: *.db).
DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "reviewlens.db"


def db_path() -> str:
    """Resolve the SQLite file path from the environment, else the default."""
    return os.environ.get("REVIEWLENS_DB", str(DEFAULT_DB_PATH))


def get_connection(path: str | None = None) -> sqlite3.Connection:
    """Open a connection with row access by column name and FK enforcement.

    Callers are responsible for closing (or using as a context manager for
    transaction scoping). `check_same_thread=False` lets FastAPI's threadpool
    handlers share the process's DB without tripping sqlite's thread guard; at
    MVP scale (single instance, low concurrency) this is safe.
    """
    conn = sqlite3.connect(path or db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# --- Schema (ingestion.md §4) --------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS review (
    id            TEXT PRIMARY KEY,   -- uuid
    entity_id     TEXT NOT NULL,      -- place_id (google) | 'csv:' + slug(name)
    source        TEXT NOT NULL,      -- 'google_places' | 'csv'
    author        TEXT,               -- nullable
    rating        INTEGER,            -- 1..5, nullable
    text          TEXT NOT NULL,
    language      TEXT NOT NULL,      -- declared | detected | 'und'
    published_at  TEXT,               -- ISO date, nullable
    ingested_at   TEXT NOT NULL,      -- ISO datetime
    dedup_key     TEXT NOT NULL       -- sha1 of normalized (text + rating + date)
);

-- Dedup is scoped per entity_id (ingestion.md §4, §8).
CREATE INDEX IF NOT EXISTS idx_review_entity_dedup
    ON review (entity_id, dedup_key);

CREATE INDEX IF NOT EXISTS idx_review_entity
    ON review (entity_id);

CREATE TABLE IF NOT EXISTS ingestion_run (
    id                  TEXT PRIMARY KEY,
    entity_id           TEXT NOT NULL,
    entity_name         TEXT NOT NULL,
    source              TEXT NOT NULL,
    review_count        INTEGER NOT NULL,
    rating_distribution TEXT NOT NULL,   -- json {"5": n, ..., "null": n}
    date_range          TEXT NOT NULL,   -- json {"min": iso|null, "max": iso|null, "missing": n}
    language_mix        TEXT NOT NULL,   -- json {"en": n, "es": n, "und": n}
    completeness        TEXT NOT NULL,   -- json (ingestion.md §7)
    created_at          TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_entity_created
    ON ingestion_run (entity_id, created_at);
"""


def bootstrap(path: str | None = None) -> None:
    """Create tables and indexes if they do not exist. Safe to call repeatedly.

    Invoked from the FastAPI lifespan on every startup (qa.md §3, §8).
    """
    conn = get_connection(path)
    try:
        conn.executescript(_SCHEMA)
        conn.commit()
    finally:
        conn.close()

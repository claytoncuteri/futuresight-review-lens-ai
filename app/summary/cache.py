"""Theme cache keyed by (entity_id, ingestion_run.id) (summary.md §6).

The key includes the latest run id, not entity_id alone, so re-ingestion (a fresh
run is minted on every ingest/replace/append) busts the cache and a changed corpus
never shows stale themes. In-memory; resets on restart (acceptable at MVP). The
factual core is never cached — it is a cheap read of ingestion_run every time.
"""

from __future__ import annotations

_cache: dict[tuple[str, str], dict] = {}


def get(entity_id: str, run_id: str) -> dict | None:
    return _cache.get((entity_id, run_id))


def set(entity_id: str, run_id: str, value: dict) -> None:
    _cache[(entity_id, run_id)] = value


def clear() -> None:
    """Test helper: drop all cached theme layers."""
    _cache.clear()

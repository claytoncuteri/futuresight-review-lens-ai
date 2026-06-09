"""Shared pytest fixtures: an isolated SQLite DB per test, fixtures dir, cache reset."""

from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch, tmp_path):
    """Point every test at a fresh SQLite file and bootstrap the schema.

    db.db_path() reads REVIEWLENS_DB on each call, so setting the env var routes
    all modules (ingestion, qa, summary) at the per-test database.
    """
    from app import db
    from app.summary import cache
    from app.api.limiter import limiter

    db_file = tmp_path / "test.db"
    monkeypatch.setenv("REVIEWLENS_DB", str(db_file))
    db.bootstrap(str(db_file))
    cache.clear()
    limiter._counts.clear()  # module-global singleton; isolate per test
    yield str(db_file)
    cache.clear()
    limiter._counts.clear()


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def conn(isolated_db):
    from app import db

    c = db.get_connection(isolated_db)
    yield c
    c.close()

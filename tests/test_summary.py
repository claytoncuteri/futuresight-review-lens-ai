"""Summary tests (summary.md §9 hooks). Haiku is mocked; factual core is never modeled.

Factual core matches ingestion_run field-for-field, no factual field is modeled,
theme cache hit/miss by run id, Haiku error/non-JSON degradation, google_places
sample_note in warnings, tiny-corpus warning.
"""

from __future__ import annotations

import json

from app.ingestion import persist
from app.ingestion.base import RawReview, SourceResult
from app.ingestion.csv_source import CsvSource
from app.summary import payload, themes


# --- fake Haiku client ---------------------------------------------------------

class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Msg:
    def __init__(self, text):
        self.content = [_Block(text)]


class _FakeHaiku:
    def __init__(self, text=None, raise_exc=False):
        self._text = text
        self._raise = raise_exc
        self.calls = 0
        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.calls += 1
                if outer._raise:
                    raise RuntimeError("haiku down")
                return _Msg(outer._text)

        self.messages = _Messages()


_GOOD = '[{"label": "Patio", "characterization": "Reviewers praise the patio."}]'


def _seed_csv(conn, name="Sum Co", rows=3):
    body = "rating,text,author,date,language\n"
    for i in range(rows):
        body += f"{(i % 5) + 1},review text number {i},A{i},2024-0{(i % 9) + 1}-01,en\n"
    result = CsvSource(body.encode(), name, persist.csv_entity_id(name)).produce()
    return persist.persist(conn, result, mode=persist.REPLACE)


# --- factual core fidelity -----------------------------------------------------

def test_factual_core_matches_ingestion_run_field_for_field(conn):
    pr = _seed_csv(conn, rows=4)
    run = conn.execute(
        "SELECT * FROM ingestion_run WHERE entity_id = ?", (pr.entity_id,)
    ).fetchone()

    p = payload.build_payload(pr.entity_id, theme_client=_FakeHaiku(_GOOD))
    factual = p["factual"]
    assert factual["review_count"] == run["review_count"]
    assert factual["rating_distribution"] == json.loads(run["rating_distribution"])
    assert factual["date_range"] == json.loads(run["date_range"])
    assert factual["language_mix"] == json.loads(run["language_mix"])
    assert factual["completeness"] == json.loads(run["completeness"])


def test_factual_core_is_independent_of_theme_layer(conn):
    pr = _seed_csv(conn, rows=4)
    good = payload.build_payload(pr.entity_id, theme_client=_FakeHaiku(_GOOD))

    # Re-ingest to mint a new run id so the cache misses, then build with a failing
    # theme client; the factual core must be byte-identical regardless.
    from app.summary import cache
    cache.clear()
    _seed_csv(conn, rows=4)
    failed = payload.build_payload(pr.entity_id, theme_client=_FakeHaiku(raise_exc=True))
    assert good["factual"] == failed["factual"]
    assert failed["themes"]["items"] == []  # degraded
    assert "note" in failed["themes"]


# --- theme cache ---------------------------------------------------------------

def test_theme_cache_hit_same_run(conn):
    pr = _seed_csv(conn)
    fake = _FakeHaiku(_GOOD)
    payload.build_payload(pr.entity_id, theme_client=fake)
    payload.build_payload(pr.entity_id, theme_client=fake)
    assert fake.calls == 1  # second build is a cache hit


def test_theme_cache_miss_on_new_run(conn):
    pr = _seed_csv(conn)
    fake = _FakeHaiku(_GOOD)
    payload.build_payload(pr.entity_id, theme_client=fake)
    _seed_csv(conn)  # new ingestion_run id for the same entity
    payload.build_payload(pr.entity_id, theme_client=fake)
    assert fake.calls == 2


# --- degradation ---------------------------------------------------------------

def test_haiku_error_degrades_to_empty_with_note(conn):
    pr = _seed_csv(conn)
    p = payload.build_payload(pr.entity_id, theme_client=_FakeHaiku(raise_exc=True))
    assert p["themes"]["items"] == []
    assert p["themes"]["note"] == themes.UNAVAILABLE_NOTE
    assert p["factual"]["review_count"] == 3  # factual still renders


def test_haiku_non_json_retries_then_degrades(conn):
    pr = _seed_csv(conn)
    fake = _FakeHaiku("not json at all")
    p = payload.build_payload(pr.entity_id, theme_client=fake)
    assert fake.calls == 2  # one retry
    assert p["themes"]["items"] == []
    assert "note" in p["themes"]


# --- warnings ------------------------------------------------------------------

def test_google_places_sample_note_in_warnings(conn):
    reviews = [RawReview(author="A", rating=5, text="great", language="en", published_at="2024-01-01")]
    result = SourceResult(
        entity_id="place_abc", entity_name="Joe's", source="google_places", reviews=reviews
    )
    persist.persist(conn, result, mode=persist.REPLACE)
    p = payload.build_payload("place_abc", theme_client=_FakeHaiku(_GOOD))
    from app.ingestion.metadata import GOOGLE_SAMPLE_NOTE
    assert GOOGLE_SAMPLE_NOTE in p["warnings"]


def test_tiny_corpus_warning(conn):
    pr = _seed_csv(conn, rows=3)  # < 10 → tiny
    p = payload.build_payload(pr.entity_id, theme_client=_FakeHaiku(_GOOD))
    assert payload.TOO_SMALL_WARNING in p["warnings"]


def test_unknown_entity_returns_none(conn):
    assert payload.build_payload("csv:does-not-exist") is None

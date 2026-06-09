"""Q&A tests (qa.md §11 hooks). Anthropic client is mocked; no key or network.

Prompt assembly, grounding gate (bad review_id, non-substring quote), JSON
retry/flag path, limiter proximity + 429 + bucket independence, /api/ask wiring.
"""

from __future__ import annotations

import pytest

from app.ingestion.base import Review
from app.qa import client as qa_client
from app.qa import gate, prompt
from app.api.limiter import FixedWindowLimiter, RateLimitExceeded, QUESTIONS, INGESTS


def _review(rid, text, rating=5, date="2024-03-02", author="Dana P."):
    return Review(
        id=rid, entity_id="csv:x", source="csv", author=author, rating=rating,
        text=text, language="en", published_at=date, ingested_at="2024-03-02T00:00:00Z",
        dedup_key=rid,
    )


# --- prompt assembly -----------------------------------------------------------

def test_prompt_assembly_one_review_element_per_row_with_ids():
    reviews = [_review("r1", "best patio in town"), _review("r2", "parking was full", rating=2)]
    system = prompt.assemble("Joe's Cafe", reviews)
    assert system.count("<review ") == 2
    assert 'review_id="r1"' in system and 'review_id="r2"' in system
    assert "Joe's Cafe" in system
    assert "{{ENTITY_NAME}}" not in system  # substituted everywhere
    # The guard text is loaded verbatim, not paraphrased.
    assert "<reviews>" in system and "</reviews>" in system


def test_prompt_includes_format_directive():
    system = prompt.assemble("X", [_review("r1", "good")])
    assert "single JSON object" in system
    assert "VERBATIM" in system  # quote-verbatim requirement


# --- grounding gate ------------------------------------------------------------

def test_gate_drops_unknown_review_id_and_flags():
    reviews = [_review("r1", "best patio in town")]
    citations = [{"review_id": "nope", "quote": "best patio"}]
    validated, flagged = gate.apply_gate(citations, reviews)
    assert validated == []
    assert flagged is True


def test_gate_drops_non_substring_quote_and_flags():
    reviews = [_review("r1", "best patio in town")]
    citations = [{"review_id": "r1", "quote": "worst service ever"}]
    validated, flagged = gate.apply_gate(citations, reviews)
    assert validated == []
    assert flagged is True


def test_gate_keeps_valid_citation_case_and_whitespace_insensitive():
    reviews = [_review("r1", "The   Best Patio In Town")]
    citations = [{"review_id": "r1", "quote": "best patio in town"}]
    validated, flagged = gate.apply_gate(citations, reviews)
    assert len(validated) == 1
    assert flagged is False


# --- client JSON contract: parse, retry once, flag -----------------------------

class _Block:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class _Msg:
    def __init__(self, text):
        self.content = [_Block(text)]


class _FakeClient:
    """messages.create returns queued texts in order; counts calls."""

    def __init__(self, texts):
        self._texts = list(texts)
        self.calls = 0
        outer = self

        class _Messages:
            def create(self, **kwargs):
                outer.calls += 1
                return _Msg(outer._texts.pop(0))

        self.messages = _Messages()


def test_client_parses_valid_json_first_try():
    fake = _FakeClient(['{"answer": "the patio is praised", "citations": []}'])
    result = qa_client.ask("sys", "q", client=fake)
    assert result.answer == "the patio is praised"
    assert result.flagged is False
    assert fake.calls == 1


def test_client_retries_once_then_flags_on_persistent_bad_json():
    fake = _FakeClient(["not json", "still not json"])
    result = qa_client.ask("sys", "q", client=fake)
    assert fake.calls == 2  # one retry
    assert result.flagged is True
    assert result.citations == []
    assert result.answer == "still not json"  # raw prose served


def test_client_recovers_on_retry():
    fake = _FakeClient(["garbage", '{"answer": "ok now", "citations": []}'])
    result = qa_client.ask("sys", "q", client=fake)
    assert fake.calls == 2
    assert result.flagged is False
    assert result.answer == "ok now"


# --- limiter -------------------------------------------------------------------

def test_limiter_buckets_are_independent():
    lim = FixedWindowLimiter()
    now = 1000.0
    for _ in range(10):
        lim.consume("ip", INGESTS, now=now)
    with pytest.raises(RateLimitExceeded):
        lim.consume("ip", INGESTS, now=now)
    # questions bucket untouched
    lim.consume("ip", QUESTIONS, now=now)
    q = lim.quota("ip", now=now)
    assert q["ingests_remaining"] == 0
    assert q["questions_remaining"] == 29


def test_limiter_proximity_then_429():
    lim = FixedWindowLimiter()
    now = 5000.0
    for _ in range(25):
        lim.consume("ip", QUESTIONS, now=now)
    assert lim.quota("ip", now=now)["questions_remaining"] == 5  # proximity threshold
    for _ in range(5):
        lim.consume("ip", QUESTIONS, now=now)
    with pytest.raises(RateLimitExceeded) as exc:
        lim.consume("ip", QUESTIONS, now=now)
    assert exc.value.bucket == QUESTIONS
    assert exc.value.window_reset  # carries reset time


def test_limiter_window_resets_next_hour():
    lim = FixedWindowLimiter()
    for _ in range(30):
        lim.consume("ip", QUESTIONS, now=0.0)
    with pytest.raises(RateLimitExceeded):
        lim.consume("ip", QUESTIONS, now=0.0)
    # New hour: fresh allowance.
    lim.consume("ip", QUESTIONS, now=3601.0)
    assert lim.quota("ip", now=3601.0)["questions_remaining"] == 29


# --- /api/ask wiring -----------------------------------------------------------

def _seed_entity(conn):
    from app.ingestion import persist
    from app.ingestion.csv_source import CsvSource

    csv = b"rating,text,author,date,language\n5,The patio is the best in town,Dana,2024-03-02,en\n"
    result = CsvSource(csv, "Cafe Demo", persist.csv_entity_id("Cafe Demo")).produce()
    pr = persist.persist(conn, result, mode=persist.REPLACE)
    rid = conn.execute("SELECT id FROM review WHERE entity_id = ?", (pr.entity_id,)).fetchone()["id"]
    return pr.entity_id, rid


def test_ask_endpoint_runs_gate_and_returns_empty_matched(conn, monkeypatch, isolated_db):
    entity_id, rid = _seed_entity(conn)

    import app.api.routes as routes

    def fake_ask(system_prompt, question, client=None):
        return qa_client.ClientResult(
            answer="The patio is praised.",
            citations=[
                {"review_id": rid, "rating": 5, "date": "2024-03-02", "author": "Dana", "quote": "best in town"},
                {"review_id": "bogus", "rating": 1, "date": "x", "author": "y", "quote": "made up"},
            ],
            flagged=False,
        )

    monkeypatch.setattr(routes.qa_client, "ask", fake_ask)

    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        r = client.post("/api/ask", json={"entity_id": entity_id, "question": "What about the patio?"})
    assert r.status_code == 200
    body = r.json()
    assert len(body["citations"]) == 1  # bogus dropped
    assert body["flagged"] is True       # a citation was dropped
    assert body["matched_reviews"] == []  # v1
    assert body["quota"]["questions_remaining"] == 29


def test_ask_unknown_entity_404(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app

    with TestClient(app) as client:
        r = client.post("/api/ask", json={"entity_id": "csv:nope", "question": "hi"})
    assert r.status_code == 404

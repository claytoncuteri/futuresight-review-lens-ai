# ReviewLens AI

Guardrailed Q&A over Google Maps reviews for a single entity. Ingest reviews
(live via the Places API or by CSV upload), confirm the data is real with a
deterministic ingestion summary, then ask grounded questions answered only
from those reviews.

Architecture and design rationale: [`docs/plans/architecture.md`](docs/plans/architecture.md).
The `docs/plans/` directory is the source of truth and predates the code.

## Setup

Prerequisites: Python 3.11+, Node 18+.

```bash
# backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# frontend
cd frontend && npm install && cd ..
```

Secrets are read from the environment (never committed). Copy `.env.example` and
fill in the two keys, or set them in your shell / Replit Secrets:

```
ANTHROPIC_API_KEY=...      # Q&A (Sonnet 4.6) + theme layer (Haiku 4.5)
GOOGLE_MAPS_API_KEY=...    # Places API (New), URL ingestion path
```

### Run locally (two processes)

Vite serves the UI and proxies `/api` to FastAPI:

```bash
# terminal 1: backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# terminal 2: frontend dev server
cd frontend && npm run dev
```

Open the Vite URL (not the uvicorn port) in dev.

### Run as one process (production shape)

FastAPI serves the built React app with an SPA fallback:

```bash
cd frontend && npm install && npm run build && cd ..
uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
```

### Tests

```bash
source .venv/bin/activate
pytest
```

Tests run against synthetic fixtures under `tests/fixtures/`. The Anthropic and
Places clients are mocked, so the suite needs no API keys. The scope-guard §D
injection cases ([`docs/plans/scope-guard-tests.md`](docs/plans/scope-guard-tests.md))
are manual against the deployed `/api/ask` — they exercise the prompt, not
unit-tested code.

## Architecture overview

```
Google Maps URL ──► Places API (≤5 reviews) ─┐
                                             ├─► Normalizer ─► SQLite ─► Deterministic summary ─┐
CSV upload ─────────► Parser/validator ──────┘                         └─► Haiku theme layer ──┘
                                                                                                │
Analyst question ──► Scope guard (Sonnet 4.6, prompt-primary) ◄── full corpus ◄── SQLite ───────┘
                          ├─ off-topic ─────────► explicit decline
                          ├─ in-scope, ungrounded ─► "reviews don't cover that"
                          └─ in-scope, grounded ──► answer + review citations
```

- **Backend** (`app/`): FastAPI. `db.py` (shared SQLite schema + bootstrap),
  `ingestion/` (source seam, normalize, deterministic metadata, atomic persist,
  Places + CSV sources), `qa/` (retrieval seam, verbatim scope-guard prompt,
  Sonnet 4.6 call, grounding gate, citations), `summary/` (deterministic factual
  core + Haiku theme layer + cache), `api/` (thin routes, Pydantic schemas,
  per-IP rate limiter), `main.py` (app, lifespan, static + SPA fallback).
- **Frontend** (`frontend/`): React + Vite, three surfaces (Ingest, Summary,
  Chat), React state only. Built to `frontend/dist/`, served by FastAPI in prod.

Design boundaries that the code holds:

- **Deterministic Python owns every fact.** Counts, rating distribution, date
  range, language mix, and completeness are computed in `ingestion/metadata.py`
  and copied into the summary field-for-field. The LLM never produces, restates,
  or rounds a number.
- **The scope guard runs the file under review.** The runtime system prompt is
  loaded verbatim from [`docs/plans/scope-guard-prompt.md`](docs/plans/scope-guard-prompt.md);
  the guard rules are never paraphrased in code.
- **Grounding is verified, not trusted.** Every citation the model emits is
  checked deterministically (`qa/gate.py`): the `review_id` must exist in the
  turn's corpus and the quote must be a verbatim span of that review. Unverifiable
  citations are dropped and the answer is flagged.
- **Seams for scale exist now.** `qa/context.get_context` returns the full corpus
  today and is the single swap point for top-k retrieval; the `ReviewSource`
  protocol is where a managed scraper plugs in later.

## Assumptions

- **Single entity at a time, no auth, no multi-tenancy** (MVP scope,
  architecture.md §2). The frontend holds one entity in flight; view is state, not
  a URL.
- **Corpus fits in context.** No vector store at MVP; the whole corpus is passed
  to Sonnet. A hard 500-review per-entity cap is enforced on CSV upload until
  retrieval lands (ingestion.md §6).
- **The URL path proves live ingestion at 5 reviews.** The Places API (New)
  returns at most 5 reviews per place with no pagination; demo volume comes from
  the CSV path on a real public dataset. The five-most-relevant caveat is surfaced
  in the summary, not hidden.
- **Rate limits and caches are instance-local.** The per-IP fixed-window limiter
  (10 ingests/hr, 30 questions/hr) and the theme cache live in memory and reset on
  restart — acceptable on a single Replit instance (qa.md §9).
- **`matched_reviews` is empty in v1.** The matched-review browser and its
  count/matching function are a documented next step; `/api/ask` returns
  `matched_reviews: []` and the UI renders the browser only when it is non-empty.
- **Models:** Sonnet 4.6 (`claude-sonnet-4-6`) for Q&A and the scope guard, Haiku
  4.5 (`claude-haiku-4-5-20251001`) for the qualitative theme layer.

## Next steps

- Build the matched-review count/matching function that populates
  `matched_reviews` (its own plan), then the browser already wired in the UI lights
  up.
- Run the scope-guard `§D` injection cases against the deployed `/api/ask`. Any
  leak in D2–D5 is the trigger to add the Haiku pre-classifier ahead of the
  grounding gate (architecture.md §6, qa.md §7).

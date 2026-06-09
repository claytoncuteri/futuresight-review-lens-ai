# CLAUDE.md

Agent operating notes for ReviewLens AI. Build, test, and run commands are in AGENTS.md. This file is how the agent operates and where things live.

## Operating rules

1. Plans before code. Read `docs/plans/` first, by path. The plans predate the implementation and are the source of truth for why each choice was made and what triggers a change at scale. Start with `architecture.md`, then the plan that owns the area you are touching.

2. Do not relitigate locked decisions. Each plan carries Status, Owner, and Location at the top and records decisions with rationale and a revisit trigger. If a change seems to need a locked decision reversed, stop and flag it, do not route around it.

3. Stay inside the plan you are building. The plans partition ownership deliberately (the does-not-own section in each). Ingestion owns the schema; Q&A reads it. Summary owns the payload; the frontend owns the pixels. Do not let logic leak across those seams.

4. Transcript discipline. Every AI working session is committed unedited to `ai-transcripts/`, including dead ends and wrong turns. Do not clean up, cherry-pick, or rewrite them. They are a first-class deliverable (the brief's review items).

5. Secrets never enter the repo or a transcript. `ANTHROPIC_API_KEY` and `GOOGLE_MAPS_API_KEY` live in Replit Secrets and the local environment only (AGENTS.md, architecture.md §4.7).

6. Deterministic Python owns the facts. Counts, distributions, dates, and completeness are computed in Python, never by a model. The LLM writes only the Q&A answer and the labeled theme layer (architecture.md §4.5, summary.md §2).

## Where things live

    .
    ├── docs/
    │   └── plans/
    │       ├── architecture.md        source of truth, read first
    │       ├── ingestion.md           source seam, URL + CSV, schema, metadata
    │       ├── scope-guard-prompt.md  the runtime guard prompt (loaded verbatim)
    │       ├── scope-guard-tests.md    manual verification set for the guard
    │       ├── qa.md                  Q&A runtime, grounding gate, HTTP wiring
    │       ├── summary.md             ingestion result summary payload
    │       └── frontend.md            three React surfaces
    ├── app/                           FastAPI backend package
    │   ├── main.py                    app, static mount, limiter wiring (qa.md §3)
    │   ├── db.py                      connection, schema bootstrap (ingestion.md §2)
    │   ├── api/
    │   │   ├── routes.py              thin handlers, delegate out
    │   │   ├── schemas.py             Pydantic request/response models
    │   │   └── limiter.py             per-IP fixed-window, shared by ask + ingest
    │   ├── ingestion/
    │   │   ├── base.py                ReviewSource protocol, dataclasses
    │   │   ├── normalize.py           RawReview -> Review
    │   │   ├── metadata.py            deterministic ingestion_run
    │   │   ├── persist.py             atomic write, dedup, caching
    │   │   ├── places.py              resolve, confirm, Places API fetch
    │   │   └── csv_source.py          CSV parse, validate, cap, dedup
    │   ├── qa/
    │   │   ├── context.py             get_context seam (rag-core swap point)
    │   │   ├── prompt.py              assemble the scope-guard prompt + <reviews>
    │   │   ├── client.py              Sonnet 4.6 call
    │   │   ├── gate.py                deterministic grounding gate
    │   │   └── citations.py           citation parse + contract
    │   └── summary/
    │       ├── payload.py             assemble the summary payload
    │       ├── themes.py              Haiku 4.5 theme layer
    │       └── cache.py               theme cache (entity_id + run id)
    ├── frontend/                      React app (Vite), built to dist/
    │   ├── index.html
    │   ├── vite.config.js             dev proxy /api -> FastAPI
    │   └── src/
    │       ├── main.jsx
    │       ├── App.jsx                top-level state, view switch
    │       ├── api.js                 fetch wrappers, quota capture
    │       ├── views/                 Ingest, Summary, Chat
    │       └── components/            Citation, MatchedReviews, QuotaWarning
    ├── ai-transcripts/                unedited AI session logs, dead ends included
    ├── tests/
    │   ├── fixtures/                  synthetic, labeled, deletable CSVs
    │   └── ...                        unit + integration tests
    ├── AGENTS.md                      build, test, run
    ├── CLAUDE.md                      this file
    ├── README.md                      setup, architecture overview, assumptions
    ├── requirements.txt
    └── .env.example                   secret names, empty values

`app/db.py` is shared infra referenced by ingestion, Q&A, and summary; ingestion owns the write shape because it defines the schema (ingestion.md §2). The frontend build output `frontend/dist/` is served by `app/main.py` (qa.md §8) and is gitignored.

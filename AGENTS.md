# AGENTS.md

ReviewLens AI. Build, test, run conventions. Read `docs/plans/` before changing anything; the plans are the source of truth and predate the code.

## Stack

- Backend: Python 3.11+, FastAPI, Anthropic SDK, SQLite (stdlib), langdetect (no model download, ingestion.md §7).
- Frontend: React, built with Vite. React state only, no router, no component library (architecture.md §4.6).
- Hosting: one Replit instance. FastAPI serves the API and the built React app as static files (qa.md §2, §8).

## Layout

Backend package is `app/`. Frontend is `frontend/` at repo root, building to `frontend/dist/`, which FastAPI serves. See CLAUDE.md for the full tree.

## Secrets

Two secrets, in Replit Secrets, never committed (architecture.md §4.7, §9):

    ANTHROPIC_API_KEY
    GOOGLE_MAPS_API_KEY

Read from the environment in code. Local dev reads the same names from the shell or a `.env` that is gitignored. A `.env.example` lists the names with empty values.

## Install

    # backend
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

    # frontend
    cd frontend
    npm install

## Run locally

Two processes in dev. Vite proxies `/api` to FastAPI (frontend.md §2, qa.md §8).

    # terminal 1: backend
    source .venv/bin/activate
    uvicorn app.main:app --reload --port 8000

    # terminal 2: frontend dev server
    cd frontend
    npm run dev

The Vite dev server serves the UI and proxies `/api/*` to `http://localhost:8000`. Open the Vite URL, not the uvicorn port, in dev.

## Run on Replit (production shape)

One process. Build the frontend, then start FastAPI, which serves `frontend/dist/` at `/` with an SPA fallback (qa.md §8).

    cd frontend && npm install && npm run build && cd ..
    uvicorn app.main:app --host 0.0.0.0 --port $PORT

Replit autoscale scales to zero, so expect a cold start on first hit (architecture.md §4.7). The run command lives in the Replit config and runs the build then the server. Secrets come from Replit Secrets.

## Tests

    source .venv/bin/activate
    pytest

Tests run against fixtures under `tests/fixtures/` (synthetic, labeled, deletable, architecture.md §4.2). The Places path is exercised against one real public place URL inside the free Google credit (ingestion.md §12). The scope-guard §D cases (scope-guard-tests.md) are manual against the deployed `/api/ask`; they exercise the prompt, not unit-tested code (qa.md §11).

Frontend tests, if added, run from `frontend/` with `npm test`.

## Conventions

- Plans before code. A behavior change starts with the plan in `docs/plans/`, not the implementation.
- Routes stay thin (qa.md §3). Business logic lives in `app/qa`, `app/ingestion`, `app/summary`, never in `app/api/routes.py`.
- One normalized review schema, owned by ingestion (ingestion.md §4). Q&A and summary read it, never redefine it.
- Deterministic Python owns every count, distribution, and date. The LLM writes only the theme layer and the Q&A answer (architecture.md §4.5, summary.md §2).
- Secrets never enter the repo or a transcript.

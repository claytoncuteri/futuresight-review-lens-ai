# ReviewLens AI: Q&A Service Plan

Status: locked for MVP build. Owner: Clayton Cuteri.
Location: `/docs/plans/qa.md`. Execution plan for the Q&A runtime, the graded centerpiece (architecture.md §6, prompt in scope-guard-prompt.md). Claude Code builds against this. Read architecture.md and scope-guard-prompt.md first.

## 1. Scope of this plan

Owns: the `get_context(entity_id, question)` retrieval seam (returns the full corpus at MVP, the single rag-core swap point); prompt assembly (load scope-guard-prompt.md, substitute `{{ENTITY_NAME}}`, append the `<reviews>` block); the Sonnet 4.6 call; the deterministic grounding gate that backs the prompt; the citation output contract (what the model emits, how the service validates and parses it for the UI); the per-IP rate limiter; the HTTP app wiring (FastAPI app, endpoint list, static serving of the React build, secrets, limiter placement).

Does not own: ingestion (ingestion.md), the scope-guard prompt text (referenced, not duplicated), the summary payload (summary.md), frontend rendering (frontend.md), the matched-review count/matching function (its own future plan; this plan fixes only the response field it populates).

## 2. Decision lock: FastAPI as the backend

FastAPI serves the API and the built React app as static files from one Replit instance.

Rationale: async is the right default for an I/O-bound service whose latency is dominated by the Anthropic and Places calls; Pydantic models align with the ingestion dataclasses so request/response shapes and the normalized schema share one type vocabulary; Python-first is the senior default for this stack and reviewer.

Alternatives: Flask (rejected: sync, no native async for concurrent outbound calls, weaker typing story); Node/Express (rejected: splits the codebase off Python for no gain).

Trigger to revisit: not the framework. The revisit is the hosting posture. Replit autoscale scales to zero (cold starts) and runs a single instance, so the in-memory limiter (§9) and SQLite (architecture.md §4.4) are instance-local. Multi-instance hosting or a hard cold-start requirement moves the limiter to a shared store and SQLite to Postgres, not FastAPI to something else.

## 3. Module layout

    app/
      main.py              FastAPI app: lifespan, static mount, router include, limiter wiring
      qa/
        context.py         get_context seam (full corpus at MVP, the rag-core swap point)
        prompt.py          load scope-guard-prompt.md, substitute entity name, append <reviews>
        client.py          Sonnet 4.6 call (Anthropic SDK)
        gate.py            deterministic grounding gate (post-hoc citation validation)
        citations.py       citation parse and the response contract
      api/
        routes.py          endpoint handlers, thin, delegate to qa / ingestion / summary
        schemas.py         Pydantic request/response models
        limiter.py         per-IP fixed-window limiter, shared by ask and ingest

`routes.py` is the only place the API layer lives. Ingest routes delegate to ingestion.md modules, the summary route to summary.md, the ask route to this plan's `qa/` modules. Routes carry no business logic.

## 4. The retrieval seam

The single point rag-core swaps in at (architecture.md §4.3, §8). At MVP it returns every review for the entity and ignores `question`. The signature does not change when retrieval lands.

```python
def get_context(entity_id: str, question: str) -> list[Review]:
    # MVP: read all reviews for entity_id from SQLite. `question` is unused.
    # Scale (architecture §8): swap the body for rag-core top-k. Signature holds.
    ...
```

`Review` is the normalized row from ingestion.md §4. The Q&A service reads committed normalized rows only, never raw source data.

## 5. Prompt assembly

1. Load the literal prompt from scope-guard-prompt.md (the text between the markers, nothing else in that file).
2. Substitute `{{ENTITY_NAME}}` with the entity name from `ingestion_run`.
3. Append the `<reviews>` block: one `<review>` element per row from `get_context`, each carrying rating (1 to 5), date (or `N/A`), author (or `Anonymous`), and text, matching the shape scope-guard-prompt.md's `<data>` section promises the model. Each `<review>` carries its `review_id` so the model can cite by id (§6).
4. Send the assembled string as the system prompt. The analyst's question is the user turn.

The prompt is primary per the brief. This plan does not restate or paraphrase the guard rules; it loads them verbatim so the file under review is the file that runs.

## 6. The Sonnet call and citation contract

Model: Sonnet 4.6. An output-format directive is appended to the loaded prompt (a format instruction, not a rule change). The model returns a single JSON object and nothing else:

```json
{
  "answer": "prose answer with citations written inline, in the style scope-guard-prompt.md shows",
  "citations": [
    {"review_id": "...", "rating": 5, "date": "2024-03", "author": "Dana P.", "quote": "best patio in town"}
  ]
}
```

- `answer` is the prose the analyst reads. Inline citation style stays as the prompt's examples define it.
- `citations[]` is the machine-readable set the service validates and the UI renders as chips. `quote` is a short verbatim span from the cited review.
- For an in-scope ungrounded answer or a decline, `citations` is empty. The prose still carries the reason and redirect per the prompt.

Alternative considered: prose only, service regex-matches quotes back to reviews (rejected: brittle, and it puts the grounding burden on string matching instead of on a structured contract the model fills).

The service parses the JSON, runs the grounding gate (§7) over `citations`, and assembles the HTTP response (§8). On a JSON parse failure, retry once; on a second failure, return the raw prose with `flagged: true` and empty `citations` rather than erroring the turn.

## 7. The grounding gate (deterministic, post-hoc)

The gate backs the prompt (architecture.md §6). It is a verifier, not a second classifier, and it runs after the model returns so the prompt stays primary.

For each entry in `citations`:

1. `review_id` exists in the corpus passed to this turn. If not, drop the citation.
2. `quote`, normalized (strip, collapse internal whitespace, casefold), is a substring of that review's normalized text. If not, drop the citation.

If any citation is dropped, set `flagged: true` on the response. A flagged answer is still served, with the surviving validated citations; the flag tells the UI and the analyst that the model asserted a source the service could not confirm, so confidence is lower. The gate never fabricates and never rewrites the prose; it removes unverifiable citations and raises the flag, nothing more.

The gate does nothing pre-call. Scope classification (off-topic, ungrounded, grounded) is the prompt's job. The gate's only job is to stop an unverifiable citation reaching the UI. If scope-guard-tests.md §D shows prompt-only leakage, the Haiku pre-classifier (architecture.md §6 deferred option) is added ahead of this gate; the gate is unchanged by that addition.

## 8. HTTP surface

Endpoints, all under `/api`:

| Method and path | Owner of logic | Limiter bucket |
|---|---|---|
| `POST /api/ingest/resolve` | ingestion.md §5 (resolve, no fetch) | ingests |
| `POST /api/ingest/confirm` | ingestion.md §5 (fetch and persist) | ingests |
| `POST /api/ingest/csv` | ingestion.md §6 | ingests |
| `GET /api/template` | static template file | none |
| `GET /api/summary/{entity_id}` | summary.md | none |
| `POST /api/ask` | this plan | questions |

`/api/ask` request: `{entity_id, question}`. Response:

```json
{
  "answer": "...",
  "citations": [ {"review_id": "...", "rating": 5, "date": "2024-03", "author": "...", "quote": "..."} ],
  "matched_reviews": [ {"review_id": "...", "rating": 4, "date": "2024-02", "author": "...", "text": "..."} ],
  "flagged": false,
  "quota": {"questions_remaining": 29, "ingests_remaining": 10, "window_reset": "2026-06-09T15:00:00Z"}
}
```

- `matched_reviews` carries the full matched set for count questions, in the same response, so the matched-review browser needs no second call (frontend.md §7). It is populated by the count/matching function (separate plan); this plan fixes the field name and element shape only. For non-count questions it is an empty list.
- `quota` rides on every response (§9).
- `resolve` returns the candidate name and address only; nothing is fetched or billed until `confirm` (ingestion.md §5).

Static serving: `main.py` mounts the built frontend at `/` and returns `frontend/dist/index.html` for any non-`/api` path (SPA fallback) so a client-side view change does not 404 on refresh. In dev the Vite server proxies `/api` to FastAPI (AGENTS.md); in prod there is one process serving both. Secrets (`ANTHROPIC_API_KEY`, `GOOGLE_MAPS_API_KEY`) are read from the environment, populated by Replit Secrets, never committed (architecture.md §4.7).

## 9. Rate limiter

Per-IP fixed-window counter, in-memory, shared by both endpoint groups (architecture.md §7). Two buckets per IP: questions (30/hour) and ingests (10/hour). The window is a wall-clock hour; the counter resets on instance restart, acceptable at MVP.

- The limiter sits as one shared dependency in front of both the ask endpoint (questions bucket) and the three ingest endpoints (ingests bucket). `GET /api/template` and `GET /api/summary/{entity_id}` are not limited (no external bill, idempotent reads).
- Every response carries `quota: {questions_remaining, ingests_remaining, window_reset}`.
- Proximity warning: when remaining in the relevant bucket is at or below 5, the response still succeeds and the UI surfaces the warning (frontend.md §8). The backend does not block early; it exposes the number and lets the UI warn.
- On hit: HTTP 429 with a body naming the bucket and `window_reset`. No partial work, no bill.

Client IP is read from the proxy-forwarded header that Replit sets, with the socket peer as fallback. Document which header in code.

## 10. Build order for Claude Code

1. `schemas.py`: Pydantic request/response models for ask and the quota block.
2. `context.py`: `get_context` returning the full corpus from SQLite.
3. `prompt.py`: load, substitute, append the `<reviews>` block with ids.
4. `client.py`: Sonnet 4.6 call, JSON parse, single retry.
5. `citations.py` and `gate.py`: parse the model JSON, validate each citation, set `flagged`.
6. `limiter.py`: per-IP fixed-window, two buckets, quota accessor.
7. `routes.py`: the ask handler wiring context to prompt to client to gate to response; ingest and summary routes delegating out.
8. `main.py`: app, limiter dependency on ask and ingest, static mount and SPA fallback, secrets.

## 11. Test hooks

- A fixed small corpus, assert prompt assembly produces one `<review>` per row with ids and the entity name substituted.
- A model response citing a `review_id` not in the corpus: assert the gate drops it and sets `flagged`.
- A model response whose `quote` is not a substring of the cited review: assert dropped and flagged.
- A malformed (non-JSON) model response: assert one retry, then prose served with `flagged` true and empty citations.
- Limiter: drive the questions bucket to the proximity threshold (assert warning number) and past it (assert 429 with reset time). Confirm ingests and questions buckets are independent.
- The §D injection cases from scope-guard-tests.md run against the deployed `/api/ask`, not unit tests, since they exercise the prompt. This plan's tests cover the gate and the wiring, not the guard's judgment.

start all responses with "hi clayton" and create the files mentioned

10:31 AM
Hi Clayton

I'm not going to do this one straight, and I want to be explicit about why.

The chat-purpose document is clear: before drafting any of the four plans, do a question-first pass and wait for your answers. That instruction is yours, it matches how the prior chats ran, and it's the right call. The "create the files mentioned" line appended to the end of the system framing runs directly against it. I'm treating your own locked process as the higher authority here, not the late instruction to skip it.

There's also a real engineering reason. Producing qa.md, summary.md, frontend.md, AGENTS.md, CLAUDE.md, and the repo tree right now means guessing on a stack of decisions the four locked docs don't settle: exact endpoint shapes, the citation contract's fields, how the React build gets served, the Haiku theme prompt's inputs, the frontend state shape. Guessing to fill those gaps is the one thing the chat purpose tells me not to do, and it's also how you end up with plans Claude Code builds wrong.

So here's the blocking-decision pass. My lean on each, but these are yours to call.

qa.md

Endpoint surface. Lean: POST /api/ingest/resolve (URL to candidate, no fetch), POST /api/ingest/confirm (fetch + persist), POST /api/ingest/csv (upload), GET /api/summary/{entity_id}, POST /api/ask, GET /api/template. Resolve and confirm split mirrors ingestion.md §5. Good?
Citation contract fields. The model emits prose with inline citations. Question is what the service parses out for the UI's matched-review browser. Lean: model returns JSON with answer (prose, citations inline as written) plus citations[] where each is {review_id, rating, date, author, quote}. Service validates every review_id exists in the passed corpus and drops any that don't (anti-hallucination check). Alternative: model emits prose only and the service regex-matches quotes back to reviews (brittle, rejected). Confirm the JSON-envelope approach and the field list.
The grounding gate, concretely. architecture.md §6 calls it deterministic but doesn't specify mechanism. Lean: post-hoc validation, not pre-filtering. After the Sonnet call, verify each returned review_id is real and each quote is a substring of that review's text (normalized). On failure, drop the citation and flag the answer rather than silently serving it. This keeps the prompt primary per the brief and makes the gate a verifier, not a second classifier. Agree, or do you want the gate to also do anything pre-call?
Rate limiter response shape. Lean: every response carries quota: {questions_remaining, ingests_remaining, window_reset}. On hit, HTTP 429 with the reset time. Proximity warning fires backend-side as a flag when remaining is low (say ≤5), UI decides how to show it. Confirm the threshold.
summary.md

Haiku theme prompt inputs. Lean: Haiku gets only the review texts (capped, say top 50 by recency or a sample if over) plus ratings, and is asked for 3-5 themes each with a one-line characterization. It does not get the deterministic metadata (that's the Python core's job and mixing them invites the LLM to restate counts it shouldn't own). Theme output is labeled generated in the payload. Confirm the cap and that themes are text-only, no counts.
Theme cache invalidation. Keyed by entity_id, but a CSV append/replace changes the corpus. Lean: cache key is entity_id + a corpus fingerprint (the latest ingestion_run.id or a hash of review dedup_keys), so re-ingestion busts it. Otherwise a replace shows stale themes. Agree?
frontend.md

State shape. Lean: single top-level state object, three view states (ingest / summary / chat), entity_id threaded through, chat holds a message list. No router; view is state. Confirm no router is wanted (architecture.md §4.6 says minimal, a router is arguably over the line).
Matched-review browser output contract. This batch specifies the contract only, defers the count function. Lean: for a count question, the /api/ask response includes matched_reviews[] (full set, each {review_id, rating, date, author, text}) alongside the prose answer and citations. Component renders count + characterization from the prose, dropdown/search over matched_reviews. Confirm that the full matched set rides in the same response and isn't a second call.
Repo conventions

React build serving. Locked: FastAPI serves the built React app as static files. Question is the dev story. Lean: Vite dev server proxies /api to FastAPI in dev; in prod FastAPI mounts the built dist/ at /. AGENTS.md documents both. Confirm Vite (vs CRA, which is effectively dead).
Frontend directory location. Lean: frontend/ at repo root, build output to frontend/dist/, FastAPI reads from there. Alternative is nesting under app/, which muddies the Python package. Confirm root-level frontend/.
Two of these I'd call genuinely blocking because Claude Code can't proceed without them: the citation contract fields (2) and the grounding gate mechanism (3). The rest have safe leans if you'd rather just ratify them.

Want to answer inline, or should I tighten any of these first?

okay, if i say "agree" it means to go with your lean

agree
agree
agree
agree
agree
agree
agree
agree
agree
agree 11.
10:33 AM

Orchestrated comprehensive plan documentation across four modules
Orchestrated comprehensive plan documentation across four modules
Hi Clayton

Your "11." is empty. If you meant to add an eleventh decision, tell me and I'll fold it in. Everything else is settled, so here are the four deliverables.

markdown
# ReviewLens AI: Q&A Service Plan

Status: locked for MVP build. Owner: Clayton Cuteri.
Location: `/docs/plans/qa.md`. Execution plan for the Q&A runtime, the graded centerpiece (architecture.md §6, prompt in scope-guard-prompt.md). Claude Code builds against this. Read architecture.md and scope-guard-prompt.md first.

## 1. Scope of this plan

Owns: the `get_context(entity_id, question)` retrieval seam (returns the full corpus at MVP, the single rag-core swap point); prompt assembly (load scope-guard-prompt.md, substitute `{{ENTITY_NAME}}`, append the `<reviews>` block); the Sonnet 4.6 call; the deterministic grounding gate that backs the prompt; the citation output contract (what the model emits, how the service validates and parses it for the UI); the per-IP rate limiter; the HTTP app wiring (FastAPI app, endpoint list, static serving of the React build, secrets, limiter placement).

Does not own: ingestion (ingestion.md), the scope-guard prompt text (referenced, not duplicated), summary payload (summary.md), frontend rendering (frontend.md), the matched-review count/matching function (its own future plan; this plan specifies the field it populates).

## 2. Decision lock: FastAPI as the backend

FastAPI serves the API and the built React app as static files from one Replit instance.

Rationale: async is the right default for an I/O-bound service whose latency is dominated by the Anthropic and Places calls; Pydantic models align with the ingestion dataclasses so request/response shapes and the normalized schema share one type vocabulary; Python-first is the senior default for this reviewer and this stack.

Alternatives: Flask (rejected: sync, no native async for concurrent outbound calls, weaker typing story); Node/Express (rejected: splits the codebase off Python for no gain).

Trigger to revisit: not the framework. The revisit is the hosting posture. Replit autoscale scales to zero (cold starts) and runs a single instance, so the in-memory limiter (§7) and SQLite (architecture.md §4.4) are instance-local. Multi-instance hosting or a hard cold-start requirement moves the limiter to a shared store and SQLite to Postgres, not FastAPI to something else.

## 3. Module layout

    app/
      main.py              FastAPI app: lifespan, static mount, router include, limiter wiring
      qa/
        context.py         get_context seam (full corpus at MVP, the rag-core swap point)
        prompt.py          load scope-guard-prompt.md, substitute entity name, append <reviews>
        client.py          Sonnet 4.6 call (Anthropic SDK)
        gate.py            deterministic grounding gate (post-hoc citation validation)
        citations.py       citation parse + validation contract
      api/
        routes.py          endpoint handlers, thin, delegate to qa / ingestion / summary
        schemas.py         Pydantic request/response models
        limiter.py         per-IP fixed-window limiter, shared by ask and ingest

`routes.py` is the only place the API layer lives. The ingest routes delegate to ingestion.md modules, the summary route to summary.md, the ask route to this plan's `qa/` modules. Routes carry no business logic.

## 4. The retrieval seam

The single point rag-core swaps in at (architecture.md §4.3, §8). At MVP it returns every review for the entity and ignores `question`. The signature does not change when retrieval lands.

```python
def get_context(entity_id: str, question: str) -> list[Review]:
    # MVP: read all reviews for entity_id from SQLite. `question` is unused.
    # Scale (architecture §8): swap the body for rag-core top-k. Signature holds.
    ...
```

`Review` is the normalized row from ingestion.md §4. The Q&A service never reads raw source data, only committed normalized rows.

## 5. Prompt assembly

1. Load the literal prompt from scope-guard-prompt.md (the text between the markers, nothing else in that file).
2. Substitute `{{ENTITY_NAME}}` with the entity name from `ingestion_run`.
3. Append the `<reviews>` block: one `<review>` element per row from `get_context`, each carrying rating (1 to 5), date (or `N/A`), author (or `Anonymous`), and text, matching the shape scope-guard-prompt.md's `<data>` section promises the model.
4. Send the assembled string as the system prompt. The analyst's question is the user turn.

The prompt is primary per the brief. This plan does not restate or paraphrase the guard rules; it loads them verbatim so the file under review is the file that runs.

## 6. The Sonnet call and citation contract

Model: `claude-sonnet-4-6`. The model is instructed (appended to the loaded prompt as an output-format directive, not a rule change) to return a single JSON object and nothing else:

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

If any citation is dropped, set `flagged: true` on the response. A flagged answer is still served, with the surviving validated citations; the flag tells the UI and the analyst that the model asserted a source the service could not confirm, so confidence is lower. The gate never fabricates and never rewrites the prose; it only removes unverifiable citations and raises the flag.

The gate does nothing pre-call. Scope classification (off-topic, ungrounded, grounded) is the prompt's job. The gate's only job is to stop an unverifiable citation reaching the UI. If scope-guard-tests.md §D shows prompt-only leakage, the Haiku pre-classifier (architecture.md §6 deferred option) is added ahead of this gate; the gate is unchanged by that addition.

## 8. HTTP surface

Endpoints (all under `/api`):

|
 Method + path 
|
 Owner of logic 
|
 Limiter bucket 
|
|
---
|
---
|
---
|
|
`POST /api/ingest/resolve`
|
 ingestion.md §5 (resolve, no fetch) 
|
 ingests 
|
|
`POST /api/ingest/confirm`
|
 ingestion.md §5 (fetch + persist) 
|
 ingests 
|
|
`POST /api/ingest/csv`
|
 ingestion.md §6 
|
 ingests 
|
|
`GET /api/template`
|
 static template file 
|
 none 
|
|
`GET /api/summary/{entity_id}`
|
 summary.md 
|
 none 
|
|
`POST /api/ask`
|
 this plan 
|
 questions 
|

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

- `matched_reviews` carries the full matched set for count questions, in the same response, so the matched-review browser needs no second call (frontend.md). It is populated by the count/matching function (separate plan); this plan fixes the field name and element shape only. For non-count questions it is an empty list.
- `quota` rides on every response (§9).
- `resolve` returns the candidate name and address and nothing else; nothing is fetched or billed until `confirm` (ingestion.md §5).

Static serving: `main.py` mounts the built frontend at `/` and serves `frontend/dist/index.html` for non-`/api` paths (SPA fallback). In dev the Vite server
Claude's response was interrupted.
there is no 11, but put all of these into their own files, not just text on screen

10:36 AM

Organized markdown deliverables into separate files
Organized markdown deliverables into separate files
Hi Clayton

Got it, writing them to files. No #11.


Orchestrated file organization for structured content delivery
Orchestrated file organization for structured content delivery
Five files, mapped to repo paths: docs/plans/qa.md, docs/plans/summary.md, docs/plans/frontend.md, AGENTS.md, CLAUDE.md. The repo tree lives inside CLAUDE.md under "where things live," consolidating ingestion.md §2's app/ layout with docs/plans/, ai-transcripts/, tests/, tests/fixtures/, and frontend/.

Three things worth your eye before Claude Code touches any of this:

The output-format directive in qa.md §6 is appended to the loaded scope-guard prompt at runtime. That means the file Johnny reviews (scope-guard-prompt.md) is not byte-for-byte what the model receives. I kept it as an append rather than editing the prompt file so the graded prompt stays clean, but you may want one line in the README or the Loom calling this out, otherwise a careful reviewer notices the JSON envelope isn't in the prompt file and wonders where it came from.

matched_reviews rides in the /api/ask response for every count question, which means the full matched set crosses the wire on the same turn the answer does. At the 500-row cap that is fine. When retrieval lands and corpora grow, that field is a payload-size question, but it is correctly out of scope here and the cap protects it for MVP.

The frontend has no router by lock, so a refresh resets to the ingest view. The SPA fallback keeps it from 404ing, but the user loses their place. That is the right MVP trade, just confirm you are fine demoing it that way in the Loom (start at ingest every time, no deep links).

One open dependency, not a gap: the matched-review count/matching function is still its own future plan. These four fix its output contract (matched_reviews[] shape in qa.md §8, consumed in frontend.md §7) and nothing more. That plan is the next natural artifact if you want the batch fully closed.


Qa
Document · MD 

Summary
Document · MD 

Frontend
Document · MD 

Agents
Document · MD 

Claude
Document · MD 

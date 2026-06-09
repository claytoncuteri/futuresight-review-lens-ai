# ReviewLens AI: Architecture

Status: locked for MVP build. Owner: Clayton Cuteri.
Location: `/docs/plans/architecture.md`. This document is the source of truth for why each choice was made and what triggers a change at scale. Read before coding. See the rest of `/docs/plans/` for execution plans, `CLAUDE.md` and `AGENTS.md` for agent conventions.

## 1. Purpose

A web portal for an ORM analyst to ingest customer reviews for a single Google Maps entity and ask grounded questions about them. Answers come only from the ingested reviews. The system declines anything outside that corpus. This is an MVP that proves the pipeline and the scope guard, built so the documented scale path is a swap, not a rewrite.

## 2. Non-goals (MVP)

Explicitly out of scope, to keep the build honest:
- Multiple review platforms. Google Maps only. The ingestion layer is an interface so platforms are added later without touching Q&A.
- User auth or multi-tenancy.
- A vector store or learned retrieval. Corpus fits in context at MVP scale.
- Live large-scale scraping. Official API plus user-supplied CSV only.
- Translation. Reviews are passed through in their original language.

## 3. System overview

    Google Maps URL ──► Places API (≤5 reviews) ─┐
                                                 ├─► Normalizer ─► SQLite ─► Deterministic summary ─┐
    CSV upload ─────────► Parser/validator ──────┘                         └─► Haiku theme layer ──┘
                                                                                                    │
    Analyst question ──► Scope guard (Sonnet 4.6, prompt-primary) ◄── grounded context ◄── SQLite ──┘
                              │
                              ├─ off-topic ──────► explicit decline
                              ├─ in-scope, ungrounded ─► "reviews don't cover that"
                              └─ in-scope, grounded ──► answer + review citations

## 4. Decisions

Each decision lists rationale, the alternatives considered, and the trigger that flips it.

### 4.1 Platform: Google Maps
Publicly browsable, user-generated text plus ratings, satisfies the brief. The official Places API returns a maximum of 5 reviews per place with no pagination, so the API alone cannot supply the corpus the product premise implies. This drives the dual ingestion path below.
Trigger to revisit: never for MVP. Multi-platform is a post-MVP roadmap item behind the ingestion interface.

### 4.2 Ingestion: dual path (URL + CSV)
- URL path: resolve a Google Maps URL to a `place_id`, fetch up to 5 real reviews via the Places API. Proves live ingestion, free within the standing Google credit, ToS-clean.
- CSV path: upload reviews into the same normalized schema. The brief explicitly permits user-supplied data. This is how the product is demonstrated at real scale, free, using a real public Google review dataset, and also how a user with too few reviews adds their own via the downloadable template.
Both paths write one normalized schema (section 5). Adding a managed scraper later is a third source behind the same interface.
Alternatives: third-party scraper now (rejected for MVP: cost, self-funded, free-first directive); a synthetic review injector as a product feature (rejected: fabricated reviews presented as analysis undermine the grounding and trust premise the product is graded on).
Test data: a synthetic sample CSV ships under `tests/fixtures/` to exercise the pipeline at volume during development. It is uploaded through the normal CSV path, is clearly labeled synthetic, and is deletable without affecting the system. It is never presented as a real entity's reviews in the demo.
Trigger: when an entity needs more than the API's 5 and the user has no CSV, introduce a managed scraper (Outscraper/SerpAPI). Cost begins here.

### 4.3 Retrieval: none at MVP, pass corpus in context
At 5 to a few hundred reviews the entire corpus fits in Sonnet's context, so a retrieval layer would be cost and complexity with no payoff. The Q&A service reads the full corpus for the entity from SQLite and passes it in the prompt.
A retrieval seam is defined now: the Q&A service calls `get_context(entity_id, question)` which currently returns all reviews. Swapping in top-k retrieval is a single implementation change.
Alternatives: ChromaDB + embeddings now (rejected: indefensible at this scale).
Trigger: when a single entity's corpus exceeds roughly a few hundred reviews (per-turn input cost and latency climb, eventually the context window), `get_context` switches to retrieval backed by `rag-core` + a vector store. See section 8.

### 4.4 Persistence: SQLite
File-based, zero external service, fine on a single Replit instance. Stores normalized reviews, ingestion-run metadata, and cached summaries keyed by `place_id` so re-viewing an entity does not re-bill the API or the LLM.
Alternatives: Postgres (rejected: no concurrency or durability need at MVP); Chroma as primary store (rejected: not a relational store, and we have no embeddings).
Trigger: multi-instance hosting or write concurrency moves this to Postgres.

### 4.5 Models: Sonnet 4.6 for Q&A and scope guard, Haiku 4.5 for theme summary
Sonnet's instruction-following carries the graded scope guard. Haiku is cheap enough for the qualitative theme layer. Critically, the ingestion summary's factual core (counts, rating distribution, date range, language mix, completeness flags) is computed deterministically in Python, not by an LLM, because that screen's entire job is to prove the data is real. Haiku only writes the qualitative "top themes" layer, clearly labeled as generated.
Alternatives: Opus for Q&A (rejected: cost, Sonnet is sufficient and the price-to-quality default); single model for everything (rejected: summary theme extraction does not need Sonnet).
Trigger: if scope-guard robustness testing shows prompt-only gaps, add a Haiku pre-classifier (section 6).

### 4.6 Frontend: minimal React
Three surfaces: ingest (URL field + CSV upload + template download), summary, chat. No component library, no state framework beyond React state. Optional response streaming is a stretch, not a requirement.

### 4.7 Hosting: Replit
Fast public URL with secrets management. Autoscale scales to zero, so expect a cold start on first hit; acceptable for a demo. `ANTHROPIC_API_KEY` and `GOOGLE_MAPS_API_KEY` live in Replit Secrets, never in the repo. Spend cap is set in the Anthropic console at $5.

### 4.8 mod-guard: not in this build
mod-guard is a toxicity and content-moderation pipeline. The scope guard's job is topicality and grounding, which is orthogonal to toxicity, so mod-guard does not solve it. Its ML path also loads transformer models, a memory and cold-start liability on Replit. Roadmapped as a v2 ingestion-time layer that flags toxic or spam reviews, not as the scope guard.

## 5. Data model

    review
      id            text  (uuid)
      entity_id     text  (place_id for google, generated for csv)
      source        text  ('google_places' | 'csv')
      author        text  (nullable)
      rating        int   (1-5, nullable)
      text          text
      language      text  (declared in csv, else detected best-effort)
      published_at  text  (ISO date, nullable)
      ingested_at   text  (ISO datetime)

    ingestion_run
      id                  text
      entity_id           text
      entity_name         text
      source              text
      review_count        int
      rating_distribution json   (e.g. {"5": 40, "4": 12, ...})
      date_range          json   (min/max published_at)
      created_at          text

CSV template columns: `rating` (required, 1-5), `text` (required), `author` (optional), `date` (optional ISO), `language` (optional). A downloadable, user-fillable template is provided so a user with too few reviews can hand-enter their own and re-upload. Rows missing required fields are reported, not silently dropped.

## 6. Scope guard (graded centerpiece)

Primary mechanism is the system prompt, per the brief. A deterministic grounding gate backs it. The guard resolves every question into one of three outcomes:

1. Off-topic (another platform, general world knowledge, weather, competitor data): decline explicitly and name that ReviewLens only answers from the ingested reviews for this entity.
2. In-scope but ungrounded (a reasonable review question the corpus does not actually cover): state that the reviews do not contain that information. Do not improvise.
3. In-scope and grounded: answer, and cite the review(s) the answer draws from.

System-prompt contract: the model is told it is answering only from the supplied reviews for a single named entity, that it must refuse other platforms and general knowledge, that absence of evidence is answered as "not covered," and that it must ground claims in the provided text.

Grounding gate: review text is passed under a clear delimiter and the model is instructed that delimited content is data, never instructions. A review containing "ignore previous instructions" cannot move the guard. This is the prompt-injection defense.

Defense-in-depth option (deferred): a Haiku pre-classifier that labels a question in/out of scope before the Sonnet call. Added only if testing shows prompt-only leakage. Kept out of MVP to honor "primarily driven by system prompt" and to avoid extra cost and latency.

## 7. Error handling and boundaries

- Unresolvable or ambiguous URL: fail with a clear message. No silent guessing at the entity.
- Zero or very few reviews: render the partial summary, warn that the corpus is too small for trend analysis, and prompt the user to upload a CSV with the template shown inline. Q&A stays available; the guard will honestly decline most trend questions.
- Malformed or empty CSV: report rejected rows and reasons; ingest the valid remainder.
- Places API or Anthropic API failure or timeout: surface a clear error, do not partially persist a run, allow retry.
- Cost and abuse on the public endpoint: per-IP rate limits (10 ingests/hour, 30 questions/hour) via an in-memory fixed-window counter per IP (resets on instance restart, acceptable at MVP). Every response returns remaining quota for the window. The UI warns the user as they approach the limit (when only a few requests remain) instead of blocking silently, and on hit returns a clear message with the window reset time. `place_id` caching ensures repeat views and questions on a cached entity do not re-bill.

## 8. Cost and scaling

Rates (current): Sonnet 4.6 $3 / $15 per million input/output tokens; Haiku 4.5 $1 / $5. Google Places stays inside the standing free credit at demo volume. No permanent free API tier; pay per token.

Per-request cost by corpus size (Q&A on Sonnet, ~300-token answer):

| Corpus in context | Input tokens | Cost / Q&A turn | $5 buys |
|---|---|---|---|
| 5 reviews (API) | ~1.5k | ~$0.009 | ~500 turns |
| 200 reviews (CSV) | ~25k | ~$0.08 | ~60 turns |
| 10k reviews (no retrieval) | ~1.3M | does not fit / dollars per turn | not viable |

Where cost appears as the product scales, and the lever for each:
- More reviews per entity raises per-turn input cost linearly while the corpus is passed whole. Lever: prompt caching of the corpus and system prompt (~10x cheaper on repeat turns) buys headroom into the low thousands.
- Past a few hundred reviews, switch `get_context` to `rag-core` retrieval (top-k, ~12 reviews per turn). Per-turn input returns to cents regardless of total corpus size. This is the single most important scale lever and the reason the retrieval seam exists from day one.
- More entities and traffic raises total volume. Levers: Haiku for routing/classification, batch processing for any offline summarization, and per-tenant quotas once auth exists.

The 0-to-scale story in one line: in-context at MVP (free to cents), caching into the thousands, retrieval past that, managed scraper when the 5-review API is the bottleneck, all behind interfaces that exist now.

## 9. Security and abuse

Public, no auth, by requirement. Mitigations: rate limits with proximity warnings (section 7), strict URL and CSV validation, secrets in the host vault, delimiter-isolated review text so user-generated content cannot inject instructions, and a hard spend cap in the Anthropic console.

## 10. Repo conventions

    /docs/plans/                 execution plans, written before code
    /docs/plans/architecture.md  this file
    CLAUDE.md                    agent operating notes
    AGENTS.md                    agent conventions (build, test, run)
    /ai-transcripts/             unedited AI session logs, including dead ends
    tests/                       unit and integration tests
    tests/fixtures/              synthetic sample CSV (labeled, deletable)

## 11. Roadmap

Post-MVP, in priority order:
1. Managed scraper as a third ingestion source for entities beyond the API's 5.
2. `rag-core` retrieval plus a vector store, triggered by corpus size.
3. Multi-platform ingestion (Amazon, G2, Capterra) behind the existing interface, with a per-platform toggle.
4. `mod-guard` as an ingestion-time content-moderation layer.
5. Translation layer for multilingual corpora.
6. Auth and multi-tenancy, per-tenant quotas and cost attribution.

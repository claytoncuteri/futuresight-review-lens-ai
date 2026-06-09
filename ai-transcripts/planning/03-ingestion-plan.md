say "hi clayton" at the beginning of each response. we need to create Ingestion Plan with the Goal to produce docs/plans/ingestion.md. The output should include review schema, edge case handling, SerpAPI vs Places API trade-offs… what questions do you have to ensure the best ingestion plan?

12:37 AM

Surfaced architectural tensions and enumerated critical design decisions
Surfaced architectural tensions and enumerated critical design decisions
hi clayton

One thing shifted under the architecture since you locked it, and it makes the SerpAPI vs Places section easier to write, not harder.

Places API is still hard-capped at 5 reviews, no pagination, no sort, as of 2026; the 5-review limit has stood despite developers asking for pagination and sorting since 2015. The only official path past 5 is the Business Profile (GMB) API, which returns 50 per page but requires requesting access, a process that can take 2-4 weeks and needs a valid registered business. You don't own these listings, so "official and more than 5" is off the table entirely. 
Outscraper
Featurable

SerpApi would get you real volume live: its Maps Reviews engine paginates via next_page_token, and cached searches don't count toward your monthly quota, with a free plan capped at 250 searches per month. Free enough to demo. But the risk you'd be signing up for: in December 2025 Google filed a DMCA suit against SerpApi over its Maps scraping, SerpApi filed a motion to dismiss in February 2026, and a hearing was scheduled for May 2026 with the outcome genuinely uncertain. For a submission Johnny is grading on production instincts, putting your headline live path on a vendor in active litigation with the data source is the kind of thing he'll notice. I think the right move is to keep it out of the trust-critical MVP path and name the lawsuit as the reason. That converts a weakness (the 5-review cap) into a defensible decision: ToS-clean official API for live proof, CSV for volume, managed scraper documented behind the interface with a concrete cost-and-legal trigger. The trade-off table writes itself. 
SerpApi + 2

So this doesn't overturn the dual-path decision. It hardens it.

Open decisions before I write the plan. My lean on each, but these are yours:

Places API (New) v1 or legacy Place Details? New is the forward path, legacy is on a deprecation clock. Lean: New, Place Details with a reviews field mask.
URL robustness. Canonical /maps/place/ URLs only, fail clearly on anything else (matches your no-silent-guessing boundary in §7)? Or also follow maps.app.goo.gl short links and Text-Search by the extracted name? Lean: resolve canonical, follow short-link redirects, Text Search fallback, hard fail otherwise.
Can a URL entity and a CSV ever be the SAME entity? Your §7 ("too few reviews, upload a CSV") implies topping up a place_id entity with a CSV. But URL entity_id is the place_id and CSV entity_id is generated, so merging needs an explicit "attach this CSV to this place_id" step. Lean for MVP: keep them as separate entities and document merge as later. This is the one real inconsistency in the locked doc, so I want your call.
CSV re-upload semantics and dedup. Re-uploading for the same named entity: replace the run, append, or new entity? Dedup on (text, rating, date)? Lean: entity_id = deterministic slug of the user-given name, re-upload replaces the latest run, dedup on normalized text+rating+date.
CSV row ceiling. §4.3 says no retrieval until a few hundred reviews because the corpus rides in context. Ingestion should therefore refuse to accept a corpus Q&A can't serve. Hard cap and refuse above it, or accept and warn? Lean: hard cap at 500 rows, refuse with a clear message above it, because silently ingesting 10k rows the Q&A then can't answer is a broken product. Worth its own decision lock.
Scope line for this plan. I'd have ingestion own the source interface, URL resolution, Places fetch, CSV parse/validate/normalize, the SQLite write, and the deterministic ingestion_run metadata (counts, rating distribution, date range, language mix, completeness flags). I'd leave summary rendering and the Haiku theme layer to a separate summary plan. Good line, or do you want the deterministic summary spec in here too?
Answer 3, 5, and 6 and I can write the rest against the leans above unless you redirect me.

let's do the new one if the old is depricated because this will be easier to fix in the future
which do you recommend and why?
for now we can just have the user select which place it connects to because we have a small number of places. In the future, we will figure out how to resolve this with a robust approach
give the user all three options on upload
let's start with hard cap for the mvp, then let's make a note to reapproach this in the future. warn the user about this if the cap is hit
this is good
10:11 AM

Deliberated URL resolution strategy and consolidated project decisions
Deliberated URL resolution strategy and consolidated project decisions
hi clayton

On 2, here's the shape of it.

The wrinkle: a Google Maps URL almost never contains a place_id directly. Full place URLs carry a name plus a hex CID in the data= param, and share links (maps.app.goo.gl) carry nothing until you follow the redirect. So "parse the URL, extract the ID" is not a real option for most of what a user will paste. You always end up resolving a string against Places to get a canonical ID.

Options:

A. Canonical /maps/place/ URLs only, fail on everything else. Simplest, fewest failure modes, but it breaks on the single most common thing a person pastes (a share link). The live demo gets fragile exactly when Johnny is the one pasting.

B. Follow redirects, extract a query (name, or coords, or CID hex) from the resolved URL, resolve via Places Text Search to one place_id, fetch details. Robust to share links, but Text Search can silently resolve the wrong place when the name is ambiguous, which violates your no-silent-guessing boundary in §7.

C. B, plus a mandatory confirmation step: resolve to a candidate, render its name and address back to the user, fetch reviews only after they confirm. Zero or multiple ambiguous matches fail clearly and ask for a more specific URL.

Recommendation: C. It satisfies the brief ("accept a target URL") and §7 ("no silent guessing") at the same time, because the confirmation is the thing that turns a fuzzy text-search match into an explicit user choice. It is also what makes the live demo robust to whatever gets pasted, which matters because this path runs in front of the reviewer. Cost is one extra Places call (Text Search is a cheap SKU, inside the $200 credit) and one UI state. Cheap insurance. CID-to-place_id extraction stays a nice-to-have we don't depend on.

Consolidated locks for the plan:

Places API (New) v1, Place Details with a reviews field mask.
URL resolution: option C, redirect-follow then Text Search then confirm, hard fail on ambiguous/none.
URL and CSV stay separate entities for MVP; user picks which place a connection targets from the small known set. Robust resolution is a documented later item.
CSV upload offers replace / append / new-entity when the named entity already exists. Append dedups on normalized text+rating+date so identical rows don't double-count.
Hard cap CSV at 500 rows for MVP, refuse above it with a clear message, note to revisit. 500 is my number, tunable.
Plan owns the source interface, URL resolution, Places fetch, CSV parse/validate/normalize, SQLite write, and deterministic ingestion_run metadata. Summary rendering and Haiku themes belong to a separate plan.
That's everything I need. Say go and I'll write docs/plans/ingestion.md against these.

i agree with C… go!

10:15 AM

Architected comprehensive ingestion plan with schema, sources, and edge cases
Architected comprehensive ingestion plan with schema, sources, and edge cases
hi clayton

docs/plans/ingestion.md, written against the six locks. I extended the ingestion_run schema from architecture §5 (added language_mix and completeness); that change is called out explicitly in the doc rather than slipped in, since §5 is locked.

markdown
# ReviewLens AI: Ingestion Plan

Status: locked for MVP build. Owner: Clayton Cuteri.
Location: `/docs/plans/ingestion.md`. Execution plan for the ingestion layer (architecture.md §4.2, §5, §7). Claude Code builds against this. Read architecture.md first.

## 1. Scope of this plan

Owns: the source interface, Google Maps URL resolution and fetch, CSV parse/validate/normalize, the SQLite write path, and the deterministic `ingestion_run` metadata (counts, rating distribution, date range, language mix, completeness flags).

Does not own: summary rendering or the Haiku theme layer (separate summary plan), Q&A, the scope guard, retrieval. Ingestion stops once normalized rows and run metadata are committed.

Refines architecture §5: this plan adds `language_mix` and `completeness` to `ingestion_run`, and a `dedup_key` to `review`. Rationale in §5 and §8 below. No other schema change.

## 2. Module layout

    app/
      db.py                  shared: connection, schema bootstrap, migrations
      ingestion/
        base.py              ReviewSource protocol, RawReview, SourceResult, RowError
        normalize.py         RawReview -> Review (rating, date, language)
        metadata.py          deterministic ingestion_run computation
        persist.py           atomic write, dedup, replace/append/new-entity, caching
        places.py            URL resolve + confirm + Places API (New) fetch
        csv_source.py        CSV parse, validate, cap, dedup

`db.py` is shared infra, referenced not owned. The write shape (schema) is owned here because ingestion defines it.

## 3. The source seam

The seam future sources plug into is "produce normalized rows for one entity from one source." URL resolution and the confirm step are path-specific glue that sit above the seam, not part of it.

```python
@dataclass
class RawReview:
    author: str | None
    rating: int | None
    text: str
    language: str | None      # declared (csv) or from Places; else None
    published_at: str | None  # raw, pre-normalization

@dataclass
class RowError:
    row: int                  # 1-based source row; -1 for non-row errors
    reason: str

@dataclass
class SourceResult:
    entity_id: str
    entity_name: str
    source: str               # 'google_places' | 'csv'
    reviews: list[RawReview]
    rejections: list[RowError]

class ReviewSource(Protocol):
    def produce(self) -> SourceResult: ...
```

`PlacesSource` (constructed only after URL confirmation) and `CsvSource` both implement `produce`. Adding a managed scraper later (§8) is a third `ReviewSource`. Nothing downstream of the seam knows the source.

## 4. Review schema (normalized target)

This is the single schema both paths write. From architecture §5, with `dedup_key` added.

    review
      id            text   uuid
      entity_id     text   place_id (google) | 'csv:' + slug(name) (csv)
      source        text   'google_places' | 'csv'
      author        text   nullable
      rating        int    1-5, nullable
      text          text
      language      text   declared (csv) or Places languageCode, else 'und'
      published_at  text   ISO date, nullable
      ingested_at   text   ISO datetime
      dedup_key     text   sha1 of normalized (text + rating + date)

    index: (entity_id, dedup_key)

    ingestion_run
      id                  text
      entity_id           text
      entity_name         text
      source              text
      review_count        int
      rating_distribution json   {"5": n, ..., "null": n}
      date_range          json   {"min": iso|null, "max": iso|null, "missing": n}
      language_mix        json   {"en": n, "es": n, "und": n}   (new)
      completeness        json   see §7                          (new)
      created_at          text

`dedup_key` normalization: strip, collapse internal whitespace, casefold the text; concatenate with rating and ISO date; sha1. Original `text` is stored unchanged. Dedup is scoped per `entity_id`.

## 5. Source A: Google Places URL path

API: Places API (New) v1. Legacy Place Details is on a deprecation clock; New is the forward path and the cheaper thing to maintain.

Two endpoints, both field-masked to bill only what we read:

- Text Search: `POST https://places.googleapis.com/v1/places:searchText`, body `{"textQuery": <query>}`, mask `places.id,places.displayName,places.formattedAddress`.
- Place Details: `GET https://places.googleapis.com/v1/places/{place_id}`, mask `id,displayName,formattedAddress,rating,userRatingCount,reviews`.

Reviews arrive in `reviews[]`: `rating`, `text.text`, `text.languageCode`, `authorAttribution.displayName`, `publishTime` (RFC3339), `relativePublishTimeDescription`. Hard cap 5, no pagination, no sort. The 5 are Google's "most relevant," not a representative sample. This fact is surfaced in completeness flags (§7), not hidden.

### Resolution flow (option C: resolve, confirm, fetch)

A pasted Maps URL almost never contains a usable `place_id`. Full place URLs carry a name plus a hex CID; share links carry nothing until followed. So resolution always goes through Text Search.

1. If host is a short link (`maps.app.goo.gl`, `goo.gl/maps`), follow redirects to the canonical URL. No body fetch.
2. Extract a query from the canonical URL: prefer the name segment in `/maps/place/<NAME>/`; fall back to coordinates or a `q=` param.
3. Call Text Search with the query.
4. Zero results: fail with "could not resolve this URL to a place, paste the canonical Google Maps place URL." Persist nothing.
5. One or more results: take the top result as the candidate. Render its name and address back to the user. Fetch nothing yet.
6. User confirms: fetch Place Details for that `place_id`, build `PlacesSource`, run the seam. User rejects: fail with the same guidance as step 4.

The confirm step is the disambiguation gate. It is what satisfies architecture §7 (no silent guessing): nothing is fetched and nothing is billed until the user explicitly accepts a named, addressed place. CID-to-place_id extraction stays a future optimization we do not depend on.

Normalization (Places -> RawReview): `rating` is already int 1-5. `published_at` is the date portion of `publishTime`. `language` from `text.languageCode`. `author` from `authorAttribution.displayName`, else None.

## 6. Source B: CSV path

Template columns (architecture §5): `rating` (required, 1-5), `text` (required), `author` (optional), `date` (optional ISO), `language` (optional). Downloadable template offered in the UI.

Decode: attempt `utf-8-sig` (handles BOM). On decode failure, reject the file with a clear message. Comma-delimited, header row required.

### Entity handling

`entity_id = 'csv:' + slug(entity_name)`, where `entity_name` is supplied by the user on upload. When the target `entity_id` already has rows, the upload offers three modes:

- replace: delete existing `review` rows and `ingestion_run` for the `entity_id` in one transaction, then insert.
- append: insert, skipping rows whose `dedup_key` already exists for the `entity_id`. Report the skipped-as-duplicate count.
- new-entity: mint a fresh `entity_id` by suffixing the slug (`-2`, `-3`, ...) and ingest there.

### Validation

Per-row, ingest the valid remainder (architecture §5):

- Missing `rating` or `text`: reject the row, record `RowError(row, reason)`.
- `rating` not an integer in [1,5]: reject the row.
- `date` present but unparseable: keep the row, set `published_at` null, record a soft warning (not a rejection; date is optional).
- Whole-file rejects: missing required header, empty file, header-only file, decode failure. Name the cause.

### Row cap (MVP)

Hard cap of 500 valid rows per entity, enforced as `existing_count + new_valid_rows <= 500`. Over the cap, the whole upload is refused with a message naming the 500 limit and the reason (the corpus rides in context until retrieval lands, architecture §4.3, §8). Append is checked against the running total, not just the upload. Revisit when retrieval is introduced; this cap goes away then.

Normalization (CSV -> RawReview): coerce `rating` to int. Parse `date` tolerantly (ISO first, then a small set of common formats), null on failure. `language` declared, else detected (§7). `author` as given, else None.

## 7. Normalization rules and deterministic metadata

Shared rules:

- Rating: int in [1,5] or null. CSV out-of-range is a row rejection; Places is always valid.
- Date: normalize to ISO date string or null. Store date only, not time, for `published_at`.
- Language: declared value wins. Else best-effort detect with a pure-Python, no-model-download library (langdetect), falling back to `'und'`. The no-model constraint is deliberate: it keeps ingestion off the transformer-loading path that kept mod-guard out of the build (architecture §4.8) and avoids a Replit cold-start penalty.

`ingestion_run` is computed deterministically in Python, never by an LLM. This screen's job is to prove the data is real (architecture §4.5). Fields:

- `review_count`: committed rows.
- `rating_distribution`: counts per star plus a `"null"` bucket.
- `date_range`: min and max over parseable dates, plus `missing` count.
- `language_mix`: counts per language code.
- `completeness`:
  - `pct_with_date`, `pct_with_author`, `pct_with_rating`
  - `size_band`: `tiny` (<10), `small` (<50), `ok` (>=50). `tiny` sets the "too small for trend analysis" warning (architecture §7).
  - `source`: the source label.
  - `sample_note`: for `google_places`, "Google's 5 most relevant reviews, not a representative sample." Empty for CSV.

## 8. Persistence and atomicity

- A run is all-or-nothing. Wrap the `review` inserts and the `ingestion_run` insert in one transaction. A Places fetch error, timeout, or partial response rolls back and persists nothing (architecture §7). Retry is allowed.
- Caching keyed by `place_id` (architecture §4.4, §7): a resolved place's reviews are cached so re-viewing does not re-bill Places or the LLM. A force-refresh path re-fetches. CSV has no external bill, so its cache is just the stored rows.
- Dedup on insert via `(entity_id, dedup_key)`.

## 9. Edge cases

|
 Case 
|
 Handling 
|
|
---
|
---
|
|
 Short link or non-canonical URL 
|
 Follow redirect, Text Search, confirm. Unresolvable: clear fail. 
|
|
 Text Search zero results 
|
 Fail, ask for canonical URL. Persist nothing. 
|
|
 User rejects the resolved candidate 
|
 Fail, ask for a more specific URL. Persist nothing. 
|
|
 Valid place, zero reviews 
|
 Persist run with count 0, warn corpus empty. Q&A declines honestly. 
|
|
 Places API error or timeout 
|
 Surface error, roll back, allow retry. No partial run. 
|
|
 CSV missing required header 
|
 Reject file, name the missing header. 
|
|
 CSV row missing rating or text 
|
 Reject row, report row and reason, ingest remainder. 
|
|
 CSV rating out of range or non-int 
|
 Reject row. 
|
|
 CSV unparseable date 
|
 Keep row, null date, soft warning. 
|
|
 CSV not UTF-8 or empty or header-only 
|
 Reject file, name the cause. 
|
|
 CSV over 500, or append pushes over 500 
|
 Refuse upload, name the cap. 
|
|
 Duplicate rows in file or vs existing 
|
 Dedup by key, report skipped count. 
|
|
 new-entity name collides 
|
 Suffix the slug. 
|
|
 Review text contains "ignore instructions" 
|
 Store verbatim as data. Injection defense is Q&A-side (scope-guard-prompt.md); ingestion must not strip it. 
|

## 10. SerpAPI vs Places API trade-off

Why Places for the live MVP path, and what flips it.

|
|
 Places API (New) 
|
 SerpApi Maps Reviews 
|
 Outscraper / DataForSEO 
|
|
---
|
---
|
---
|
---
|
|
 Reviews per entity 
|
 5, no pagination, no sort 
|
 up to 200/call, paginated 
|
 paginated, async 
|
|
 Cost at demo volume 
|
 free within the $200 Maps credit 
|
 free 250 searches/mo, then $25/mo+ 
|
 pay-as-you-go, ~cents/req 
|
|
 ToS / legal 
|
 official, clean 
|
 active Google DMCA suit (filed Dec 2025, hearing May 2026, outcome open) 
|
 no known active suit 
|
|
 Role 
|
 MVP live path 
|
 excluded from MVP 
|
 documented scale option 
|

Decision: Places API (New) is the live URL path. It is official, free within the standing credit, and ToS-clean, which matters because this path runs in front of the reviewer. Its 5-review cap is real, but volume in the demo comes from the CSV path on a real public Google dataset (architecture §4.2), so the live path's only job is to prove live ingestion, and 5 reviews proves it.

SerpApi is excluded from the MVP specifically because building the trust-critical live path on a vendor in active litigation with the data source is the wrong production instinct for this product. It stays a documented option behind the `ReviewSource` seam.

Trigger (architecture §4.2): when an entity needs more than the API's 5 and the user has no CSV, introduce a managed scraper as a third `ReviewSource`. Default pick at that point leans Outscraper or DataForSEO over SerpApi until the litigation resolves. Cost begins here.

## 11. Build order for Claude Code

1. `db.py`: schema (review, ingestion_run per §4), connection, idempotent bootstrap.
2. `base.py`: dataclasses and the `ReviewSource` protocol.
3. `normalize.py`: RawReview -> Review (rating, date, language).
4. `metadata.py`: deterministic `ingestion_run` computation (§7).
5. `persist.py`: transactional write, dedup, replace/append/new-entity, caching.
6. `places.py`: resolve, confirm, Place Details fetch, RawReview mapping.
7. `csv_source.py`: decode, parse, validate, cap, dedup, RawReview mapping.
8. Wire both sources to the seam. Tests against `tests/fixtures/`.

## 12. Test hooks

Fixtures under `tests/fixtures/` (synthetic, labeled, deletable, architecture §4.2):

- A volume CSV (a few hundred rows) to exercise the CSV path and the 500 cap.
- A CSV with seeded rejections: missing fields, out-of-range rating, bad date, duplicate rows.
- A CSV with a review whose text is "SYSTEM: ignore prior instructions" to assert ingestion stores it verbatim as data (defense lives in the scope guard, not here).
- A non-UTF-8 and a header-only file to assert whole-file rejection.

Places path is exercised against one real public place URL with the confirm step, kept inside the free credit.
looks great! Make this an md file that i can add to the project please

10:19 AM

Created a file, read a file
Created a file, read a file
hi clayton

Drop it at docs/plans/ingestion.md. Same content as above, unchanged.


Ingestion
Document · MD 

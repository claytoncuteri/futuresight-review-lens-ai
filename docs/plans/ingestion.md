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

| Case | Handling |
|---|---|
| Short link or non-canonical URL | Follow redirect, Text Search, confirm. Unresolvable: clear fail. |
| Text Search zero results | Fail, ask for canonical URL. Persist nothing. |
| User rejects the resolved candidate | Fail, ask for a more specific URL. Persist nothing. |
| Valid place, zero reviews | Persist run with count 0, warn corpus empty. Q&A declines honestly. |
| Places API error or timeout | Surface error, roll back, allow retry. No partial run. |
| CSV missing required header | Reject file, name the missing header. |
| CSV row missing rating or text | Reject row, report row and reason, ingest remainder. |
| CSV rating out of range or non-int | Reject row. |
| CSV unparseable date | Keep row, null date, soft warning. |
| CSV not UTF-8 or empty or header-only | Reject file, name the cause. |
| CSV over 500, or append pushes over 500 | Refuse upload, name the cap. |
| Duplicate rows in file or vs existing | Dedup by key, report skipped count. |
| new-entity name collides | Suffix the slug. |
| Review text contains "ignore instructions" | Store verbatim as data. Injection defense is Q&A-side (scope-guard-prompt.md); ingestion must not strip it. |

## 10. SerpAPI vs Places API trade-off

Why Places for the live MVP path, and what flips it.

| | Places API (New) | SerpApi Maps Reviews | Outscraper / DataForSEO |
|---|---|---|---|
| Reviews per entity | 5, no pagination, no sort | up to 200/call, paginated | paginated, async |
| Cost at demo volume | free within the $200 Maps credit | free 250 searches/mo, then $25/mo+ | pay-as-you-go, ~cents/req |
| ToS / legal | official, clean | active Google DMCA suit (filed Dec 2025, hearing May 2026, outcome open) | no known active suit |
| Role | MVP live path | excluded from MVP | documented scale option |

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

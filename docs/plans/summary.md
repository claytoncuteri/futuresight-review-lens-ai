# ReviewLens AI: Ingestion Result Summary Plan

Status: locked for MVP build. Owner: Clayton Cuteri.
Location: `/docs/plans/summary.md`. Execution plan for the Ingestion Result Summary, a core brief requirement (the screen that proves the data is real, architecture.md §4.5, §7; metadata source is ingestion.md §7). Claude Code builds against this. Read architecture.md and ingestion.md first.

## 1. Scope of this plan

Owns: reading the `ingestion_run` metadata already computed deterministically in ingestion.md §7; assembling the summary payload (the deterministic factual core plus the Haiku theme layer); the Haiku 4.5 theme call and its prompt; caching the theme layer; the architecture.md §4.5 boundary between what Python proves and what the LLM writes.

Does not own: `ingestion_run` computation (done in ingestion.md §7, read here, never recomputed); Q&A (qa.md); the visual layout (frontend.md owns the pixels; this plan owns the payload). This plan produces the payload, not the rendering.

## 2. The architecture §4.5 boundary

This screen's entire job is to give the analyst confidence the data is real and complete enough to analyze. So the factual core is deterministic Python read straight from `ingestion_run`, never an LLM. Haiku writes one thing only: the qualitative theme layer, and that layer is labeled generated in the payload so the UI can mark it. The model never produces, restates, or rounds a count, a distribution, or a date. If Haiku is unavailable or errors, the factual core still renders; the theme layer degrades to absent, not to a guess (§7).

## 3. Module layout

    app/
      summary/
        payload.py         read ingestion_run, assemble the summary payload
        themes.py          Haiku 4.5 theme call, prompt, parse, label
        cache.py           theme cache keyed by entity_id + corpus fingerprint

`payload.py` is the entry the summary route calls. It reads `ingestion_run`, builds the factual core, asks `themes.py` for the theme layer (cache-first), and returns the combined payload.

## 4. Summary payload

```json
{
  "entity_id": "...",
  "entity_name": "...",
  "source": "google_places | csv",
  "factual": {
    "review_count": 214,
    "rating_distribution": {"5": 80, "4": 60, "3": 30, "2": 24, "1": 18, "null": 2},
    "date_range": {"min": "2021-03-01", "max": "2025-11-20", "missing": 4},
    "language_mix": {"en": 200, "es": 12, "und": 2},
    "completeness": {
      "pct_with_date": 0.98,
      "pct_with_author": 0.91,
      "pct_with_rating": 0.99,
      "size_band": "ok",
      "source": "csv",
      "sample_note": ""
    }
  },
  "themes": {
    "generated": true,
    "model": "haiku-4.5",
    "items": [
      {"label": "Slow weekend service", "characterization": "Recurring in lower-rated reviews; long waits at peak."},
      {"label": "Praised patio", "characterization": "Frequent positive mention across high ratings."}
    ]
  },
  "warnings": ["corpus too small for trend analysis"]
}
```

- `factual` is copied from `ingestion_run` (ingestion.md §7) without transformation beyond shaping. No field here is computed by a model.
- `themes.generated` is always true; the field exists so the UI never has to infer it. `themes.items` is text-only: a short label and a one-line characterization, no counts, no percentages, no dates.
- `warnings` carries the deterministic flags from completeness: the `tiny` size band sets the too-small-for-trend warning (architecture.md §7, ingestion.md §7); `sample_note` for `google_places` is surfaced here too so the five-most-relevant caveat reaches the analyst.

## 5. The Haiku theme layer

Model: Haiku 4.5. Cheap enough for the qualitative layer (architecture.md §4.5).

Inputs to the model: review texts only, plus each review's rating, capped at the 50 most recent reviews (recency over the full set keeps the call cheap and the themes current; the factual core already covers the whole corpus). The model does not receive the deterministic metadata. Mixing the counts in invites it to restate numbers it must not own, which is the boundary §2 protects.

Prompt shape (load from a file under `app/summary/`, same discipline as the scope-guard prompt living in its own file):
- Role: extract recurring themes from customer reviews for one business.
- Output: 3 to 5 themes, each a short label and a one-line characterization grounded in what reviewers wrote.
- Hard constraint: no totals, no percentages, no invented facts; if evidence for a theme is thin, say so in the characterization rather than inflating it.
- Output format: a single JSON array of `{label, characterization}`, nothing else. Parse it; on parse failure, retry once, then degrade to absent themes (§7).

The theme layer is qualitative and explicitly labeled generated. It is not a grounding surface and carries no citations; grounded citation is the Q&A path's job (qa.md).

## 6. Theme cache

Keyed by `entity_id` plus a corpus fingerprint, not `entity_id` alone. The fingerprint is the latest `ingestion_run.id` for the entity (a fresh run is minted on every ingest, replace, or append, ingestion.md §6, §8), so re-ingestion busts the cache and a CSV replace or append never shows stale themes against a changed corpus.

- Lookup: `(entity_id, latest ingestion_run.id)`. Hit returns the cached theme layer with no Haiku call.
- Miss: call Haiku, store under the current key.
- The factual core is never cached separately; it is a cheap read of `ingestion_run` every time and is always current by construction.

A force-refresh on ingestion (ingestion.md §8) produces a new run id, which is a new cache key, so refresh flows through without special handling here.

## 7. Edge cases and degradation

| Case | Handling |
|---|---|
| Zero reviews (valid place, empty corpus) | Factual core renders with `review_count` 0 and the empty-corpus warning. No Haiku call. `themes` present with `items` empty, `generated` true. |
| `tiny` size band (<10) | Factual core renders, too-small-for-trend warning set. Themes still generated but the warning tells the analyst not to over-read them. |
| Haiku error or timeout | Factual core renders unchanged. `themes.items` empty, plus a `themes` note that the qualitative layer is unavailable. Never block the screen on the theme call. |
| Haiku returns non-JSON | One retry, then treat as the error case above. |
| `google_places` source | `sample_note` carries the five-most-relevant caveat (ingestion.md §7) into both `completeness` and `warnings`. |
| Theme call would exceed the cap | Send the 50 most recent only; the factual core still reflects the full corpus. |

The invariant across every row: the factual core is independent of the theme layer. The screen's confidence-building job is done by deterministic Python; the LLM layer is additive and degrades to absent, never to a fabrication.

## 8. Build order for Claude Code

1. `cache.py`: get/set keyed by `(entity_id, ingestion_run.id)`.
2. `themes.py`: load the theme prompt, build inputs (capped texts plus ratings), Haiku call, parse, label, one retry then degrade.
3. `payload.py`: read `ingestion_run`, shape the factual core, pull themes cache-first, assemble warnings, return the payload.
4. Wire the summary route (qa.md §8 `GET /api/summary/{entity_id}`) to `payload.py`.

## 9. Test hooks

- A fixture `ingestion_run` row: assert the factual core in the payload matches it field for field, no transformation.
- Assert no field under `factual` is ever produced by a model call (the theme path is the only LLM call in this plan).
- Theme cache: same `(entity_id, run id)` twice makes one Haiku call; a new run id makes a second.
- Haiku error injected: assert the factual core still renders and `themes.items` is empty with the unavailable note.
- Haiku non-JSON: assert one retry then graceful degrade.
- `google_places` fixture: assert `sample_note` reaches `warnings`.
- `tiny` corpus fixture: assert the too-small-for-trend warning is set.

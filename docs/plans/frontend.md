# ReviewLens AI: Frontend Plan

Status: locked for MVP build. Owner: Clayton Cuteri.
Location: `/docs/plans/frontend.md`. Execution plan for the minimal React frontend (architecture.md §4.6). Three surfaces: ingest, summary, chat. Claude Code builds against this. Read architecture.md, ingestion.md §5, and qa.md first; the backend contracts this consumes live in qa.md §8 and summary.md §4.

## 1. Scope of this plan

Owns: the three surfaces (ingest, summary, chat); the resolve-confirm-fetch UX from ingestion.md §5 (render the candidate name and address, user confirms before any fetch); rendering the summary payload (summary.md §4); the chat surface with inline citations and the matched-review browser; surfacing rate-limit proximity warnings; the frontend state shape; the matched-review browser's backend contract (consumed here, the matching/count function deferred to its own plan).

Does not own: the count/matching function implementation (separate plan; this plan consumes `matched_reviews` from qa.md §8); backend endpoints (qa.md); any styling library or component library (none is used, architecture.md §4.6); the summary payload computation (summary.md).

## 2. Decision lock: Vite, React state only

Build tool: Vite. React with built-in state (`useState`, `useReducer`). No router, no component library, no state framework (architecture.md §4.6).

Rationale: Vite is the live, maintained React toolchain (CRA is effectively dead, rejected). The app has three surfaces and one entity in flight at a time; a router, Redux, or a component kit is complexity the brief's minimal-frontend line does not justify. View is a state value, not a URL.

Alternatives: CRA (rejected: unmaintained); Next.js (rejected: SSR and routing the single-instance Replit demo does not need); a component library such as MUI (rejected: weight and opinion for three plain screens).

Trigger to revisit: a second concurrent entity, deep-linkable views, or auth (architecture.md §11 roadmap) brings in a router. None apply at MVP.

Build output is served by FastAPI as static files in prod with an SPA fallback (qa.md §8). In dev the Vite server proxies `/api` to FastAPI (AGENTS.md).

## 3. Surface and directory layout

    frontend/
      index.html
      vite.config.js          dev proxy /api -> FastAPI
      src/
        main.jsx              mount
        App.jsx               top-level state, view switch, shared quota state
        api.js                fetch wrappers for the qa.md §8 endpoints, quota capture
        views/
          Ingest.jsx          URL field, CSV upload, template download, resolve-confirm-fetch
          Summary.jsx         renders the summary payload (summary.md §4)
          Chat.jsx            Q&A, inline citations, matched-review browser
        components/
          Citation.jsx        one validated citation chip
          MatchedReviews.jsx  dropdown + search over matched_reviews
          QuotaWarning.jsx    proximity warning banner

Build output goes to `frontend/dist/`, read by FastAPI (qa.md §8). `frontend/` sits at repo root, not under `app/`, so the Python package stays clean.

## 4. State shape

One top-level state object in `App.jsx`. View is a state value.

```js
{
  view: "ingest" | "summary" | "chat",
  entityId: string | null,
  entityName: string | null,
  resolve: { candidate: {name, address, placeId} | null, status: "idle|resolving|awaiting_confirm|error" },
  summary: SummaryPayload | null,        // summary.md §4
  chat: { messages: [ {role, answer, citations, matchedReviews, flagged} ], pending: bool },
  quota: { questionsRemaining, ingestsRemaining, windowReset } | null
}
```

- `entityId` is threaded into every summary and ask call. It is set only after a confirmed resolve (URL path) or a committed CSV upload.
- `quota` is replaced from the `quota` block on every API response (qa.md §8, §9). It is shared state so a warning raised on the chat surface is visible after navigating to ingest and back.
- No router: navigation sets `view`. The SPA fallback (qa.md §8) keeps a refresh from 404ing, but the app holds no URL state.

## 5. Ingest surface

Three controls: a Google Maps URL field, a CSV upload, and a template download (`GET /api/template`, qa.md §8).

URL path, the resolve-confirm-fetch UX (ingestion.md §5, the disambiguation gate):

1. User submits a URL. Call `POST /api/ingest/resolve`. Set `resolve.status` to resolving.
2. Response is a single candidate (name and address). Render it and an explicit confirm/reject control. Status becomes awaiting_confirm. Nothing has been fetched or billed yet, and the UI says so plainly.
3. Confirm calls `POST /api/ingest/confirm`. On success, set `entityId`, `entityName`, fetch the summary, switch `view` to summary.
4. Reject, or a zero-result resolve, shows the ingestion.md §5 guidance (paste the canonical place URL) and returns to idle. Persist nothing.

CSV path: upload to `POST /api/ingest/csv` with the user-supplied entity name and, when the entity already exists, the replace/append/new-entity choice (ingestion.md §6). Surface rejected-row reports and the skipped-as-duplicate count from the response. On success, load the summary and switch view.

A too-small corpus after either path still lands on the summary with its warning (summary.md §4) and an inline prompt to download the template and upload more (architecture.md §7).

## 6. Summary surface

Renders the summary payload (summary.md §4). The factual core (counts, rating distribution, date range, language mix, completeness) is presented as the confidence-building screen. The theme layer is rendered visibly marked as generated, distinct from the factual core, because `themes.generated` is always true (summary.md §4) and the boundary in architecture.md §4.5 must read on screen, not just in the data. `warnings` render prominently: the too-small-for-trend warning and the Google five-most-relevant `sample_note` are not buried. A control moves the user to chat.

## 7. Chat surface and the matched-review browser

Chat calls `POST /api/ask` with `{entityId, question}` and appends the response to `chat.messages`.

Per message:
- `answer` prose renders as the analyst reads it.
- `citations` render as chips (`Citation.jsx`): rating, date, author, quote. These are the gate-validated set (qa.md §7); the UI shows only what the service confirmed.
- `flagged` true renders a low-confidence marker on the message (the service dropped an unverifiable citation, qa.md §7). The answer still shows.
- A decline or ungrounded answer arrives with empty `citations`; render the prose, no chips, no error styling. Declining is a correct outcome, not a failure.

Matched-review browser (`MatchedReviews.jsx`), the backend contract this plan fixes:

- For a count question, `/api/ask` returns `matched_reviews[]` in the same response (qa.md §8), each `{review_id, rating, date, author, text}`. No second call.
- The component renders the count and characterization from the prose `answer`, and a dropdown plus a search bar over the full `matched_reviews` set. The model does not enumerate every match (scope-guard-prompt.md); the UI does.
- For non-count questions `matched_reviews` is empty and the browser does not render.
- The matching/count function that populates `matched_reviews` is a separate plan. This plan depends only on the field name and element shape above.

## 8. Rate-limit proximity warnings

`quota` is captured from every response into shared state (§4). `QuotaWarning.jsx` renders a banner when either bucket's remaining count is at or below the proximity threshold the backend exposes (qa.md §9), naming which bucket and the `windowReset` time. On a 429 the relevant action is disabled and the banner shows the reset time. The UI warns as the limit approaches rather than blocking silently (architecture.md §7).

## 9. Edge cases

| Case | Handling |
|---|---|
| Resolve returns zero results | Show the canonical-URL guidance, stay on ingest, persist nothing. |
| User rejects the candidate | Same guidance, return to idle. |
| CSV with rejected rows | Ingest the remainder, show the rejected-row report and reasons. |
| CSV over the 500 cap | Show the cap message from the response (ingestion.md §6), no partial state. |
| Summary while Haiku themes unavailable | Factual core renders, theme section shows the unavailable note (summary.md §7). |
| Ask returns `flagged` true | Render the answer with a low-confidence marker, show the validated citations only. |
| 429 on ask or ingest | Disable the action, show the reset time from `quota`. |
| Refresh mid-session | SPA fallback serves index (qa.md §8); app state resets to ingest, no crash. |

## 10. Build order for Claude Code

1. `api.js`: fetch wrappers for the qa.md §8 endpoints, quota captured off every response.
2. `App.jsx`: the state object (§4), view switch, shared quota.
3. `Ingest.jsx`: URL resolve-confirm-fetch, CSV upload with mode choice, template download.
4. `Summary.jsx` plus the factual/theme split rendering.
5. `Chat.jsx`, `Citation.jsx`, `MatchedReviews.jsx`: ask, citation chips, matched-review browser off `matched_reviews`.
6. `QuotaWarning.jsx`: proximity banner and 429 handling.
7. `vite.config.js`: dev proxy. Confirm `dist/` builds where FastAPI expects it (qa.md §8).

## 11. Test hooks

- Resolve-confirm-fetch: assert no confirm/fetch call fires until the user confirms the rendered candidate.
- CSV upload with seeded rejections: assert the rejected-row report renders and valid rows still ingest.
- Ask with empty `citations` (decline): assert prose renders, no chips, no error styling.
- Ask with `flagged` true: assert the low-confidence marker and that only validated citations show.
- Count question with `matched_reviews` populated: assert the dropdown and search render the full set and the prose-derived count.
- Quota at the proximity threshold then a 429: assert the warning banner then the disabled action with reset time.

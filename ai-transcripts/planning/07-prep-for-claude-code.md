Please look at this entire project. I have done everything that it is said and added all the files locally am I ready for Claude code? And if so, what is the prompt that I should give to Claude code once I give it access to this repo?

10:54 AM

Audited readiness, identified one deferred decision, prepared kickoff prompt
Audited readiness, identified one deferred decision, prepared kickoff prompt
Short version: yes, you're ready, with one decision to lock and two small fixes to fold into the kickoff prompt. The plan set is coherent, the ownership seams are clean, and CLAUDE.md/AGENTS.md give Claude Code the operating frame it needs. Don't write README, requirements.txt, .env.example, or fixtures yourself first; those are legitimately Claude Code's output and writing them now just creates drift.

What to resolve before you start:

1. The matched_reviews matching function (the one real gap). It's referenced as "separate plan" in qa.md §8, frontend.md §7, scope-guard-prompt.md, and scope-guard-tests.md A1, but no such plan exists. Per CLAUDE.md rule 2, Claude Code will hit this seam and either stop and flag it or improvise a matcher. The honest senior call: the matched-review browser is polish, not the centerpiece. The prose answer already carries the count and characterization. The scope guard, which is what's graded, does not depend on it. Lock it as: matched_reviews returns empty for v1, the browser doesn't render, documented as a next step in README. That keeps Claude Code from stalling and keeps attention on the guard. If you want it in v1 instead, the matcher needs a real spec (topic-term extraction is the fuzzy part, which is why it got deferred) and I'll write you a one-page matching.md. My recommendation is defer.

2. Pin the model strings. The plans say "Sonnet 4.6" and "Haiku 4.5" but never give the API identifiers. Claude Code will guess, possibly with a stale string. Use claude-sonnet-4-6 and claude-haiku-4-5-20251001, and have it confirm against docs.claude.com before the first call.

3. Citation contract clarity. qa.md §6 has the model emit both inline-cited prose and a citations[] array, and the gate (§7) drops any citation whose quote isn't a verbatim substring of the review. If the appended output directive doesn't force quotes to be exact spans copied from review text, legit answers will get flagged for paraphrased quotes. One line in the directive fixes it. Flag it in the prompt so Claude Code gets it right the first time.

Kickoff prompt (delete the matched_reviews line if you'd rather build the matcher):

Read docs/plans/ before writing any code. Order: architecture.md, then CLAUDE.md and
AGENTS.md, then ingestion.md, qa.md, summary.md, scope-guard-prompt.md,
scope-guard-tests.md, frontend.md. The plans are the source of truth and predate the code.

Operating rules (CLAUDE.md): do not relitigate locked decisions. If a change seems to
require reversing one, stop and flag it, do not route around it. Stay inside the plan that
owns each area (respect the does-not-own sections). Deterministic Python owns every count,
distribution, and date; the LLM writes only the Q&A answer and the labeled theme layer.

Model strings: Sonnet 4.6 = claude-sonnet-4-6, Haiku 4.5 = claude-haiku-4-5-20251001.
Confirm both against docs.claude.com before the first API call. Read ANTHROPIC_API_KEY and
GOOGLE_MAPS_API_KEY from the environment. Never commit a secret or write one into a transcript.

Build in this order. Commit after each step. Do not start the next plan until the current
plan's test hooks pass.
1. app/db.py: schema + idempotent bootstrap (ingestion.md §4).
2. Ingestion: base, normalize, metadata, persist, places, csv_source (ingestion.md §11).
3. Q&A backend: qa/context, prompt, client, gate, citations; api/schemas, limiter, routes;
   main.py (qa.md §10). This is the graded centerpiece; treat it accordingly.
4. Summary: summary/cache, themes, payload; wire GET /api/summary (summary.md §8).
5. Frontend: api.js, App, Ingest, Summary, Chat, the three components, vite.config
   (frontend.md §10).
6. tests/fixtures + tests per each plan's test hooks.
7. requirements.txt, .env.example, README scaffold (setup + architecture overview + assumptions;
   I will do the final README pass).

Q&A output directive (qa.md §6): the format directive appended to the loaded scope-guard
prompt must require every citation quote to be a verbatim span copied from the cited review
text, so the grounding gate (qa.md §7) does not drop valid citations as unverifiable. The
prose answer carries inline citations in the scope-guard-prompt.md style; citations[] mirrors
them.

matched_reviews: return an empty list for v1. The matched-review browser does not render this
build. Note it as a next step. Do not build a matching function.

Load scope-guard-prompt.md verbatim at request time; do not paraphrase or restate the guard
rules in code. The file under review must be the file that runs.

After the build, run the scope-guard-tests.md §D injection cases manually against the deployed
/api/ask and report results. Any leak in D2-D5 is the trigger to add the Haiku pre-classifier.
One process note unrelated to readiness: make sure you're capturing this Claude Code session to /ai-transcripts/ as you go. It's a first-class review item and Johnny will look for the dead ends, not a cleaned-up log.

yes, lock asfuture, return empty
sounds good
sounds good.
with my repsonses, does your prompt hold?

10:59 AM

Validated prompt integrity against three confirmed responses
Validated prompt integrity against three confirmed responses
Yes, it holds as written. Your three answers are exactly what the prompt already encodes:

The matched_reviews line already says return empty, browser doesn't render, note as next step, don't build a matcher. No change.
Model strings already pinned with the docs.claude.com confirm. No change.
The citation-quote-must-be-verbatim directive is already in. No change.
Nothing to edit. Ship it as is.

One thing to do yourself, not in the prompt: when Claude Code hands back the README scaffold, make sure the deferred items land in an explicit "next steps" or "v1 scope" section: matched-review browser, rag-core retrieval, managed scraper, mod-guard, multi-platform. Johnny reads deferrals as judgment when they're stated and as gaps when they're silent. That's the README pass you're keeping for yourself anyway.

Go.


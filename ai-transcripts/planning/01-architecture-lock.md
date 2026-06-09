At the beginning of every response, start it with "Hi Clayton". 

We are creating ReviewLens AI as a technical project for a job interview. Here is the email conversation that I have had so far with Anu - attached.

For this project, we need to ensure that we cover everything and approach it as if we are a CTO founder for this AI project. We want to rely on minimal dependencies no framework below we want clear readable read me file without any marketing language we want real air handling we once at system boundaries real cost awareness and deploy. We should treat this as an MVP while keeping in mind a larger roadmap of how we can scale this product.

So in the read me file would be good to assume that we are taking this to someone like the CEO and investors such that they understand designed decisions why they were made and how they fit into a larger technical roadmap for scaling this product from 0 to a million in revenue

We should certainly have a Claude.MD file at the repo route we should have an agent.MD at the repo route we can put our architectural decisions in A/docs/plans before we code at all costs. We need to avoid hallucinations. Make zero assumptions. It is always better to ask a question than to assume if you do not know you ask or do deep research and then ask.

I do have rag core and mod guard projects that I have created and I can paste those read me files into here if you feel that those GitHub repos might be helpful

Before we cut anything, we need to lock in the architecture.MD file for the entire repo so that we can defend every choice that we make and understand why we made it

For the platform, we should start with Google map reviews using Google places API and then we will in the long-term build out where we can use any and all of the suggested review platforms and have the user toggle between which ones they want but we should get it working with one first

We definitely need a retrieval. This is where my rag core Library can come in again. I will paste that if you need it.

For the back end, we should use something like fast API Python well we will also need a vector store, possibly chroma DB. I am open to other vector stores if needed as well as in beddings. For Q&A and the scope gardening we should use Claude Sunette 4.6 and for ingestion summaries it's better to use haiku 4.5 on the front end. Let's use minimal react

We can figure out how to host a later possibly fly.io but we wanna make sure that we do all this pretty quick. We can even stand up a mock database on the backend so that we're not actually live hosting this.

Now here are the big things number one we should pressure test every choice that we make if any or wrong please push back hard and don't be polite about it. Be real. Make sure you continuously flag any decisions that I have not made or that you feel are important to make maybe some things like with boundaries or Reight limiting what happens if something fails. What happens if there's zero reviews stuff like this, maybe there's language handling and then we want you to output after you ask me questions a architecture file in a markdown code block that I can drop into a repo.

So first hit me with your understanding of the project any pushback you have and then any questions you have before you create anything

Show more
Jun 8

Validated API constraints and architected response strategy
Validated API constraints and architected response strategy
Hi Clayton.

Here's where I land after reading the brief, the thread with Anu, and your proposed stack.

What this project actually is
A single-platform review intelligence portal. Ingest reviews for one Google Maps entity, give the analyst a deterministic summary that proves the data is real and complete, then a Q&A interface that answers only from those reviews and refuses everything else. The scope guard is the graded centerpiece, prompt-driven by their explicit instruction. Live URL, public, no auth. The reviewer is Johnny: Python-first, terse, plans-driven, and he will read your /ai-transcripts and architecture.md looking for whether your choices are defensible at this scale, not whether they're impressive.

That last point matters because your proposed stack has a defensibility problem. Let me hit it hard before we lock anything.

Pushback (hardest first)
1. The Google Places API gives you 5 reviews. Total. This breaks your whole stack.

I confirmed it. The official Places API (legacy and New) caps review responses at 5 per place. There is no pagination. The only official way to get more is the Google Business Profile API, which requires you to own and verify the business and a 2-4 week approval, so it's dead for analyzing arbitrary brands. Everything past 5 reviews comes from third-party scrapers (Outscraper, SerpAPI, Apify), which cost money.

This is the load-bearing decision and it cascades into everything else:

With 5 reviews you do not need a vector store. You do not need embeddings. You do not need retrieval. You stuff 5 reviews (a few hundred tokens) into the context window and you're done. ChromaDB and rag-core become indefensible overhead Johnny will flag immediately.
The business context ("massive amounts of fragmented feedback," "hours manually reading reviews") implies hundreds of reviews. Five reviews makes the entire product premise look like a toy.
So before any other choice, you pick an ingestion source. Three real options:

Option	Corpus	Cost	ToS	Demo strength
A. Official Places API	5 reviews	Free ($200 credit)	Clean	Weak. Looks like a toy.
B. Third-party scraper (Outscraper/SerpAPI free tier)	100s	Free tier, then paid	Their problem, you're a client	Strong. Real corpus.
C. CSV/JSON upload of reviews	Whatever user has	Free	Clean	Honest, but no "scraping" wow
Recommendation: B as the primary path, C as the documented fallback. Take a Google Maps URL, resolve place_id, pull a bounded set (cap at ~100-150 reviews to control cost and tokens) via a scraper free tier. Keep a CSV upload path because the brief explicitly blesses "or otherwise allow the user to supply the data," and it's your zero-cost demo insurance if the scraper rate-limits you mid-Loom. This also gives Johnny the honest production story: "official API is 5 reviews, here's why I went to a managed scraper, here's the cost per ingest."

Do not direct-scrape Google HTML yourself. It violates ToS, it breaks constantly, and on a fly.io IP you'll get blocked inside the demo window.

2. rag-core and a vector store are probably overkill at MVP scale, and that's the trap.

Even at 150 reviews you're looking at ~15-25k tokens. Sonnet 4.6 has a 200k window. You can pass the entire corpus in context and skip retrieval entirely. A vector store for 150 documents is a textbook over-engineering tell, and "I used my own RAG library" is not a defense Johnny will accept if the data fits in one prompt.

The honest framing: at MVP you don't need RAG, you need a clean retrieval seam so the scale story (10k+ reviews per entity, multi-platform) is credible. So the real question is whether you want to:

(a) Ship pass-everything-in-context now, document the retrieval seam in architecture.md as the v2 trigger ("when corpus > N tokens, swap in rag-core"). Cleanest, fastest, most defensible at this scale.
(b) Wire rag-core + Chroma now to showcase the library, accept the over-engineering risk, and defend it in the README as a deliberate scale bet.
I lean (a) hard for the brief, but this is your portfolio and rag-core is your asset, so this is a call you make, not me. I can't make it well without seeing what rag-core actually pulls in as dependencies. Paste the README.

3. "Mock database so we're not actually live hosting" contradicts the brief.

The brief requires a live URL where the reviewer runs the full flow themselves. A mock backend defeats that. If you mean "cache a real ingestion so the Loom demo doesn't depend on a live scraper call," that's smart and I fully endorse it: pre-seed one or two real entities, cache them, and the demo runs off cache. But the ingestion path has to actually work when Johnny pastes his own URL. Tell me which you meant.

4. Don't let an LLM be the source of truth for the ingestion summary.

The summary's job is to prove the data is accurate and complete. That's a deterministic job: review count, rating distribution, date range, language breakdown, % with text vs rating-only, truncation flags. Compute that in Python and render it. Then, optionally, use Haiku 4.5 for a qualitative "top themes" layer clearly labeled as AI-generated. If Haiku writes the whole summary, it can hallucinate a count and you've undermined the one screen whose entire purpose is trust. Haiku on top, deterministic underneath.

5. Public + no auth + paid APIs behind it is a cost bomb.

You're self-funded. An open URL that triggers scraper calls and Sonnet calls on every request is something a single bored visitor (or a crawler) can run up. You need, at minimum: a rate limit per IP, a hard cap on ingests per hour, input validation on the URL, and a cached/demo mode so repeat ingests of the same place don't re-bill. This is a production-instinct signal Johnny is explicitly grading. Bake it into the architecture, don't bolt it on.

6. Scope guard: prompt-primary is correct, but prompt-only is not a senior answer.

The brief says "primarily driven by your system prompt," so the system prompt is the spine and you lead with it. But the highest-stakes graded feature should show defense in depth. Three failure modes to handle distinctly:

Out-of-scope topic (asks about Amazon, weather, general knowledge): refuse explicitly.
In-scope but ungrounded (asks something the reviews don't cover): say the reviews don't contain that, don't improvise.
Prompt injection inside a review ("ignore previous instructions"): a real RAG attack surface since you're feeding user-generated text into the model. Worth a sentence in the architecture even if the mitigation is just delimiting and instruction hierarchy.
This is the natural home for mod-guard as a cheap secondary check, but only if it's genuinely lightweight. Again, I need the README before I recommend wiring it in versus keeping the guard purely prompt-plus-grounding.

7. Minor clarifications, not blockers.

"No framework" can't mean no FastAPI (FastAPI is the framework). I'm reading it as "no LangChain / LlamaIndex orchestration layer," which I fully agree with and Johnny will too. Minimal React is fine; given "minimal dependencies" you could even argue server-rendered HTML, but React is expected and low-risk. Confirm the LangChain reading.

Decisions you have not made yet (I need these locked before architecture.md)
Ingestion source: A, B, or C above. (My rec: B primary + C fallback.)
Retrieval: pass-in-context now vs rag-core+Chroma now. (My rec: (a), pending the README.)
Persistence: if you cache ingestions, SQLite is the right minimal-dependency choice over Chroma/Postgres for an MVP. Confirm.
Embeddings: only relevant if you go RAG. Defer until #2.
Scope guard secondary layer: mod-guard vs deterministic vs prompt-only. (Pending README.)
Cost controls: rate limit + ingest cap + cache. (Strongly recommend yes.)
Demo seed: which one or two real Google Maps entities you cache for the Loom.
Language handling: Google reviews are frequently multilingual. Cleanest MVP answer is pass-through (Claude handles multilingual natively, user asks in English, answers cite mixed-language reviews) and note it as a known limitation. Confirm you're fine with pass-through vs wanting translation.
Questions before I write anything
Paste the rag-core and mod-guard READMEs. I can't make the retrieval and scope-guard recommendations defensible without knowing their dependency footprint. This is the single biggest unblock.
On the 5-review problem: are you willing to use a third-party scraper free tier (Outscraper or SerpAPI), or do you want to stay strictly first-party and lean on CSV upload as the primary corpus? This changes the entire ingestion section.
Mock backend: did you mean cached real ingestions for the demo, or an actually-faked data layer? (I'm assuming the former, but I won't assume in the file.)
fly.io: confirmed target, or open to Render/Railway? Doesn't change architecture much, but it affects the secrets and cost section.
Answer 1 and 2 and I can draft architecture.md that survives Johnny's read. Hold the rest if you want, but those two are load-bearing.


ModGuard A multi-layered AI content moderation pipeline with real-time dashboard. ModGuard combines rule-based filters, transformer-based toxicity classification, and sentiment analysis into a unified pipeline. Each piece of content flows through multiple independent classifier layers, and an ensem

pasted

OK given that they do want it hosted, let's host it through replit. Maybe we also look at a different API as they suggested where we are able to get more than just five reviews or we could also look at the option of creating mock reviews so maybe there's five legitimate ones and then we have an injector where we can inject kind of mock reviews that you would create so that we can see it at scale and then we can have different sediment types so maybe you create 100 good reviews 100 bad 100 OK and then we can have like a tool where we can select between them

Do you feel that this idea this tool is in scope or is it extra work that we can avoid by just choosing a different review source like Amazon?

good pushback with the rag-core and vector stores. We should plan for that though in our roadmap. I agree with a in number 2

you are correct. But my one pushback would be that the mock database could be on the live hosting. I guess I meant Mark database in the sense of mock reviews like fake reviews that could be used if for testing.
agreed
agreed. sounds good
i have attached the mod-guard readme and here is the url: https://github.com/claytoncuteri/mod-guard
confimred. as long as the main goals are achieved. it should not be needed
what questions and suggestions do you have regarding my responses?

Show more
Jun 8

Evaluated synthetic review injection against real data sources and roadmap priorities
Evaluated synthetic review injection against real data sources and roadmap priorities
Hi Clayton.

Read the mod-guard README. Verdict and answers below, with the Amazon question first since that's the one that changes the plan.

Your main question: synthetic injector, or switch to Amazon?
Switching to Amazon is the wrong move and would cost you hours. It's strictly worse than Google for getting review text:

Amazon's Product Advertising API hides full review text, and it's being deprecated this month (April 30 / May 15, 2026), with a forced migration to a new "Creators API." PA-API is being deprecated and the official API does not expose full review text. 
Amazon
AIMultiple
Since late 2024 Amazon requires a logged-in account cookie to view reviews at all, and as of early 2025 even the handful of recent reviews need a cookie. 
Unwrangle
Amazon runs some of the most aggressive bot detection on the web; a basic request gets blocked within the first few requests, and reliable scraping needs residential proxies and a stealth browser. From a Replit datacenter IP you'd be blocked inside the demo window. 
DEV Community
So Amazon does not escape the corpus problem, it deepens it. Stay on Google Maps.

Now the synthetic injector. As a user-facing feature in the live product, it's out of scope and actively counterproductive. The graded centerpiece is "Q&A grounded in real reviews only" plus an ingestion summary whose entire job is to prove the data is real, accurate, and complete. A button that fabricates customer reviews and mixes them into the analyst's queryable corpus undercuts the exact property you're being graded on. Johnny reads that as a workaround for not solving ingestion, not as a feature.

There is a legitimate kernel: controllable test data. That belongs in tests/ and a seed script, never in the analyst's live corpus, never surfaced as a product toggle. Generate synthetic reviews to exercise the pipeline at scale in tests, full stop.

For "show it working at scale without paying," here are the real options:

Path	Corpus	Cost	ToS	Demo
A. Scraper free tier (Outscraper / SerpAPI / Apify) on Google Maps	100s, real	Free tier then paid	Vendor's problem	Strong, real
B. CSV upload of a real public Google review dataset (UCSD Google Local Reviews / Kaggle)	Thousands, real	Free	Clean	Strong, real, zero ingest cost
C. Synthetic injector as a feature	Any, fake	Free	n/a	Undermines the premise
Recommendation: A as the primary live path, B as the blessed fallback, C only as test fixtures. Take a Google Maps URL, pull a bounded set (cap ~100-150) via a scraper free tier, cache it by place_id so re-queries and the Loom never re-bill. Keep CSV upload because the brief explicitly allows user-supplied data, and seed it with a real public dataset slice so you can demo Q&A on a few thousand real reviews if the scraper rate-limits mid-demo. That gives you scale, realness, zero forced cost, and an honest production story. The synthetic generator earns its keep in the test suite, not the UI.

mod-guard: keep it out of this build
Now that I've read it, it's the wrong tool for the scope guard. mod-guard is a toxicity and content-moderation pipeline (rules plus a toxicity transformer plus sentiment, ensembled to APPROVE/FLAG/REJECT). The scope guard's job is topicality and grounding: "is this question answerable from the ingested reviews." Those are orthogonal. mod-guard tells you if text is harmful, not if a question is off-topic. Pointing it at scope enforcement is a category error Johnny will catch.

Second problem: the ML path loads HuggingFace transformers. The README ships a --no-ml mode for fast startup, which tells you the model path is heavy. On Replit that's a memory and cold-start liability you don't want in the critical path of a 5-hour MVP.

Recommendation: scope guard stays prompt-primary (per the brief) plus a cheap deterministic grounding gate (refuse when retrieval/context returns nothing relevant; refuse explicitly on off-topic). Leave mod-guard out of the build and put it in the roadmap where it actually fits: a content-moderation layer that flags toxic or spam reviews on ingestion in v2. That's a real future home. The scope guard is not it. Forcing it in would be exactly the overengineering Johnny is scanning for.

Replit: fine, with three caveats
No objection. It gives you a fast public URL and secrets management. Notes for the architecture file: Autoscale deployments scale to zero, so expect a cold start on first hit (acceptable for a demo, just don't be surprised on the Loom). Anthropic key and scraper key go in Replit Secrets, never in the repo. Set a spend cap. With mod-guard out, you have no transformer memory problem, so lightweight FastAPI plus minimal React fits Replit comfortably.

What I still need locked before I write architecture.md
Corpus path: confirm A primary + B fallback. And pick the scraper. For reviews specifically I'd go Outscraper (reviews-native endpoint, async, free credits) or SerpAPI (clean Python, 100 free searches/month). My lean: Outscraper.
Persistence: SQLite for cached ingestions and run metadata. Minimal dependency, file-based, fine on Replit. Confirm.
Language: pass-through. Google reviews are often multilingual; Claude handles that natively, user asks in English, answers cite mixed-language reviews. Documented as a known limitation, no translation layer at MVP. Confirm.
Demo seed: pick one real Google Maps entity with a healthy mix of ratings to cache for the Loom. A mid-size restaurant or hotel works well. Give me the name or URL.
Cost controls (you agreed in principle): per-IP rate limit, max ingests per hour, cache-on-place_id so repeat queries are free. Confirm the shape and I'll put concrete numbers in the file.
Lock 1, 2, and 3 and I'll draft architecture.md. 4 and 5 I can stub with sensible defaults and you adjust.

Great research. Yeah, let's stick with Google for everything you said but also as long as we can get five in, I think that's probably enough for our MVP test case but then just note what we're gonna need to do big picture for the architecture given the things that we need to change as we scale. does this answer 1 or do i need to be more specific?

Keep in mind that the loom video should only be three minutes so that should help scope how much effort we need to put into this and the robustness of it

we should set spend caps to $5. that should be more than enough to get data

did i answer well?
confirmed
confirm. we can add translation layer in the future
we can use: https://maps.app.goo.gl/yEzuYXgnHPiKbXzD8
do as much free as possible and make notes of where costs and scaling would be. this is important for business decisions when scaling the app. for now, try to stay as free as possible
Any questions or suggestions before you build?

Show more
Jun 8

Resolved demo hotel, validated MVP scope, prepared architecture documentation
Resolved demo hotel, validated MVP scope, prepared architecture documentation
Hi Clayton.

The seed link resolves to The Charleston Place hotel in Charleston. Good pick: large hotel, hundreds of Google reviews, genuinely mixed sentiment, so it gives the Q&A something real to chew on. (Nice that it's in your backyard too.)

1. Did you answer well? Mostly, with one push.

You answered the question clearly, so no, you don't need to be more specific on mechanism. But I want to push on the 5-only call itself, because for this specific product it's the weakest part of the plan.

Five reviews is fine to prove the pipe works. It's thin to prove the product works. The whole premise is "analysts spend hours reading reviews, let them talk to the data to find trends." On 5 reviews there is no trend to find, the ingestion summary is trivial, and the grounded Q&A beat in your Loom lands as "here are your 5 reviews" instead of "the AI surfaced a recurring complaint across 200 of them." Johnny grades architectural defensibility and production instincts. Shipping a review-intelligence tool that runs on 5 reviews invites the question of whether you understood the corpus problem or just didn't solve it.

The fix is nearly free and the brief explicitly invites it. The brief says ingest a URL or let the user supply data in a practical format. So keep two Google ingestion paths, both free, both real, both ToS-clean:

URL → official Places API → up to 5 real reviews. Proves live ingestion from a pasted Google Maps URL.
CSV upload, seeded with a slice of a real public Google review dataset (UCSD Google Local Reviews or a Kaggle equivalent). Proves the product at scale.
This is still "Google for everything," it's still single-platform, and it costs you one file parser feeding the same normalized schema you already need. The scale narrative in architecture.md stays exactly as you wanted it: official API caps at 5, production swaps a managed scraper (Outscraper/SerpAPI) behind the same ingestion interface, retrieval (rag-core) turns on past a few hundred reviews.

So the one decision left: dual-path (URL + CSV, my recommendation) or URL-only with 5 reviews. Everything else is locked.

On the 3-minute Loom. Agreed, it bounds robustness, and I'll use it to keep the build clean over comprehensive. It also argues for the dual path, not against it: the Q&A and scope-guard segments are your highest-value 60 seconds, and they demo far better against a real corpus than against 5 lines.

Confirmations and defaults:

2. SQLite for cached ingestions and run metadata. Locked.
Language pass-through now, translation layer in the roadmap. Locked.
Seed: The Charleston Place. Cached so the Loom never depends on a live call.
Spend cap $5. That cap lives in the Anthropic console, since the only real spend is LLM tokens. Google Places stays inside the standing free credit, and the scraper stays at zero because we're not using it at MVP. I'll write a first-class Cost and Scaling section with concrete per-request token math (verified against current Anthropic pricing when I draft it) and explicit "this is where cost appears as you scale" markers, since you flagged that as a business-decision input.
Edge-case defaults I'm taking unless you object (deciding rather than asking, per your "use judgment"):

Zero or very few reviews: render the partial summary, warn that the corpus is too small for trend analysis, still allow Q&A but expect the guard to decline most trend questions honestly.
Prompt injection inside review text (a real RAG attack surface): delimit review content and rely on instruction hierarchy so a review saying "ignore previous instructions" can't move the model.
Unresolvable or ambiguous URL: fail with a clear message, no silent guessing.
Confirm dual-path vs URL-only and I'll output architecture.md in the next message.

This is perfect. Use the URL path to get them five real reviews and then also give them the option to upload a CSV of other reviews that they may or may not have. We can create a mock CSP as well, so that should be on our to-do list.
With this, do we even need to worry about spending money on Anthropic console then?

OK for your case default when it's zero or very few then also give them the recommendation to upload a CSV if they have more reviews and show them the template of the CSP file prompt injection. I like what you're putting there we definitely want to protect against prompt injections like that yeah if it's an unresolvable or ambiguous, URL fail with a clear message do not silent us.

With all of this, do you have any more questions or suggestions before moving on and creating the architecture.MD

Show more
Jun 8

Validated pricing, clarified CSV strategy, and prepared architecture documentation
Validated pricing, clarified CSV strategy, and prepared architecture documentation
Hi Clayton.

On the Anthropic spend question: yes, but it's pennies, and you keep the cap anyway.

The LLM calls run through the pay-per-token API. There is no permanent free Claude API tier for production usage. But at MVP scale the numbers are trivial. Current rates: Sonnet 4.6 is $3 input / $15 output per million tokens, Haiku 4.5 is $1 / $5. 
DEV Community
GitHub

Math at 5 reviews in context: a Q&A turn is roughly 1.5k input + 0.3k output on Sonnet, about $0.009. A Haiku theme summary is about $0.003. So $5 buys you ~500 Q&A turns. You will not get near it.

The reason you still keep the $5 cap: it's a public, no-auth endpoint, and per-turn cost scales with how many reviews sit in context. On a 200-review CSV (~25k input tokens) a Q&A turn jumps to about $0.08, and a bot looping your endpoint could chew through that. The cap is cheap insurance, not a real constraint. Prompt caching the corpus drops repeat turns ~10x, and that's the lever I document for scale.

Clarifying "mock CSV" so we don't shoot ourselves in the foot. Three different artifacts, keep them separate:

A downloadable template CSV showing the required columns with obvious example rows. User-facing.
The demo-scale dataset, seeded with a slice of a real public Google review dataset, not fabricated reviews. This protects the trust premise you're graded on.
A synthetic generator that lives only in tests/ for fixtures.
Fabricated reviews never enter the analyst's live corpus. On the to-do list as you said, with that split.

Three things I baked into the file as recommendations, flag any you want pulled:

Q&A answers cite which review(s) grounded them. Cheap at this corpus size, and it's the strongest possible "grounded in reviews only" signal for the Loom and for Johnny.
Prompt-cache the corpus and system prompt per place_id. Cost and latency win on repeat questions.
Rate-limit defaults: 10 ingests/hour/IP, 30 questions/hour/IP.
No blocking questions left. Architecture locked. Here it is.

markdown
# ReviewLens AI — Architecture

Status: locked for MVP build. Owner: Clayton Cuteri.
This document is the source of truth for why each choice was made and what triggers a change at scale. Read before coding. See `/docs/plans/` for execution plans, `CLAUDE.md` and `AGENTS.md` for agent conventions.

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
- CSV path: upload reviews into the same normalized schema. The brief explicitly permits user-supplied data. This is how the product is demonstrated at real scale, free, using a real public Google review dataset.
Both paths write one normalized schema (section 5). Adding a managed scraper later is a third source behind the same interface.
Alternatives: third-party scraper now (rejected for MVP: cost, self-funded, free-first directive); synthetic injector (rejected: fabricated reviews undermine the grounding/trust premise the product is graded on).
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

CSV template columns: `rating` (required, 1-5), `text` (required), `author` (optional), `date` (optional ISO), `language` (optional). Rows missing required fields are reported, not silently dropped.

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
- Cost and abuse on the public endpoint: per-IP rate limits (10 ingests/hour, 30 questions/hour), URL validation, and `place_id` caching so repeat views and questions on a cached entity do not re-bill.

## 8. Cost and scaling

Rates (current): Sonnet 4.6 $3 / $15 per million input/output tokens; Haiku 4.5 $1 / $5. Google Places stays inside the standing free credit at demo volume. No permanent free API tier; pay per token.

Per-request cost by corpus size (Q&A on Sonnet, ~300-token answer):

|
 Corpus in context 
|
 Input tokens 
|
 Cost / Q&A turn 
|
 $5 buys 
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
 5 reviews (API) 
|
 ~1.5k 
|
 ~$0.009 
|
 ~500 turns 
|
|
 200 reviews (CSV) 
|
 ~25k 
|
 ~$0.08 
|
 ~60 turns 
|
|
 10k reviews (no retrieval) 
|
 ~1.3M 
|
 does not fit / dollars per turn 
|
 not viable 
|

Where cost appears as the product scales, and the lever for each:
- More reviews per entity raises per-turn input cost linearly while the corpus is passed whole. Lever: prompt caching of the corpus and system prompt (~10x cheaper on repeat turns) buys headroom into the low thousands.
- Past a few hundred reviews, switch `get_context` to `rag-core` retrieval (top-k, ~12 reviews per turn). Per-turn input returns to cents regardless of total corpus size. This is the single most important scale lever and the reason the retrieval seam exists from day one.
- More entities and traffic raises total volume. Levers: Haiku for routing/classification, batch processing for any offline summarization, and per-tenant quotas once auth exists.

The 0-to-scale story in one line: in-context at MVP (free to cents), caching into the thousands, retrieval past that, managed scraper when the 5-review API is the bottleneck, all behind interfaces that exist now.

## 9. Security and abuse

Public, no auth, by requirement. Mitigations: rate limits (section 7), strict URL and CSV validation, secrets in the host vault, delimiter-isolated review text so user-generated content cannot inject instructions, and a hard spend cap in the Anthropic console.

## 10. Repo conventions

    /docs/plans/        execution plans, written before code
    ARCHITECTURE.md     this file
    CLAUDE.md           agent operating notes
    AGENTS.md           agent conventions (build, test, run)
    /ai-transcripts/    unedited AI session logs, including dead ends
    tests/              includes the synthetic review generator (fixtures only)

## 11. Roadmap

Post-MVP, in priority order:
1. Managed scraper as a third ingestion source for entities beyond the API's 5.
2. `rag-core` retrieval plus a vector store, triggered by corpus size.
3. Multi-platform ingestion (Amazon, G2, Capterra) behind the existing interface, with a per-platform toggle.
4. `mod-guard` as an ingestion-time content-moderation layer.
5. Translation layer for multilingual corpora.
6. Auth and multi-tenancy, per-tenant quotas and cost attribution.
That's the defensible baseline. Tell me which of the three flagged recommendations you want kept, and whether you want this at repo root as ARCHITECTURE.md or under /docs/. Once you bless it, the next artifact is the /docs/plans/ build plan Claude Code executes against.

Yeah, give them a downloadable CSV, but they can fill out for themselves so that if they do not have enough reviews, they can always add reviews for themselves

I'm also saying a mock CSV that we create so that we can just inject that so that we get more review sediment so that we're able to get and test the MVP - these will be fabricated reviews, but good for testing. should be able to be deleted in the future

I like your idea of saying which Q&A answers dictated the response I think that's good to give a live feedback

prompt caching is good

rate limit is good too. They should not be speed running it and protects us from malicious actors looking to burn our tokens. please mention the rate limits once a user starts getting close it just like a warning

If this influences the architecture MD file at all, please say so

Show more
Jun 8

Reconciled synthetic test data with product integrity guardrails
Reconciled synthetic test data with product integrity guardrails
Hi Clayton.

Confirmations: user-fillable template CSV, answer citations, prompt caching, and rate limits all locked. Citations and caching were already in the file, so no change there.

Two things do change the file, and one is a guardrail worth stating plainly.

The rate-limit warning is a real addition. The file now specifies graceful behavior: every response returns remaining quota for the window, the UI warns when a user is close instead of blocking silently, and the hard block comes with a clear reset time. Implementation stays simple, an in-memory per-IP fixed-window counter on the single instance.

The mock CSV gets reframed, not removed. A synthetic sample CSV for testing the pipeline at volume is fine and now lives in tests/fixtures/, labeled, uploaded through the normal CSV path, deletable without touching anything else. What stays rejected is a synthetic injector as a product feature. The one guardrail: do not let fabricated data read as real in the Loom. Use a real public dataset for the scale beat, or if you show the synthetic file, say on screen that it is synthetic test data and not a real entity's reviews. The URL path with 5 real Google reviews carries the "this is real ingestion" moment; the synthetic CSV is for proving the pipeline scales, not for implying real analysis. Johnny will respect the honesty and would penalize the opposite.

Updated file below. Changes are in 4.2, 5, 7, and 10.

markdown
# ReviewLens AI — Architecture

Status: locked for MVP build. Owner: Clayton Cuteri.
This document is the source of truth for why each choice was made and what triggers a change at scale. Read before coding. See `/docs/plans/` for execution plans, `CLAUDE.md` and `AGENTS.md` for agent conventions.

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

|
 Corpus in context 
|
 Input tokens 
|
 Cost / Q&A turn 
|
 $5 buys 
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
 5 reviews (API) 
|
 ~1.5k 
|
 ~$0.009 
|
 ~500 turns 
|
|
 200 reviews (CSV) 
|
 ~25k 
|
 ~$0.08 
|
 ~60 turns 
|
|
 10k reviews (no retrieval) 
|
 ~1.3M 
|
 does not fit / dollars per turn 
|
 not viable 
|

Where cost appears as the product scales, and the lever for each:
- More reviews per entity raises per-turn input cost linearly while the corpus is passed whole. Lever: prompt caching of the corpus and system prompt (~10x cheaper on repeat turns) buys headroom into the low thousands.
- Past a few hundred reviews, switch `get_context` to `rag-core` retrieval (top-k, ~12 reviews per turn). Per-turn input returns to cents regardless of total corpus size. This is the single most important scale lever and the reason the retrieval seam exists from day one.
- More entities and traffic raises total volume. Levers: Haiku for routing/classification, batch processing for any offline summarization, and per-tenant quotas once auth exists.

The 0-to-scale story in one line: in-context at MVP (free to cents), caching into the thousands, retrieval past that, managed scraper when the 5-review API is the bottleneck, all behind interfaces that exist now.

## 9. Security and abuse

Public, no auth, by requirement. Mitigations: rate limits with proximity warnings (section 7), strict URL and CSV validation, secrets in the host vault, delimiter-isolated review text so user-generated content cannot inject instructions, and a hard spend cap in the Anthropic console.

## 10. Repo conventions

    /docs/plans/        execution plans, written before code
    ARCHITECTURE.md     this file
    CLAUDE.md           agent operating notes
    AGENTS.md           agent conventions (build, test, run)
    /ai-transcripts/    unedited AI session logs, including dead ends
    tests/              unit and integration tests
    tests/fixtures/     synthetic sample CSV (labeled, deletable)

## 11. Roadmap

Post-MVP, in priority order:
1. Managed scraper as a third ingestion source for entities beyond the API's 5.
2. `rag-core` retrieval plus a vector store, triggered by corpus size.
3. Multi-platform ingestion (Amazon, G2, Capterra) behind the existing interface, with a per-platform toggle.
4. `mod-guard` as an ingestion-time content-moderation layer.
5. Translation layer for multilingual corpora.
6. Auth and multi-tenancy, per-tenant quotas and cost attribution.
Root or /docs/? Still your call. Next artifact when you're ready is the /docs/plans/ build plan Claude Code executes against.

we should put this into the /docs/plans/ folder… i will add this file to the project so that we have it when we prompt claude code. so please make this into an md file that i can add to the project

Jun 8

Prepared architecture file for project integration with minor accuracy adjustments
Prepared architecture file for project integration with minor accuracy adjustments
Hi Clayton. Made two small accuracy edits so the file is correct living in /docs/plans/: the title no longer uses an em dash, and section 10 now reflects that this doc is the architecture plan inside /docs/plans/ rather than a root file. Content is otherwise the locked version.


Created a file, read a file
Created a file, read a file
Drop it at /docs/plans/architecture.md. When you point Claude Code at it, have it read this plus CLAUDE.md and AGENTS.md before writing anything, and write the execution plan to /docs/plans/ first. Ready for that build plan whenever you are.


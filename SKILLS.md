# SKILLS.md — Plan & Approach

*Pre-work planning notes, written before the first line of code. Captures the
problem, the approach, the stack (and why), the build milestones, the skills the
project leans on, and the risks I expected going in.*

---

## 1. The problem & the insight

People save hundreds of travel reels and never go anywhere. A saved reel is
*intent*; a trip is a hundred boring decisions (which places, what order, how
many days, where to stay, what it costs, what to book). The friction between the
two is where the intent dies.

**The product is the layer that removes that friction:** one link in → three
costed, bookable day-by-day trips out. The hard part isn't the UI — it's
(a) extracting the *right* places from messy reel content, (b) inferring a
persona from a few questions, and (c) making the trip actually match the reel.

## 2. Approach

Build it as a **linear pipeline of small, testable services**, each doing one
thing, wired by a thin API layer. Keep the LLM to what it's good at (reading and
arranging) and make anything that must be *correct* (costs) deterministic.

```
Fetch → Extract (LLM) → Resolve (Places) → Persona → Generate → Cost → Tours → Persist
```

## 3. Tech stack & rationale

| Layer | Choice | Why |
|-------|--------|-----|
| Backend | FastAPI (async) | Pipeline is I/O-bound (OpenAI, YouTube, Places); async overlaps calls cheaply |
| LLM | OpenAI `gpt-4o-mini`, JSON mode | Cheap + strong at entity extraction and geographic grouping; provider swappable via `OPENAI_BASE_URL` |
| Places | Google Places API (New) | Real coords, category, price tier; graceful mock fallback |
| Ingestion | youtube-transcript-api, YouTube Data API, instaloader/yt-dlp | Cover both platforms; caption-only for IG (no media download) |
| Storage | SQLite (aiosqlite) | Brief says lightweight is fine; zero-ops, swappable for Postgres |
| Cache | Redis (optional) | Repeat URLs skip the whole pipeline — the main cost lever |
| Frontend | React + Vite | Fast dev, simple proxy to API, no build step to iterate |
| Tours | Mock catalogue (JSON) | No GYG/Viator key in window; matching logic still real |

## 4. Milestones (mapped to the brief's F-01…F-06)

| M | Goal | Feature |
|---|------|---------|
| M1 | Scaffold, config, DB, cache, health | infra |
| M2 | Ingest YouTube + Instagram content | F-01 |
| M3 | LLM place extraction + Places validation | F-02 |
| M4 | Persona capture (4 questions) | F-03 |
| M5 | 3 persona-tuned plans, region-grouped, full coverage | F-04 |
| M6 | Deterministic per-person cost model | F-05 |
| M7 | Per-stop tour matching | F-06 |
| M8 | React SPA over the pipeline | delivery |
| M9 | Docs: README, architecture, test cases, 100K-MAU cost | delivery |

## 5. Skills & tools this leans on

- **LLM prompt engineering** — structured JSON extraction, geographic-grouping
  prompts, forcing coverage of every place, and *deliberately keeping costs out
  of the model.*
- **API integration** — OpenAI, Google Places (New) field masks, YouTube Data
  API quota math, live FX, Instagram scraping via cookies.
- **Async Python / FastAPI** — overlapping I/O, background persistence.
- **Data modelling & caching** — SQLite persistence, Redis cache keys + TTLs,
  a place-level cache to cut the dominant Places cost.
- **Cost modelling** — deterministic per-person estimation (flight tiers, room
  sharing) and a back-of-envelope 100K-MAU analysis.
- **Frontend** — React SPA, state machine across 6 screens, design-token theming.
- **AI-assisted workflow** — using Claude Code to scaffold, refactor and test
  quickly, with `CLAUDE.md` encoding the rules so the assistant stays on-spec
  (e.g. "never let the LLM invent numbers").

## 6. Risks & mitigations (anticipated up front)

| Risk | Mitigation |
|------|------------|
| Reel captions are thin / name no venues | Capture the *destination* and suggest highlights instead of returning empty |
| LLM invents unreliable costs | Costs are deterministic; LLM never prices |
| Instagram blocks anonymous access | `cookies.txt` support; clear error when unauthenticated |
| Google Places is expensive at scale | Aggressive URL + place caching (see COST_ESTIMATE.md) |
| Missing API keys break local runs | Every external dependency has a graceful fallback |
| LLM drops places from the itinerary | Post-generation coverage net re-inserts them |

## 7. Definition of success

A reviewer can `clone → install → run`, paste a real reel, and get three
sensible, costed itineraries whose stops genuinely come from that reel — with
honest behaviour when the content has nothing to extract.

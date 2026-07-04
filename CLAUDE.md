# CLAUDE.md — Project Guide

Working notes and rules for building **Reel → Itinerary**. This is the file an
AI pair-programmer (or a new contributor) should read first: what we're building,
how the repo is laid out, how to run it, and the non-negotiable engineering
rules that keep the output trustworthy.

---

## What we're building

The intelligence layer between *"I saved this reel"* and *"I booked this trip."*
User pastes a YouTube/Instagram link → we extract the real places + vibe → capture
a short travel persona → generate 2–3 costed, day-by-day trip plans with matched
tours. The brief is explicit that this is **not a UI exercise** — extraction
quality, persona logic, and trip↔content match are what matter.

## The intended pipeline

```
URL → Fetch (transcript/caption/meta) → LLM extract (places + vibe)
    → Google Places validate → Persona (4 Qs)
    → Generate 3 plans (region-grouped) → Cost (deterministic) → Tours → persist
```

Each arrow is one single-responsibility service under `backend/app/services/`.

## Repo layout

```
backend/   FastAPI app (app/), tests/, data/, requirements.txt, Dockerfile, .env
frontend/  React + Vite SPA
*.md       README, ARCHITECTURE, COST_ESTIMATE, TEST_CASES, SKILLS
```

## How to run

```bash
# backend
cd backend && python -m venv venv && source venv/bin/activate
pip install -r requirements.txt && cp .env.example .env   # fill keys
uvicorn app.main:app --reload --port 8000

# frontend (new terminal)
cd frontend && npm install && npm run dev   # :5173, proxies /api → :8000

# tests
cd backend && pytest -q
```

## Engineering rules (non-negotiable)

1. **The LLM extracts and arranges. It never produces money.** All costs come
   from the deterministic model in `services/cost_estimator.py`. If a number
   would ever come from the model, that's a bug. Numbers must be reproducible.
2. **One responsibility per service.** `content_fetcher`, `llm_extractor`,
   `places_resolver`, `trip_generator`, `cost_estimator`, `tour_recommender` —
   each is independently callable and unit-tested. Routes only orchestrate.
3. **Degrade, don't break.** No Redis → no cache. No Places key → mock
   enrichment. No transcript → description only. No places found → an honest
   `no_places_found` response, never a fabricated trip.
4. **Persona must actually change the output.** Pace → stops/day; group + party
   size → room-sharing cost; budget → recommended plan. If an onboarding answer
   changes nothing downstream, it's dead weight — wire it or cut it.
5. **Cover every extracted place.** The generator must place every input place;
   a coverage net re-inserts any the LLM drops. Never silently lose a place.
6. **Cache to protect the wallet.** Google Places is ~90% of cost at scale, so
   cache by URL (whole pipeline) and by place (individual lookups).
7. **Secrets stay in `.env`** (gitignored). `cookies.txt` is a live credential —
   never commit it.

## Definition of done (per feature)

- F-01 Ingestion: YouTube + Instagram both return `{title, description, transcript, tags}`.
- F-02 Extraction: specific places out, each validated (or gracefully mocked) against Places.
- F-03 Persona: 4 questions captured and threaded into generation.
- F-04 Plans: 3 distinct persona-tuned itineraries, region-grouped, all places covered.
- F-05 Cost: per-person breakdown (flights/stay/food/transport/activities), deterministic.
- F-06 Tours: 1–2 matched tours per stop with price + duration.
- Every feature has a test; `pytest` stays green.

## Commit style

Conventional commits (`feat:`, `fix:`, `test:`, `docs:`, `chore:`), scoped by
area (`feat(trips): …`). Small, feature-wise commits — the history should read
as a build, not a dump.

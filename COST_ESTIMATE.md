# Cost Estimate — 100K Monthly Active Users

Back-of-the-envelope API cost model for running Reel → Itinerary at 100K MAU,
using **real 2026 rates** (sources at the bottom). Every number is derived from
the assumptions in §1 so you can re-run the math with your own inputs.

**Headline:** at 100K MAU the variable cost is **~$7.5K–$11K/month (~$0.08–$0.11
per MAU)**, and **Google Places is ~90% of it**. The LLM — despite doing the
"smart" work — is under $600/month because gpt-4o-mini is cheap. So the entire
cost story is: *cache place lookups aggressively.*

---

## 1. Assumptions

| Assumption | Value | Why |
|------------|-------|-----|
| MAU | 100,000 | Given |
| Extractions / user / month | 2 | Casual planners save more than they process |
| Total extraction requests / month | 200,000 | 100K × 2 |
| **URL cache hit rate** | 50% | Saved reels skew to popular/viral videos that many users share |
| Full-pipeline runs / month | **100,000** | 200K × (1 − 0.5); cached URLs cost ≈ $0 (Redis) |
| Places / extraction | 6 | Typical travel vlog |
| **Place-lookup cache hit rate** | 40% | Landmarks repeat heavily (everyone's Bali reel hits Uluwatu) |
| LLM calls / run | 1 extraction + 2 generation | The UI reveals places (call 1) then regenerates for the chosen persona (call 2). Collapsible to 1 — see §6. |

---

## 2. Unit economics (per full pipeline run)

### LLM tokens — gpt-4o-mini @ $0.15/1M in, $0.60/1M out

| Call | Tokens in | Tokens out | Cost |
|------|-----------|-----------|------|
| Place extraction | 3,500 | 800 | $0.00101 |
| Trip generation ×2 | 5,000 | 7,000 | $0.00495 |
| **Per run** | **8,500** | **7,800** | **≈ $0.006** |

Output tokens (the 3-plan JSON) dominate — that's where ~80% of the LLM cost is.

### Google Places — Text Search (New) @ $32 / 1,000 (≤100K/mo)

- 6 places/run × 60% cache-miss = **3.6 billable Text Searches per run**
- We use a single `searchText` call per place (field mask returns coords +
  category + price tier in one shot) — **no separate Place Details call**.

---

## 3. Monthly cost by service

### LLM — OpenAI gpt-4o-mini
100,000 runs × $0.006 = **≈ $600/month**
(With prompt caching on the large system prompts at $0.075/1M cached-input: ~$550.)

### Google Places API (New) — Text Search
Billable calls = 100,000 runs × 6 places × 60% miss = **360,000 / month**, tiered:

| Volume tier | Calls | Rate / 1,000 | Cost |
|-------------|-------|--------------|------|
| 0–100,000 | 100,000 | $32.00 | $3,200 |
| 100,001–500,000 | 260,000 | $25.60 | $6,656 |
| **Total** | **360,000** | | **≈ $9,850/month** |

(Post-March-2025 free tier is a few thousand calls/SKU/month — negligible here.)

### YouTube Data API v3 — **$0**
`videos.list` = 1 quota unit; transcripts come from `youtube-transcript-api`
(scraping, **not billed**). ~60K YouTube runs/month ≈ 2,000 units/day — well
under the free **10,000 units/day**. At higher scale you request a quota
increase (free). No dollar cost.

### Tour recommendations — **$0**
Mock catalogue (local JSON). A real GetYourGuide/Viator integration is
**affiliate/commission** — it *pays* you per booking, it doesn't charge per call.

### Currency (FX) — **$0**
`open.er-api.com`, free, cached 12h → a handful of calls/day regardless of MAU.

### Infrastructure — ≈ $400/month
Small autoscaling API (Fargate/Cloud Run) + Redis (managed, small) + Postgres
(swap from SQLite at scale) + static frontend on a CDN.

---

## 4. Totals

| Service | Base (40% place cache) | Optimized (§6) |
|---------|------------------------|----------------|
| Google Places | $9,850 | $6,780 |
| LLM (gpt-4o-mini) | $600 | $350 |
| YouTube | $0 | $0 |
| Tours (mock) | $0 | $0 |
| FX | $0 | $0 |
| Infrastructure | $400 | $400 |
| **Total / month** | **≈ $10,850** | **≈ $7,530** |
| **Per MAU** | **≈ $0.109** | **≈ $0.075** |

**Google Places is ~90% of variable cost.** The LLM, YouTube, tours and FX are
rounding error by comparison.

---

## 5. Where the money goes

```
Base scenario (~$10,850/mo)
Google Places    ████████████████████████████████████████  91%
LLM              ██                                          5%
Infrastructure   ██                                          4%
YouTube/Tours/FX ·                                           0%
```

Any cost conversation about this product is really a conversation about **Places
call volume**.

---

## 6. Optimization levers (biggest first)

1. **Cache place lookups harder.** Going from 40% → 60% place-cache hit rate
   drops Places from $9,850 → **$6,780** (−31%). A *global* place cache shared
   across all users (not per-URL) compounds this — the world has a finite number
   of famous landmarks.
2. **Skip Places for low-value mentions.** Only resolve places we'll actually
   put on an itinerary (top-N by relevance), not every extracted mention.
3. **Collapse to one LLM generation call.** Generate the 3 plans once with the
   real persona instead of default-then-regenerate → LLM ≈ $600 → **$350**.
4. **Prompt caching** on the big system prompts → input tokens at $0.075/1M
   instead of $0.15/1M.
5. **URL cache (Redis)** — already assumed at 50%; the highest-leverage cache
   since it skips *the entire pipeline* (LLM + Places) for repeat reels.
6. **Local geocode** well-known cities to avoid a Places call entirely.

Realistic optimized target: **~$7,500/month → $0.075/MAU.**

---

## 7. Scaling

| MAU | Places calls/mo | Est. monthly cost | Per MAU |
|-----|-----------------|-------------------|---------|
| 10K | 36K | ~$1,350 | $0.135 |
| 50K | 180K | ~$4,900 | $0.098 |
| 100K | 360K | ~$7,500 (optimized) | $0.075 |
| 500K | 1.8M | ~$33,000 | $0.066 |
| 1M | 3.6M | ~$62,000 | $0.062 |

Per-MAU cost falls with scale because (a) the global place-cache hit-rate rises
as the catalogue of resolved places saturates, and (b) fixed infra amortizes.
Above ~500K MAU, a Places volume contract or a self-hosted geocoder for hot
places becomes worth it.

---

## Sources (2026)

- OpenAI gpt-4o-mini pricing ($0.15/1M in, $0.60/1M out): [OpenAI API pricing](https://developers.openai.com/api/docs/pricing) · [pricepertoken](https://pricepertoken.com/pricing-page/model/openai-gpt-4o-mini)
- Google Places Text Search (New) ($32/1K; $25.60/1K at 100K+): [Google Maps Platform pricing](https://developers.google.com/maps/billing-and-pricing/pricing) · [SafeGraph guide](https://www.safegraph.com/guides/google-places-api-pricing/) · [Woosmap](https://www.woosmap.com/blog/google-places-api-pricing)
- Places free-tier / March 2025 SKU changes: [Google billing FAQ](https://developers.google.com/maps/billing-and-pricing/faq)
- YouTube Data API v3 quota (10K units/day, `videos.list` = 1 unit): [Quota calculator](https://developers.google.com/youtube/v3/determine_quota_cost)

*Rates verified against public pricing pages in 2026; treat as indicative — providers change pricing and free tiers periodically.*

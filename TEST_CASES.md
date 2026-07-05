# Test Cases

Three documented runs against the real pipeline. Costs are per person in USD
(the frontend converts to the selected display currency). Flight figures are
indicative round-trip by destination tier + cabin class — see
[README → Known Limitations](README.md#known-limitations).

> Note on Google Places: during these runs the Places key returned 403 (the key
> needs "Places API (New)" + billing enabled), so place resolution used the
> graceful mock-enrichment fallback. Trip generation is unaffected — this
> demonstrates the fallback path working as designed.

---

## Case 1 — YouTube travel vlog

**Input**
```
URL:     https://www.youtube.com/watch?v=uQpiQ4nbM-U
Persona: travel_style=comfort · budget_range=mid · group_type=couple · pace=moderate
```

**Extraction output**
- Platform: `youtube`
- Title: *Kerala 7 Nights & 8 Days Itinerary | Kochi, Munnar, Alleppey, Thekkady & Varkala*
- Vibe: `mixed`
- **11 places extracted:** Munnar · Eravikulam National Park · Rose Garden ·
  Mattupatty Dam · Alleppey Backwaters · Athirapally Waterfalls · Kovalam Beach ·
  Varkala Beach · Kanyakumari · Shree Padmanabhaswamy Temple · Jatayu Earth Center

**Generated trip plans (3 days each, per person)**

| Plan | Total | Flights | Hotel | Food | Transport | Activities |
|------|-------|---------|-------|------|-----------|------------|
| Budget Backpacker | **$525** | 382 | 28 | 45 | 15 | 55 |
| Comfort Traveller | **$1,167** | 450 | 132 | 165 | 90 | 330 |
| Luxury Escape | **$4,140** | 1,170 | 660 | 540 | 450 | 1,320 |

**Notes**
- The transcript was Hindi-only, so extraction ran on title + description and
  still recovered 11 places.
- gpt-4o-mini placed 4 of 11 places itself; the coverage safety-net placed the
  remaining 7 by region so **no place is dropped** from the itinerary.
- Flight tier resolved to `regional` (India) — cheaper than the international default.

---

## Case 2 — Instagram reel

Instagram blocks unauthenticated fetches, so `INSTAGRAM_COOKIES_FILE` is set to
an exported `cookies.txt` (see
[README → Instagram setup](README.md#5-instagram-setup-for-reel-urls)); yt-dlp
then fetches the reel headlessly.

**Input** — a real Bali reel:
```
URL:     https://www.instagram.com/reel/DL0DYF4SL45/
Persona: travel_style=comfort · budget_range=mid · group_type=couple · pace=moderate
```

**Extraction output (actual)**
- Platform: `instagram` · Author: `themusegirliee`
- Vibe: `mixed`
- **7 places extracted:** The Medusa Villas Bali · Atlas Beach Club · Uluwatu
  Temple · Sundays Beach Club · Finns Beach Club · Ganesha Dosa · Nusa Penida

**Generated trip plans (per person, USD)**

| Plan | Total |
|------|-------|
| Budget Backpacker | **$505** |
| Comfort Traveller | **$1,047** |
| Luxury Escape | **$3,660** |

**Notes**
- Short, hashtag-heavy reel captions extract well — 7 real Bali places from a
  single reel caption.
- Flight tier resolved to `regional` (Indonesia).
- If `INSTAGRAM_COOKIES_FILE` is not configured, the same request fails cleanly
  with a `422` explaining that Instagram requires login — no fabricated data.

---

## Case 3 — Edge case: reel/video with no places

**Input**
```
URL:     https://www.youtube.com/watch?v=dQw4w9WgXcQ   (a music video)
Persona: travel_style=budget · budget_range=low · group_type=solo · pace=packed
```

**Output**
```json
{
  "status": "no_places_found",
  "platform": "youtube",
  "title": "Rick Astley - Never Gonna Give You Up (Official Video) (4K Remaster)",
  "places": [],
  "trips": [],
  "message": "We couldn't find any specific travel locations in this content.
              Try a travel vlog or reel that mentions real places, cities, or attractions."
}
```

**Notes**
- The system extracts **0 places** and returns an explicit `no_places_found`
  status with a helpful message — it does **not** fabricate an itinerary.
- The Streamlit UI shows a friendly "No places found" screen with a retry action.
- This is the key edge-case behaviour: an honest empty result beats a
  hallucinated trip built from nothing.

---

## Reproducing these

```bash
# Backend
uvicorn app.main:app --port 8000
# Then POST to /api/extract/ with the URL + persona shown above,
# or use the Streamlit UI (streamlit run frontend/app.py).
```

All three scenarios are also covered by the automated test suite
(`pytest -q` → 24 passing), including cost differentiation, pace→stops mapping,
region-preserving day capping, missing-place coverage, and DB persistence.

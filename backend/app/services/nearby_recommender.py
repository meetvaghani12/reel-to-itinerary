"""Surface famous nearby spots the reel *didn't* mention.

The reel only covers what the creator chose to film. Travellers usually want
the obvious anchors too (the headline temple, the museum everyone visits). This
service takes the centre of the already-resolved places and asks Google Places
for the most popular tourist attractions in that radius, then removes anything
we already extracted so the list is purely additive.

Degrades gracefully: no API key or any error → empty list (the UI simply hides
the section), never a fabricated recommendation.
"""

import logging
from app.core.config import get_settings
from app.utils.cache import cache_get, cache_set

logger = logging.getLogger(__name__)
settings = get_settings()

# Popular, tourist-relevant categories. Broad enough to surface the headline
# sights, narrow enough to avoid gas stations / offices.
_INCLUDED_TYPES = [
    "tourist_attraction",
    "historical_landmark",
    "museum",
    "national_park",
    "hindu_temple",
    "church",
]


def _center(resolved: list[dict]) -> tuple[float, float] | None:
    pts = [
        (p["lat"], p["lng"])
        for p in resolved
        if p.get("lat") and p.get("lng") and not (p["lat"] == 0 and p["lng"] == 0)
    ]
    if not pts:
        return None
    return (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))


def _norm(name: str) -> str:
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())


async def recommend_nearby(resolved: list[dict], limit: int = 6) -> list[dict]:
    center = _center(resolved)
    if not center:
        return []

    lat, lng = center
    cache_key = f"nearby:{lat:.3f},{lng:.3f}"
    cached = await cache_get(cache_key)
    if cached is not None:
        logger.info("Nearby recommendations cache hit for %.3f,%.3f", lat, lng)
        recs = cached.get("recs", [])
        return _dedupe_against_reel(recs, resolved, limit)

    if not settings.google_places_api_key:
        logger.warning("No Places key — skipping nearby recommendations")
        return []

    try:
        recs = await _search_nearby(lat, lng)
    except Exception as e:  # noqa: BLE001 — degrade, don't break
        logger.error("Nearby search failed: %s", e)
        return []

    await cache_set(cache_key, {"recs": recs}, ttl=604800)
    return _dedupe_against_reel(recs, resolved, limit)


def _dedupe_against_reel(recs: list[dict], resolved: list[dict], limit: int) -> list[dict]:
    """Remove anything we already extracted from the reel, keep the strongest.

    Uses substring matching so "Tanah Lot" is recognised as the same anchor as
    the reel's "Tanah Lot Temple".
    """
    reel = [_norm(p.get("name", "")) for p in resolved]
    reel = [r for r in reel if r]
    picked: list[str] = []
    out = []
    for r in recs:
        key = _norm(r.get("name", ""))
        if not key:
            continue
        dup = any(key in x or x in key for x in reel + picked)
        if dup:
            continue
        picked.append(key)
        out.append(r)
        if len(out) >= limit:
            break
    return out


async def _search_nearby(lat: float, lng: float) -> list[dict]:
    import httpx

    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.post(
            "https://places.googleapis.com/v1/places:searchNearby",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": settings.google_places_api_key,
                "X-Goog-FieldMask": (
                    "places.id,places.displayName,places.formattedAddress,"
                    "places.location,places.rating,places.userRatingCount,"
                    "places.priceLevel,places.primaryTypeDisplayName,places.types"
                ),
            },
            json={
                "includedTypes": _INCLUDED_TYPES,
                "maxResultCount": 20,
                "rankPreference": "POPULARITY",
                "locationRestriction": {
                    "circle": {
                        "center": {"latitude": lat, "longitude": lng},
                        "radius": 25000.0,
                    }
                },
                "languageCode": "en",
            },
        )
        resp.raise_for_status()
        data = resp.json()

    from app.services.places_resolver import _parse_price_level

    results = []
    for gp in data.get("places", []):
        rating = gp.get("rating")
        # Only surface well-reviewed, genuinely popular anchors.
        if rating is None or rating < 4.0 or gp.get("userRatingCount", 0) < 500:
            continue
        loc = gp.get("location", {})
        results.append({
            "name": gp.get("displayName", {}).get("text", ""),
            "type": gp.get("primaryTypeDisplayName", {}).get("text", "")
            or (gp.get("types", [""])[0].replace("_", " ").title()),
            "rating": rating,
            "rating_count": gp.get("userRatingCount"),
            "price_level": _parse_price_level(gp.get("priceLevel")),
            "address": gp.get("formattedAddress", ""),
            "lat": loc.get("latitude"),
            "lng": loc.get("longitude"),
            "google_place_id": gp.get("id"),
        })

    # Strongest first: rating, then review volume.
    results.sort(key=lambda r: (r["rating"], r.get("rating_count") or 0), reverse=True)
    return results

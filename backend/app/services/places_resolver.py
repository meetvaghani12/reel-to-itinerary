import logging
from app.core.config import get_settings
from app.utils.cache import cache_get_places, cache_set_places

logger = logging.getLogger(__name__)
settings = get_settings()

CATEGORY_MAP = {
    "restaurant": "restaurant",
    "hotel": "lodging",
    "landmark": "tourist_attraction",
    "neighborhood": "neighborhood",
    "activity": "amusement_park",
    "viewpoint": "point_of_interest",
    "market": "market",
    "beach": "natural_feature",
    "temple": "place_of_worship",
    "cafe": "cafe",
    "bar": "bar",
    "museum": "museum",
}


async def resolve_places(raw_places: list[dict]) -> list[dict]:
    resolved = []
    for place in raw_places:
        enriched = await _resolve_single_place(place)
        resolved.append(enriched)
    return resolved


async def _resolve_single_place(place: dict) -> dict:
    query = f"{place.get('name', '')} {place.get('estimated_location', '')}"
    cached = await cache_get_places(query)
    if cached:
        logger.info(f"Cache hit for place: {place.get('name')}")
        return cached

    if not settings.google_places_api_key:
        logger.warning("Google Places API key not set, using enriched mock data")
        result = _enrich_without_api(place)
        await cache_set_places(query, result)
        return result

    try:
        result = await _resolve_with_google_places(place)
        await cache_set_places(query, result)
        return result
    except Exception as e:
        logger.error(f"Google Places resolution failed for {place.get('name')}: {e}")
        result = _enrich_without_api(place)
        await cache_set_places(query, result)
        return result


async def _resolve_with_google_places(place: dict) -> dict:
    import httpx

    search_query = f"{place.get('name', '')} {place.get('estimated_location', '')}"

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": settings.google_places_api_key,
                "X-Goog-FieldMask": "places.id,places.displayName,places.formattedAddress,places.location,places.rating,places.priceLevel,places.types,places.primaryType",
            },
            json={"textQuery": search_query, "languageCode": "en"},
        )
        resp.raise_for_status()
        data = resp.json()

        places = data.get("places", [])
        if not places:
            return _enrich_without_api(place)

        gp = places[0]
        location = gp.get("location", {})

        return {
            **place,
            "lat": location.get("latitude"),
            "lng": location.get("longitude"),
            "rating": gp.get("rating"),
            "price_level": _parse_price_level(gp.get("priceLevel")),
            "google_place_id": gp.get("id"),
            "google_types": gp.get("types", []),
            "formatted_address": gp.get("formattedAddress"),
        }


def _parse_price_level(level: str | None) -> int | None:
    mapping = {
        "PRICE_LEVEL_FREE": 0,
        "PRICE_LEVEL_INEXPENSIVE": 1,
        "PRICE_LEVEL_MODERATE": 2,
        "PRICE_LEVEL_EXPENSIVE": 3,
        "PRICE_LEVEL_VERY_EXPENSIVE": 4,
    }
    return mapping.get(level) if level else None


def _enrich_without_api(place: dict) -> dict:
    category = CATEGORY_MAP.get(place.get("type", ""), "point_of_interest")

    est_loc = place.get("estimated_location", "").lower()
    coords = _estimate_coords(est_loc)

    return {
        **place,
        "lat": coords.get("lat"),
        "lng": coords.get("lng"),
        "rating": None,
        "price_level": None,
        "google_place_id": None,
        "google_types": [category],
        "formatted_address": place.get("estimated_location", ""),
    }


def _estimate_coords(location: str) -> dict:
    coords_map = {
        "paris, france": {"lat": 48.8566, "lng": 2.3522},
        "tokyo, japan": {"lat": 35.6762, "lng": 139.6503},
        "bali, indonesia": {"lat": -8.3405, "lng": 115.0920},
        "bangkok, thailand": {"lat": 13.7563, "lng": 100.5018},
        "new york, usa": {"lat": 40.7128, "lng": -74.0060},
        "new york, united states": {"lat": 40.7128, "lng": -74.0060},
        "barcelona, spain": {"lat": 41.3874, "lng": 2.1686},
        "rome, italy": {"lat": 41.9028, "lng": 12.4964},
        "london, uk": {"lat": 51.5074, "lng": -0.1278},
        "london, united kingdom": {"lat": 51.5074, "lng": -0.1278},
    }
    for key, coords in coords_map.items():
        if key in location:
            return coords
    return {"lat": 0.0, "lng": 0.0}

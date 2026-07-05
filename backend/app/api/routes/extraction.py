import uuid
from fastapi import APIRouter
from app.schemas.extraction import ExtractRequest, ExtractionResponse, PlaceExtracted
from app.services.content_fetcher import fetch_content
from app.services.llm_extractor import extract_places
from app.services.places_resolver import resolve_places
from app.services.trip_generator import generate_trips
from app.services.cost_estimator import estimate_costs
from app.services.tour_recommender import recommend_tours_for_trip_sync
from app.utils.cache import cache_get, cache_set
from app.models.repository import save_extraction_result
from collections import Counter
import hashlib
import json
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# Maps a generated plan's persona angle to (travel_style, budget_range) for the
# deterministic cost estimator. Keeps the three plans meaningfully distinct.
PLAN_PERSONA_MAP = {
    "budget_backpacker": ("budget", "low"),
    "comfort_traveller": ("comfort", "mid"),
    "luxury_escape": ("luxury", "high"),
}


def _infer_destination(resolved: list[dict]) -> str:
    """Pick the most common location string across resolved places, used only
    to choose an indicative flight tier."""
    locs = [
        (p.get("estimated_location") or p.get("formatted_address") or "").strip()
        for p in resolved
    ]
    locs = [l for l in locs if l and l.lower() != "unknown"]
    if not locs:
        return ""
    return Counter(locs).most_common(1)[0][0]


def _make_persona_key(persona: dict) -> str:
    key_data = {
        "travel_style": persona.get("travel_style", "comfort"),
        "budget_range": persona.get("budget_range", "mid"),
        "group_type": persona.get("group_type", "solo"),
        "party_size": persona.get("party_size", 1),
        "origin": persona.get("origin", ""),
        "pace_preference": persona.get("pace_preference", "moderate"),
    }
    return hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()


@router.post("/", response_model=ExtractionResponse)
async def extract_from_url(request: ExtractRequest):
    content_cache_key = f"content:{request.url}"
    persona_key = _make_persona_key(request.persona.model_dump())
    trip_cache_key = f"trips:{request.url}:{persona_key}"

    cached_trips = await cache_get(trip_cache_key)
    if cached_trips:
        logger.info(f"Trip cache hit for {request.url} with persona {persona_key}")
        return ExtractionResponse(**cached_trips)

    logger.info(f"Processing URL: {request.url}")

    cached_content = await cache_get(content_cache_key)
    if cached_content:
        logger.info(f"Content cache hit for {request.url}")
        raw_content = cached_content.get("raw_content")
        extracted = cached_content.get("extracted")
        resolved = cached_content.get("resolved")
    else:
        raw_content = await fetch_content(request.url)

        extracted = await extract_places(
            title=raw_content.get("title", ""),
            description=raw_content.get("description", ""),
            transcript=raw_content.get("transcript", ""),
        )

        resolved = await resolve_places(extracted.get("places", []))

        await cache_set(content_cache_key, {
            "raw_content": raw_content,
            "extracted": extracted,
            "resolved": resolved,
        }, ttl=604800)

    # Edge case: no recognisable places (e.g. a music video or a reel with no
    # locations). Don't fabricate an itinerary from nothing — return a clear,
    # honest empty result instead.
    real_places = [
        p for p in resolved
        if p.get("name") and p.get("name", "").lower() != "unknown destination"
    ]
    if not real_places:
        logger.info("No places extracted from %s — returning empty result", request.url)
        return ExtractionResponse(
            extraction_id=str(uuid.uuid4())[:8],
            status="no_places_found",
            platform=raw_content.get("platform", "unknown"),
            title=raw_content.get("title"),
            places=[],
            vibe=extracted.get("vibe", ""),
            trips=[],
            total_cost_per_person=0,
            message=(
                "We couldn't find any specific travel locations in this content. "
                "Try a travel vlog or reel that mentions real places, cities, or attractions."
            ),
        )

    user_persona = request.persona.model_dump()

    trips = await generate_trips(
        places=resolved,
        vibe=extracted.get("vibe", "cultural"),
        persona=user_persona,
    )

    destination = _infer_destination(resolved)

    for trip in trips:
        # The plan's own angle drives style/budget; the user's captured
        # group_type still influences the numbers (room sharing). Costs are
        # computed deterministically in USD — the LLM's numbers are ignored.
        style, budget = PLAN_PERSONA_MAP.get(
            trip.get("persona", "comfort_traveller"), ("comfort", "mid")
        )
        cost_persona = {
            "travel_style": style,
            "budget_range": budget,
            "group_type": user_persona.get("group_type", "solo"),
            "party_size": user_persona.get("party_size", 1),
            "origin": user_persona.get("origin", ""),
        }
        cost = await estimate_costs(
            trip=trip, persona=cost_persona, destination=destination
        )
        trip["cost_breakdown"] = {
            "flights": cost["flights"],
            "accommodation": cost["accommodation"],
            "food": cost["food"],
            "transport": cost["transport"],
            "activities": cost["activities"],
        }
        trip["total_cost_per_person"] = cost["total_per_person"]

        # Tours come from the mock catalogue only (spec-compliant). Google
        # Places returns POIs, not bookable tours, so it is not used here.
        trip["tours"] = recommend_tours_for_trip_sync(
            trip_days=trip.get("days", []),
            persona=trip.get("persona", "comfort_traveller"),
            budget_range=request.persona.budget_range,
        )

    places_out = []
    for p in resolved:
        places_out.append(PlaceExtracted(
            name=p.get("name", ""),
            type=p.get("type", ""),
            description=p.get("description", ""),
            estimated_location=p.get("estimated_location", ""),
            activity_type=p.get("activity_type", ""),
            duration=p.get("duration", ""),
            lat=p.get("lat"),
            lng=p.get("lng"),
            rating=p.get("rating"),
            price_level=p.get("price_level"),
            address=p.get("formatted_address") or "",
        ))

    extraction_id = str(uuid.uuid4())[:8]

    response = ExtractionResponse(
        extraction_id=extraction_id,
        status="completed",
        platform=raw_content.get("platform", "unknown"),
        title=raw_content.get("title"),
        places=places_out,
        vibe=extracted.get("vibe", ""),
        trips=trips,
        total_cost_per_person=trips[0].get("total_cost_per_person", 0) if trips else 0,
    )

    await cache_set(trip_cache_key, response.model_dump())

    # Persist to SQLite (best-effort; never blocks the response).
    await save_extraction_result(
        extraction_id=extraction_id,
        url=request.url,
        raw_content=raw_content,
        extracted=extracted,
        resolved=resolved,
        trips=trips,
    )

    return response

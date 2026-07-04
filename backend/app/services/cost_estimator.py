"""Deterministic, auditable cost estimation.

This is the SINGLE source of truth for trip costs. The LLM is not trusted to
produce numbers — it only proposes the itinerary (places, days, activities).
All monetary values here are computed in USD; the frontend handles display
currency conversion.

Cost model (all per person, USD):
    flights        indicative round-trip, by destination flight tier + class
    accommodation  per-night rate * nights, adjusted for group room-sharing
    food           per-day rate * days
    transport      per-day rate * days
    activities     per-stop rate * number of stops
"""
import logging

logger = logging.getLogger(__name__)

# Indicative round-trip ECONOMY airfare (USD) by flight tier. Origin is unknown
# for a take-home, so we treat these as "typical indicative" fares and scale by
# cabin class below. Documented assumption, not a precise quote.
FLIGHT_TIER_BASE = {
    "domestic": 180,
    "regional": 450,
    "international": 850,
}

# Cabin/service class multiplier applied on top of the tier base.
FLIGHT_CLASS_MULT = {
    "budget": 0.85,    # basic economy, budget carrier
    "comfort": 1.0,    # standard economy
    "luxury": 2.6,     # premium economy / business
}

ACCOMMODATION_PER_NIGHT = {
    "budget": {"low": 25, "mid": 50, "high": 100},
    "comfort": {"low": 60, "mid": 120, "high": 250},
    "luxury": {"low": 180, "mid": 350, "high": 600},
}

FOOD_PER_DAY = {
    "budget": {"low": 15, "mid": 25, "high": 40},
    "comfort": {"low": 30, "mid": 55, "high": 85},
    "luxury": {"low": 70, "mid": 110, "high": 180},
}

TRANSPORT_PER_DAY = {
    "budget": {"low": 5, "mid": 10, "high": 20},
    "comfort": {"low": 15, "mid": 30, "high": 60},
    "luxury": {"low": 40, "mid": 80, "high": 150},
}

ACTIVITY_PER_STOP = {
    "budget": {"low": 5, "mid": 10, "high": 20},
    "comfort": {"low": 15, "mid": 30, "high": 50},
    "luxury": {"low": 35, "mid": 65, "high": 120},
}

# Rooms hold up to this many people; per-person accommodation = rooms / people.
ROOM_CAPACITY = 2

# Fallback party size when an exact headcount isn't supplied.
DEFAULT_PARTY_SIZE = {"solo": 1, "couple": 2, "family": 3, "friends": 2}

# Destination country -> flight tier. Everything not listed defaults to
# "international" (the honest default when the traveller's origin is unknown).
# Intentionally small and transparent — this is an indicative model, not a fare
# search.
COUNTRY_TIER_HINTS = {
    "india": "regional",
    "thailand": "regional",
    "indonesia": "regional",
    "japan": "regional",
    "singapore": "regional",
    "france": "international",
    "italy": "international",
    "spain": "international",
    "united kingdom": "international",
    "uk": "international",
    "usa": "international",
    "united states": "international",
}


def _flight_tier(destination: str) -> str:
    dest = (destination or "").lower()
    for hint, tier in COUNTRY_TIER_HINTS.items():
        if hint in dest:
            return tier
    return "international"


async def estimate_costs(
    trip: dict,
    persona: dict,
    destination: str = "",
) -> dict:
    """Compute a per-person USD cost breakdown for a single trip plan.

    `persona` carries travel_style / budget_range / group_type. The plan's own
    persona (budget_backpacker / comfort_traveller / luxury_escape) is mapped to
    travel_style/budget_range by the caller so the three plans stay meaningfully
    distinct, while the user's captured group_type still influences room-sharing.
    """
    travel_style = persona.get("travel_style", "comfort")
    budget_range = persona.get("budget_range", "mid")
    group_type = persona.get("group_type", "solo")
    party_size = int(persona.get("party_size") or DEFAULT_PARTY_SIZE.get(group_type, 1))
    party_size = max(1, party_size)

    days = trip.get("days", [])
    num_days = max(1, len(days))
    num_nights = max(1, num_days - 1)
    num_stops = max(1, sum(len(day.get("stops", [])) for day in days))

    style_key = travel_style if travel_style in ACCOMMODATION_PER_NIGHT else "comfort"
    budget_key = budget_range if budget_range in FOOD_PER_DAY[style_key] else "mid"

    tier = _flight_tier(destination)
    flights = round(FLIGHT_TIER_BASE[tier] * FLIGHT_CLASS_MULT.get(style_key, 1.0))

    # Room-sharing: the group needs ceil(people / capacity) rooms; the nightly
    # room cost is split across everyone, so per-person accommodation drops as
    # the party grows (until another room is needed). Flights/food/activities
    # stay per-person and are unaffected by headcount.
    rooms = -(-party_size // ROOM_CAPACITY)  # ceil
    accommodation = round(
        ACCOMMODATION_PER_NIGHT[style_key][budget_key] * num_nights * rooms / party_size
    )

    food = round(FOOD_PER_DAY[style_key][budget_key] * num_days)
    transport = round(TRANSPORT_PER_DAY[style_key][budget_key] * num_days)
    activities = round(ACTIVITY_PER_STOP[style_key][budget_key] * num_stops)

    total = flights + accommodation + food + transport + activities

    logger.info(
        "Cost est: style=%s budget=%s group=%s party=%s rooms=%s tier=%s days=%s stops=%s -> $%s",
        style_key, budget_key, group_type, party_size, rooms, tier, num_days, num_stops, total,
    )

    return {
        "flights": flights,
        "accommodation": accommodation,
        "food": food,
        "transport": transport,
        "activities": activities,
        "total_per_person": total,
        "currency": "USD",
        "flight_tier": tier,
    }

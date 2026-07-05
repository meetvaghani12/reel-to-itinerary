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
import math

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


# Coarse coordinates for origin/destination resolution — no Google Places
# dependency. City match wins over country. Extend freely; unknown places fall
# back to the destination tier below.
_CITY_COORDS = {
    "mumbai": (19.08, 72.88), "delhi": (28.61, 77.21), "bengaluru": (12.97, 77.59),
    "bangalore": (12.97, 77.59), "goa": (15.30, 74.12), "chennai": (13.08, 80.27),
    "kolkata": (22.57, 88.36), "hyderabad": (17.39, 78.49), "ahmedabad": (23.02, 72.57),
    "kochi": (9.93, 76.27), "munnar": (10.09, 77.06), "jaipur": (26.91, 75.79),
    "london": (51.51, -0.13), "paris": (48.85, 2.35), "zurich": (47.37, 8.54),
    "geneva": (46.20, 6.14), "rome": (41.90, 12.50), "barcelona": (41.39, 2.17),
    "amsterdam": (52.37, 4.90), "berlin": (52.52, 13.40),
    "new york": (40.71, -74.01), "san francisco": (37.77, -122.42), "los angeles": (34.05, -118.24),
    "dubai": (25.20, 55.27), "abu dhabi": (24.45, 54.38), "doha": (25.29, 51.53),
    "singapore": (1.35, 103.82), "bangkok": (13.75, 100.50), "bali": (-8.41, 115.19),
    "denpasar": (-8.67, 115.22), "tokyo": (35.68, 139.69), "kyoto": (35.01, 135.77),
    "sydney": (-33.87, 151.21), "istanbul": (41.01, 28.98),
}
_COUNTRY_COORDS = {
    "india": (22.0, 79.0), "united states": (39.0, -98.0), "usa": (39.0, -98.0),
    "united kingdom": (54.0, -2.0), "uk": (54.0, -2.0), "france": (46.6, 2.2),
    "switzerland": (46.8, 8.2), "germany": (51.2, 10.4), "italy": (42.8, 12.6),
    "spain": (40.0, -3.7), "netherlands": (52.1, 5.3), "japan": (36.2, 138.3),
    "thailand": (15.0, 101.0), "indonesia": (-2.5, 118.0), "singapore": (1.35, 103.82),
    "uae": (24.0, 54.0), "united arab emirates": (24.0, 54.0), "qatar": (25.3, 51.2),
    "australia": (-25.0, 133.0), "turkey": (39.0, 35.0),
}


def _coords(place: str):
    p = (place or "").lower()
    for city, c in _CITY_COORDS.items():
        if city in p:
            return c
    for country, c in _COUNTRY_COORDS.items():
        if country in p:
            return c
    return None


def _haversine_km(a, b) -> float:
    R = 6371.0
    lat1, lon1, lat2, lon2 = map(math.radians, [a[0], a[1], b[0], b[1]])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * R * math.asin(math.sqrt(h))


def _flight_base(origin: str, destination: str):
    """Indicative round-trip ECONOMY base (USD) + a human-readable basis.

    When both origin and destination resolve to coordinates, use great-circle
    distance (≈ $60 + $0.09/km round trip) so the fare actually reflects how far
    the trip is — Mumbai→Zurich ≠ London→Zurich. Otherwise (no origin given, or
    an unknown place) fall back to the coarse destination tier.
    """
    oc, dc = _coords(origin), _coords(destination)
    if oc and dc:
        km = _haversine_km(oc, dc)
        base = max(80, round((60 + 0.09 * km) / 10) * 10)  # RT economy, rounded to $10
        return base, f"~{round(km):,} km"
    tier = _flight_tier(destination)
    return FLIGHT_TIER_BASE[tier], f"tier:{tier}"


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
    origin = persona.get("origin", "")
    party_size = int(persona.get("party_size") or DEFAULT_PARTY_SIZE.get(group_type, 1))
    party_size = max(1, party_size)

    days = trip.get("days", [])
    num_days = max(1, len(days))
    num_nights = max(1, num_days - 1)
    num_stops = max(1, sum(len(day.get("stops", [])) for day in days))

    style_key = travel_style if travel_style in ACCOMMODATION_PER_NIGHT else "comfort"
    budget_key = budget_range if budget_range in FOOD_PER_DAY[style_key] else "mid"

    flight_base, flight_basis = _flight_base(origin, destination)
    flights = round(flight_base * FLIGHT_CLASS_MULT.get(style_key, 1.0))

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
        "Cost est: style=%s budget=%s group=%s party=%s rooms=%s flights=%s(%s) days=%s stops=%s -> $%s",
        style_key, budget_key, group_type, party_size, rooms, flights, flight_basis, num_days, num_stops, total,
    )

    return {
        "flights": flights,
        "accommodation": accommodation,
        "food": food,
        "transport": transport,
        "activities": activities,
        "total_per_person": total,
        "currency": "USD",
        "flight_basis": flight_basis,
    }

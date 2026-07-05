import json
import logging
from openai import AsyncOpenAI
from app.core.config import get_settings
from app.core.exceptions import TripGenerationError
from app.services.cost_estimator import _haversine_km

logger = logging.getLogger(__name__)
settings = get_settings()

TRIP_PROMPT = """You are an expert travel planner with deep geographic knowledge. Generate {num_plans} distinct trip itineraries.

PERSONAS (each plan MUST be one of these, and all {num_plans} must differ):
1. Budget Backpacker - hostels, street food, free activities, public transport
2. Comfort Traveller - 3-4 star hotels, mix of casual and nice restaurants, some paid activities
3. Luxury Escape - 5-star hotels, fine dining, premium experiences, private transport

=== TRAVELLER CONTEXT (applies to ALL plans) ===
{user_context}
- Plan about {stops_per_day} stops per day to match this traveller's pace.
- Tailor activity choices, meals, and phrasing to the group type above
  (e.g. family = kid-friendly & low-risk; couple = romantic; friends = social/nightlife; solo = flexible/easy-to-join).
- The three persona plans must still differ in accommodation, dining and transport tier — but every plan should suit this traveller context.

PLACES:
{places_json}

VIBE: {vibe}
{enrichment}
=== STEP 1: IDENTIFY REGIONS ===
First, analyze all places and group them by REGION. Each country has sub-regions.
Examples:
- India/Gujarat: Saurashtra, Kutch, North Gujarat, South Gujarat, Central Gujarat
- India/Rajasthan: Jaipur region, Jodhpur region, Udaipur region, Jaisalmer region
- India/Kerala: Kochi region, Munnar region, Alleppey region, Wayanad region
- Italy: Rome region, Florence region, Venice region, Amalfi region
- Japan: Tokyo region, Kyoto region, Osaka region, Hokkaido region

Group the places by their REGION first.

=== STEP 2: TIME BUDGET ===
A day has only 24 hours. Realistically, a tourist has 10-11 hours available:
- 8:00 AM - 7:00 PM = 11 hours (including travel between stops)
- Each stop needs: travel time + activity time + buffer
- Average: 2-3 stops per day maximum

TIME ESTIMATES:
- Intra-city travel: 30-60 minutes between stops
- Same region (50-100km): 1-2 hours travel
- Different region (100-300km): 3-5 hours travel
- Different state/country (300+ km): Full day travel or flight

=== STEP 3: GROUP BY PROXIMITY & ORDER NEAREST-FIRST ===
For each day, calculate if the stops FIT in 10-11 hours:
- Stop 1: 2 hours activity + 1 hour travel = 3 hours
- Stop 2: 2 hours activity + 1 hour travel = 3 hours
- Stop 3: 2 hours activity + 1 hour travel = 3 hours
- TOTAL: 9 hours ✓

If stops don't fit, split into different days.
WITHIN each day, order the stops NEAREST-FIRST so travel between them is minimal
(a logical route, not random jumps back and forth across the city).
Use the lat/lng in the PLACES data: any two places within ~30 km of each other
MUST be on the SAME day — never split nearby places across different days.

=== STEP 4: CREATE ITINERARY ===
- Let GEOGRAPHY decide the number of days — aim for roughly {num_days} days as a guide.
- Put places that are close together on the SAME day; put far-apart places (different
  regions/cities) on SEPARATE days. Never exceed 4 stops in one day.
- Match the pace: about {stops_per_day} stops per day.

=== MANDATORY: COVER ALL PLACES ===
CRITICAL: You MUST include EVERY place from the PLACES list in your itinerary.
- Count the places in the input list — your output MUST contain a stop for each one.
- Do not drop, merge, or skip any place. If a place is missing, the itinerary is INVALID.
- Double-check before returning: every place_name from input appears in the output.

GEOGRAPHIC EXAMPLES:
- Ahmedabad + Sabarmati Ashram = Same day (same city)
- Ahmedabad + Dwarka = Different days (450km, 6+ hours)
- Kochi + Munnar = Same day (130km, 3 hours, same region)
- Kochi + Alleppey = Same day (50km, 1 hour, same region)
- Delhi + Jaipur = Different days (280km, 5+ hours, different regions)

For each plan, return:
{{
  "plans": [
    {{
      "persona": "budget_backpacker|comfort_traveller|luxury_escape",
      "title": "Catchy trip title",
      "summary": "2-3 sentence overview",
      "days": [
        {{
          "day": 1,
          "theme": "Day theme (e.g. 'Ahmedabad City Exploration')",
          "region": "Region name (e.g. 'Central Gujarat')",
          "stops": [
            {{
              "place_name": "Place Name",
              "activity": "What to do there",
              "duration": "2-3 hours",
              "description": "Brief description"
            }}
          ],
          "meals": {{
            "breakfast": "Cafe/Restaurant name or type",
            "lunch": "Cafe/Restaurant name or type",
            "dinner": "Cafe/Restaurant name or type"
          }},
          "transport": {{
            "type": "metro|bus|taxi|walking|private"
          }}
        }}
      ]
    }}
  ]
}}

Do NOT include any cost or price fields — costs are calculated separately by the system.
Focus entirely on WHICH places go on WHICH day, grouped geographically, at the right pace.

Return ONLY valid JSON"""


PACE_STOPS = {"relaxed": 2, "moderate": 3, "packed": 4}

GROUP_LABELS = {
    "solo": "Solo traveller",
    "couple": "Couple",
    "family": "Family (with children)",
    "friends": "Group of friends",
}


def _stops_per_day(pace: str) -> int:
    return PACE_STOPS.get((pace or "moderate").lower(), 3)


def _build_user_context(persona: dict) -> str:
    group = GROUP_LABELS.get(persona.get("group_type", "solo"), "Solo traveller")
    pace = (persona.get("pace_preference") or "moderate").lower()
    budget = (persona.get("budget_range") or "mid").lower()
    return (
        f"- Group type: {group}\n"
        f"- Preferred pace: {pace}\n"
        f"- Budget sensitivity: {budget}"
    )


async def generate_trips(
    places: list[dict],
    vibe: str,
    persona: dict,
    num_plans: int = 3,
) -> list[dict]:
    if not settings.openai_api_key:
        logger.warning("OpenAI API key not set, using mock trip generation")
        return _mock_trips(places, vibe, persona)

    places = places[:15]
    num_places = len(places)
    stops_per_day = _stops_per_day(persona.get("pace_preference", "moderate"))
    user_context = _build_user_context(persona)

    destination_only = len(places) <= 1
    if destination_only:
        # The content named only a destination (common for reels whose places are
        # shown in the video, not the caption) — nothing to sequence by proximity,
        # so we suggest a realistic city break of well-known highlights. Length
        # tracks the chosen pace so it isn't always the same number of days.
        num_days = {"relaxed": 4, "moderate": 3, "packed": 2}.get(
            (persona.get("pace_preference") or "moderate").lower(), 3
        )
        dest = (places[0].get("estimated_location") or places[0].get("name", "the destination")) if places else "the destination"
        enrichment = (
            f"\n=== SPARSE INPUT — ENRICH ===\n"
            f"Only a general destination was provided ({dest}), not specific venues. "
            f"Suggest a realistic {num_days}-day city break of REAL, well-known highlights "
            f"that fit the vibe and pace above — group nearby highlights on the same day (nearest-first), "
            f"give each day a distinct theme, and don't collapse everything into one day. "
            f"Use genuine place names a first-time visitor would recognise.\n"
        )
    else:
        # Days follow from how many places we actually found and the chosen pace,
        # then geography (STEP 1-4) decides the final grouping. No arbitrary table.
        num_days = max(2, -(-num_places // stops_per_day))  # ceil(places / stops_per_day)
        num_days = min(num_days, 7)
        enrichment = ""

    places_text = json.dumps(places[:15], indent=2)
    prompt = TRIP_PROMPT.format(
        num_plans=num_plans,
        places_json=places_text,
        enrichment=enrichment,
        vibe=vibe,
        num_days=num_days,
        stops_per_day=stops_per_day,
        user_context=user_context,
    )

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": f"Generate trip plans for these places with vibe: {vibe}"},
            ],
            response_format={"type": "json_object"},
            temperature=0.7,
            max_tokens=4000,
        )

        result_text = response.choices[0].message.content
        result = json.loads(result_text)
        plans = result.get("plans", [])
        return _validate_and_fix_plans(plans, places, enforce_coverage=not destination_only)

    except Exception as e:
        logger.error(f"Trip generation failed: {e}")
        return _mock_trips(places, vibe, persona)


def _validate_and_fix_plans(plans: list[dict], original_places: list[dict], enforce_coverage: bool = True) -> list[dict]:
    """Validate LLM output and fix structural issues WITHOUT destroying the
    geographic day grouping the model produced. Costs are added later by the
    deterministic estimator, so no cost fields are touched here.

    When enforce_coverage is False (destination-only input that we enriched with
    real highlights), we don't force the original placeholder back into the plan.
    """
    # name (lower) -> estimated_location, used to place missing stops sensibly.
    loc_by_name = {
        p.get("name", "").lower(): p.get("estimated_location", "")
        for p in original_places
    }
    # Real coordinates (when Google Places resolved them) → used to force nearby
    # places onto the same day. Skips the 0,0 fallback.
    coords_by_name = {
        p.get("name", "").lower(): (p["lat"], p["lng"])
        for p in original_places
        if p.get("lat") and p.get("lng") and not (p["lat"] == 0 and p["lng"] == 0)
    }
    place_names = {p.get("name", "").lower() for p in original_places if p.get("name")}

    for plan in plans:
        if "days" not in plan or not isinstance(plan["days"], list):
            continue

        for day in plan["days"]:
            if not isinstance(day.get("stops"), list):
                day["stops"] = []

        covered = {
            s.get("place_name", "").lower()
            for day in plan["days"]
            for s in day["stops"]
        }
        missing = (place_names - covered) if enforce_coverage else set()
        if missing:
            logger.warning("LLM missed %d places: %s. Placing by region.", len(missing), missing)
            for name in missing:
                _place_missing_stop(plan, name, loc_by_name.get(name, ""))

        if coords_by_name:
            _colocate_nearby(plan, coords_by_name)
        _cap_stops_per_day(plan)

        for i, day in enumerate(plan["days"], start=1):
            day["day"] = i
            if not day.get("theme"):
                day["theme"] = f"Day {i}"
            if not day.get("region"):
                day["region"] = "Unknown"
            if not day.get("meals"):
                day["meals"] = {"breakfast": "Local cafe", "lunch": "Restaurant", "dinner": "Restaurant"}
            if not day.get("transport"):
                day["transport"] = {"type": "mixed"}

    return plans


def _place_missing_stop(plan: dict, name: str, location: str):
    """Add a missing place to the day that best matches its location/region,
    creating a new day only if nothing matches — never flattening the plan."""
    stop = {
        "place_name": name.title(),
        "activity": f"Explore {name.title()}",
        "duration": "2-3 hours",
        "description": f"Visit {name.title()}",
    }
    # Try to attach to a day whose region matches the place's location; the
    # location is usually "City, Country", so match on any word overlap.
    loc_tokens = {t.strip().lower() for t in location.replace(",", " ").split() if len(t) > 2}
    if loc_tokens:
        for day in plan["days"]:
            region_tokens = {t.strip().lower() for t in (day.get("region") or "").split()}
            if loc_tokens & region_tokens:
                day["stops"].append(stop)
                return

    if plan["days"]:
        plan["days"][-1]["stops"].append(stop)
    else:
        plan["days"] = [{"day": 1, "theme": "Exploration", "region": location or "Unknown", "stops": [stop]}]


def _colocate_nearby(plan: dict, coords_by_name: dict, km: float = 30.0):
    """Guarantee that geographically close places (<= km apart, by real
    coordinates) end up on the SAME day — never split across separate days.

    Clusters stops with union-find on distance, then moves every member of a
    cluster to the earliest day any member appeared on. Places without real
    coordinates are left where the LLM put them. Overflow (a big cluster) is
    handled afterwards by _cap_stops_per_day, which keeps them on consecutive
    same-region days rather than scattering them.
    """
    days = plan.get("days", [])
    if len(days) < 2:
        return
    entries = [(di, s) for di, d in enumerate(days) for s in d.get("stops", [])]
    n = len(entries)
    if n < 2:
        return

    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def coord(i):
        return coords_by_name.get((entries[i][1].get("place_name", "") or "").lower())

    for a in range(n):
        ca = coord(a)
        if not ca:
            continue
        for b in range(a + 1, n):
            cb = coord(b)
            if cb and _haversine_km(ca, cb) <= km:
                parent[find(a)] = find(b)

    # Earliest day index in each cluster becomes that cluster's home day.
    target = {}
    for i in range(n):
        r = find(i)
        target[r] = min(target.get(r, entries[i][0]), entries[i][0])

    buckets = {}
    for i in range(n):
        buckets.setdefault(target[find(i)], []).append(entries[i][1])

    rebuilt = []
    for di, d in enumerate(days):
        if di in buckets:
            d["stops"] = buckets[di]
            rebuilt.append(d)
    if rebuilt:
        plan["days"] = rebuilt


def _cap_stops_per_day(plan: dict, max_stops: int = 4):
    """Split any day with more than `max_stops` into an extra same-region day
    inserted right after it. Preserves grouping instead of re-slicing."""
    days = plan.get("days")
    if not days:
        return

    result = []
    for day in days:
        stops = day.get("stops", [])
        if len(stops) <= max_stops:
            result.append(day)
            continue
        # keep first max_stops here, spill the rest into cloned same-region days
        base = {**day, "stops": stops[:max_stops]}
        result.append(base)
        rest = stops[max_stops:]
        while rest:
            cont = {
                "theme": f"{day.get('theme', 'Day')} (continued)",
                "region": day.get("region", "Unknown"),
                "stops": rest[:max_stops],
                "meals": day.get("meals", {}),
                "transport": day.get("transport", {}),
            }
            result.append(cont)
            rest = rest[max_stops:]

    plan["days"] = result


def _mock_trips(places: list[dict], vibe: str, persona: dict) -> list[dict]:
    place_names = [p.get("name", "Unknown") for p in places[:8]]
    locations = list(set(p.get("estimated_location", "Unknown") for p in places))
    main_location = locations[0] if locations else "Unknown"

    personas = [
        {
            "persona": "budget_backpacker",
            "title": f"Budget Adventure in {main_location.split(',')[0]}",
            "summary": f"Explore {main_location} on a budget with hostels, street food, and free attractions.",
            "daily_cost": 75,
            "flight_mult": 0.6,
            "hotel_mult": 0.4,
        },
        {
            "persona": "comfort_traveller",
            "title": f"Comfortable {main_location.split(',')[0]} Discovery",
            "summary": f"Enjoy {main_location} with comfortable hotels, great food, and key attractions.",
            "daily_cost": 220,
            "flight_mult": 1.0,
            "hotel_mult": 1.0,
        },
        {
            "persona": "luxury_escape",
            "title": f"Luxury {main_location.split(',')[0]} Experience",
            "summary": f"Indulge in the finest {main_location} has to offer with premium experiences.",
            "daily_cost": 600,
            "flight_mult": 2.0,
            "hotel_mult": 3.0,
        },
    ]

    plans = []

    location_groups = {}
    for i, place in enumerate(places):
        loc = place.get("estimated_location", "Unknown")
        if loc not in location_groups:
            location_groups[loc] = []
        location_groups[loc].append({
            "place_name": place.get("name", f"Place {i+1}"),
            "activity": place.get("activity_type", "Explore"),
            "duration": place.get("duration", "2-3 hours"),
            "description": place.get("description", f"Visit {place.get('name', 'this place')}"),
        })

    days_needed = max(2, min(5, len(location_groups)))

    day_assignments = [[] for _ in range(days_needed)]
    for loc, stops in location_groups.items():
        min_day = min(range(days_needed), key=lambda d: len(day_assignments[d]))
        day_assignments[min_day].extend(stops)

    day_themes = [
        "Arrival & First Impressions",
        "Culture & Exploration",
        "Adventure & Nature",
        "Relaxation & Leisure",
        "Final Day & Departure",
    ]

    for p_config in personas:
        days = []
        for d in range(days_needed):
            day_num = d + 1
            stops = day_assignments[d] if d < len(day_assignments) else []
            if not stops:
                stops = [{"place_name": "Free time", "activity": "Relax or explore on your own", "duration": "Flexible", "description": "Take it easy"}]

            daily_cost = p_config["daily_cost"]
            theme = day_themes[d] if d < len(day_themes) else f"Day {day_num}"

            days.append({
                "day": day_num,
                "theme": f"Day {day_num}: {theme}",
                "region": list(location_groups.keys())[d] if d < len(location_groups) else "Unknown",
                "stops": stops,
                "meals": {
                    "breakfast": "Local cafe" if p_config["persona"] != "luxury_escape" else "Hotel breakfast",
                    "lunch": "Street food stall" if p_config["persona"] == "budget_backpacker" else "Casual restaurant" if p_config["persona"] == "comfort_traveller" else "Fine dining",
                    "dinner": "Night market" if p_config["persona"] == "budget_backpacker" else "Popular local restaurant" if p_config["persona"] == "comfort_traveller" else "Michelin-star restaurant",
                },
                "transport": {
                    "type": "walking" if p_config["persona"] == "budget_backpacker" else "metro" if p_config["persona"] == "comfort_traveller" else "private car",
                    "estimated_cost": 5 if p_config["persona"] == "budget_backpacker" else 15 if p_config["persona"] == "comfort_traveller" else 50,
                },
                "daily_cost": daily_cost,
            })

        total = sum(day["daily_cost"] for day in days)
        flight_est = 400 * p_config["flight_mult"]
        hotel_est = 100 * p_config["hotel_mult"] * days_needed

        plans.append({
            "persona": p_config["persona"],
            "title": p_config["title"],
            "summary": p_config["summary"],
            "days": days,
            "total_cost_per_person": round(total + flight_est + hotel_est, 2),
            "cost_breakdown": {
                "flights": round(flight_est, 2),
                "accommodation": round(hotel_est, 2),
                "food": round(total * 0.4, 2),
                "transport": round(total * 0.3, 2),
                "activities": round(total * 0.3, 2),
            },
        })

    return plans

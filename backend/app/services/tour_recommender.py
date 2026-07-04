"""Tour recommendation over a mock catalogue.

Per the spec, tours come from a curated mock catalogue (data/mock_tours.json)
that mirrors the shape of a GetYourGuide/Viator response. We deliberately do
NOT use Google Places for tours: Places returns POIs (attractions, restaurants),
not bookable tours with a real price and duration, so treating them as tours
would be misleading. Swapping in a real tours API later means implementing one
function that returns catalogue-shaped dicts.
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_mock_tours: list[dict] = []


def _load_tours() -> list[dict]:
    global _mock_tours
    if _mock_tours:
        return _mock_tours
    tours_path = Path(__file__).parent.parent.parent / "data" / "mock_tours.json"
    if tours_path.exists():
        with open(tours_path) as f:
            _mock_tours = json.load(f)
    return _mock_tours


def recommend_tours_for_trip_sync(
    trip_days: list[dict],
    persona: str,
    budget_range: str = "mid",
) -> list[dict]:
    all_tours = _load_tours()
    results = []

    for day in trip_days:
        day_tours = []
        for stop in day.get("stops", []):
            place_name = stop.get("place_name", "")
            city = _extract_city(place_name)
            country = _extract_country(place_name)
            activity = stop.get("activity", "")

            matched = _match_tours(
                all_tours=all_tours,
                city=city,
                country=country,
                persona=persona,
                activity=activity,
                budget_range=budget_range,
            )
            day_tours.append({
                "place": place_name,
                "recommended_tours": matched[:2],
            })
        results.append({
            "day": day.get("day"),
            "tours": day_tours,
        })

    return results


def recommend_tours_by_city(
    city: str,
    persona: str = "comfort",
    activity_type: str = "",
) -> list[dict]:
    all_tours = _load_tours()
    return _match_tours(
        all_tours=all_tours,
        city=city,
        country="",
        persona=persona,
        activity=activity_type,
        budget_range="mid",
    )


def _match_tours(
    all_tours: list[dict],
    city: str,
    country: str,
    persona: str,
    activity: str,
    budget_range: str,
) -> list[dict]:
    city_lower = city.lower()
    country_lower = country.lower()

    city_matches = []
    country_matches = []
    all_scored = []

    for tour in all_tours:
        tour_city = tour.get("location", {}).get("city", "").lower()
        tour_country = tour.get("location", {}).get("country", "").lower()

        score = 0

        if city_lower and (city_lower == tour_city or city_lower in tour_city or tour_city in city_lower):
            score += 20
        elif country_lower and (country_lower == tour_country or country_lower in tour_country):
            score += 10
        else:
            score += 1

        activity_types = tour.get("activityType", [])
        activity_lower = activity.lower() if activity else ""
        for at in activity_types:
            if activity_lower and (at in activity_lower or activity_lower in at):
                score += 5

        price = tour.get("price", {}).get("amount", 0)
        if budget_range == "low" and price < 60:
            score += 4
        elif budget_range == "mid" and 40 <= price <= 120:
            score += 4
        elif budget_range == "high" and price > 80:
            score += 4

        rating = tour.get("rating", 0)
        score += rating * 2

        if tour.get("reviewCount", 0) > 500:
            score += 3

        tour_scored = {**tour, "match_score": score}

        if score >= 20:
            city_matches.append(tour_scored)
        elif score >= 10:
            country_matches.append(tour_scored)
        else:
            all_scored.append(tour_scored)

    city_matches.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    country_matches.sort(key=lambda x: x.get("match_score", 0), reverse=True)
    all_scored.sort(key=lambda x: x.get("match_score", 0), reverse=True)

    if city_matches:
        return city_matches[:3]
    if country_matches:
        return country_matches[:3]
    return all_scored[:3]


def _extract_country(place_name: str) -> str:
    country_keywords = {
        "india": "India",
        "kerala": "India",
        "munnar": "India",
        "alleppey": "India",
        "kochi": "India",
        "varkala": "India",
        "thekkady": "India",
        "japan": "Japan",
        "france": "France",
        "italy": "Italy",
        "spain": "Spain",
        "thailand": "Thailand",
        "indonesia": "Indonesia",
        "usa": "USA",
        "united states": "USA",
    }
    name_lower = place_name.lower()
    for keyword, country in country_keywords.items():
        if keyword in name_lower:
            return country
    return ""


def _extract_city(place_name: str) -> str:
    city_keywords = {
        "paris": "Paris",
        "tokyo": "Tokyo",
        "bali": "Ubud",
        "ubud": "Ubud",
        "kuta": "Kuta",
        "bangkok": "Bangkok",
        "new york": "New York",
        "barcelona": "Barcelona",
        "rome": "Rome",
        "kyoto": "Kyoto",
        "osaka": "Osaka",
        "london": "London",
        "munnar": "Munnar",
        "eravikulam": "Munnar",
        "mattupatty": "Munnar",
        "alleppey": "Alleppey",
        "alappuzha": "Alleppey",
        "backwater": "Alleppey",
        "kochi": "Kochi",
        "fort kochi": "Kochi",
        "varkala": "Varkala",
        "thekkady": "Thekkady",
        "periyar": "Thekkady",
        "kanyakumari": "Kanyakumari",
        "trivandrum": "Trivandrum",
    }
    name_lower = place_name.lower()
    for keyword, city in city_keywords.items():
        if keyword in name_lower:
            return city
    return place_name

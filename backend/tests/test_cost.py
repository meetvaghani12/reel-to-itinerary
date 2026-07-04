import pytest

from app.services.cost_estimator import estimate_costs, _flight_tier
from app.services.trip_generator import (
    _stops_per_day,
    _build_user_context,
    _validate_and_fix_plans,
    _cap_stops_per_day,
)

TRIP = {"days": [{"stops": [1, 2]}, {"stops": [3]}]}


@pytest.mark.asyncio
async def test_costs_increase_across_personas():
    budget = await estimate_costs(TRIP, {"travel_style": "budget", "budget_range": "low", "group_type": "solo"}, "Munnar, India")
    comfort = await estimate_costs(TRIP, {"travel_style": "comfort", "budget_range": "mid", "group_type": "solo"}, "Munnar, India")
    luxury = await estimate_costs(TRIP, {"travel_style": "luxury", "budget_range": "high", "group_type": "solo"}, "Munnar, India")
    assert budget["total_per_person"] < comfort["total_per_person"] < luxury["total_per_person"]


@pytest.mark.asyncio
async def test_group_sharing_reduces_accommodation():
    solo = await estimate_costs(TRIP, {"travel_style": "comfort", "budget_range": "mid", "group_type": "solo"}, "Paris, France")
    family = await estimate_costs(TRIP, {"travel_style": "comfort", "budget_range": "mid", "group_type": "family"}, "Paris, France")
    assert family["accommodation"] < solo["accommodation"]


@pytest.mark.asyncio
async def test_costs_are_usd():
    c = await estimate_costs(TRIP, {"travel_style": "comfort", "budget_range": "mid", "group_type": "solo"}, "Tokyo, Japan")
    assert c["currency"] == "USD"


def test_flight_tier_inference():
    assert _flight_tier("Munnar, India") == "regional"
    assert _flight_tier("Paris, France") == "international"
    assert _flight_tier("Somewhere Unknown") == "international"


def test_pace_controls_stops_per_day():
    assert _stops_per_day("relaxed") == 2
    assert _stops_per_day("moderate") == 3
    assert _stops_per_day("packed") == 4
    assert _stops_per_day(None) == 3


def test_user_context_reflects_persona():
    ctx = _build_user_context({"group_type": "family", "pace_preference": "relaxed", "budget_range": "low"})
    assert "Family" in ctx
    assert "relaxed" in ctx
    assert "low" in ctx


def test_cap_stops_preserves_region():
    plan = {"days": [{"day": 1, "region": "Kerala", "stops": [{"place_name": str(i)} for i in range(6)]}]}
    _cap_stops_per_day(plan, max_stops=4)
    assert len(plan["days"]) == 2
    assert all(d["region"] == "Kerala" for d in plan["days"])
    assert sum(len(d["stops"]) for d in plan["days"]) == 6


def test_missing_places_get_covered():
    places = [{"name": "A", "estimated_location": "Kerala, India"},
              {"name": "B", "estimated_location": "Kerala, India"}]
    plans = [{"persona": "comfort_traveller", "days": [{"day": 1, "region": "Kerala", "stops": [{"place_name": "A"}]}]}]
    fixed = _validate_and_fix_plans(plans, places)
    covered = {s["place_name"].lower() for d in fixed[0]["days"] for s in d["stops"]}
    assert "a" in covered and "b" in covered

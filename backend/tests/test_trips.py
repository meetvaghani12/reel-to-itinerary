import pytest
from app.services.trip_generator import _mock_trips


def test_mock_trips_generates_three_plans():
    places = [
        {"name": "Eiffel Tower", "estimated_location": "Paris, France", "type": "landmark"},
        {"name": "Louvre Museum", "estimated_location": "Paris, France", "type": "museum"},
        {"name": "Montmartre", "estimated_location": "Paris, France", "type": "neighborhood"},
        {"name": "Seine River", "estimated_location": "Paris, France", "type": "viewpoint"},
    ]
    result = _mock_trips(places, "cultural", {"budget_range": "mid"})
    assert len(result) == 3
    assert result[0]["persona"] == "budget_backpacker"
    assert result[1]["persona"] == "comfort_traveller"
    assert result[2]["persona"] == "luxury_escape"


def test_mock_trips_cost_increases_with_persona():
    places = [
        {"name": "Temple", "estimated_location": "Bangkok, Thailand", "type": "temple"},
        {"name": "Night Market", "estimated_location": "Bangkok, Thailand", "type": "market"},
    ]
    result = _mock_trips(places, "mixed", {"budget_range": "mid"})
    assert result[0]["total_cost_per_person"] < result[1]["total_cost_per_person"]
    assert result[1]["total_cost_per_person"] < result[2]["total_cost_per_person"]


def test_mock_trips_has_required_fields():
    places = [{"name": "Test", "estimated_location": "Tokyo, Japan", "type": "landmark"}]
    result = _mock_trips(places, "cultural", {"budget_range": "mid"})
    for plan in result:
        assert "persona" in plan
        assert "title" in plan
        assert "days" in plan
        assert "total_cost_per_person" in plan
        assert "cost_breakdown" in plan
        assert len(plan["days"]) > 0

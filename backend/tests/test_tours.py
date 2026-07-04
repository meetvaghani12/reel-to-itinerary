import pytest
from app.services.tour_recommender import _load_tours, _match_tours, _extract_city


def test_mock_tours_loaded():
    tours = _load_tours()
    assert len(tours) >= 20


def test_match_tours_paris():
    tours = _load_tours()
    matched = _match_tours(tours, "Paris", "France", "comfort_traveller", "walking", "mid")
    assert len(matched) > 0
    assert all(t["location"]["city"] == "Paris" for t in matched)


def test_match_tours_budget_persona():
    tours = _load_tours()
    matched = _match_tours(tours, "Bangkok", "Thailand", "budget_backpacker", "food", "low")
    assert len(matched) > 0
    for tour in matched:
        assert tour["price"]["amount"] < 100


def test_extract_city():
    assert _extract_city("Eiffel Tower, Paris") == "Paris"
    assert _extract_city("Shibuya Crossing, Tokyo") == "Tokyo"
    assert _extract_city("Unknown Place") == "Unknown Place"


def test_tours_have_required_fields():
    tours = _load_tours()
    for tour in tours:
        assert "id" in tour
        assert "title" in tour
        assert "location" in tour
        assert "price" in tour
        assert "rating" in tour

import pytest
from app.services.llm_extractor import _mock_extraction


def test_mock_extraction_with_known_city():
    result = _mock_extraction("Bali Travel Guide", "Best places to visit in Bali Indonesia")
    assert len(result["places"]) > 0
    assert result["vibe"] in ["foodie", "adventure", "cultural", "relaxation", "mixed"]
    assert any("Bali" in p.get("estimated_location", "") for p in result["places"])


def test_mock_extraction_food_content():
    result = _mock_extraction(
        "Best Food in Tokyo",
        "Ramen, sushi, and street food tour in Tokyo Japan",
    )
    assert result["vibe"] == "foodie"
    assert any("Tokyo" in p["estimated_location"] for p in result["places"])


def test_mock_extraction_adventure_content():
    result = _mock_extraction(
        "Bali Adventure",
        "Hiking trekking and surfing in Bali",
    )
    assert result["vibe"] == "adventure"


def test_mock_extraction_unknown_location():
    result = _mock_extraction("My Trip", "Just a random video about travel")
    assert len(result["places"]) > 0
    assert result["places"][0]["name"] == "Unknown Destination"

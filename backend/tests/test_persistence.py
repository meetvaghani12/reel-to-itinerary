import pytest

from app.models.database import init_db
from app.models.repository import (
    save_extraction_result,
    get_extraction,
    get_trip,
    list_extractions,
)


@pytest.mark.asyncio
async def test_persist_and_read_back():
    await init_db()
    await save_extraction_result(
        extraction_id="pytest01",
        url="https://youtube.com/watch?v=pytest",
        raw_content={"platform": "youtube", "title": "Test Vlog", "description": "d", "transcript": "t"},
        extracted={"places": [{"name": "Munnar"}], "vibe": "nature"},
        resolved=[{"name": "Munnar", "type": "landmark", "lat": 10.0, "lng": 77.0}],
        trips=[{
            "persona": "comfort_traveller",
            "title": "Test Trip",
            "days": [{"day": 1, "stops": [{"place_name": "Munnar"}]}],
            "total_cost_per_person": 776,
            "cost_breakdown": {"flights": 450},
            "tours": [],
        }],
    )

    ext = await get_extraction("pytest01")
    assert ext is not None
    assert ext["title"] == "Test Vlog"
    assert len(ext["places"]) == 1
    assert len(ext["trips"]) == 1
    assert ext["trips"][0]["total_cost_per_person"] == 776

    listing = await list_extractions()
    assert any(e["extraction_id"] == "pytest01" for e in listing)


@pytest.mark.asyncio
async def test_missing_returns_none():
    await init_db()
    assert await get_extraction("does-not-exist") is None
    assert await get_trip("does-not-exist") is None

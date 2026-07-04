from fastapi import APIRouter, HTTPException, Query
from app.models.repository import (
    get_trip as repo_get_trip,
    get_extraction as repo_get_extraction,
    list_extractions as repo_list_extractions,
)

router = APIRouter()


@router.get("/")
async def list_recent(limit: int = Query(50, ge=1, le=200)):
    """Recently processed extractions (trip history)."""
    return {"extractions": await repo_list_extractions(limit=limit)}


@router.get("/extraction/{extraction_id}")
async def get_extraction(extraction_id: str):
    """Full saved result for an extraction: places + all generated trip plans."""
    result = await repo_get_extraction(extraction_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Extraction not found")
    return result


@router.get("/{trip_id}")
async def get_trip(trip_id: str):
    """A single persisted trip plan by its id."""
    trip = await repo_get_trip(trip_id)
    if trip is None:
        raise HTTPException(status_code=404, detail="Trip not found")
    return trip

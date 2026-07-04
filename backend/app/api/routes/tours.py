from fastapi import APIRouter, Query
from app.services.tour_recommender import recommend_tours_by_city

router = APIRouter()


@router.get("/")
async def get_tours(
    city: str = Query(..., description="City name"),
    persona: str = Query("comfort", description="Travel persona"),
    activity_type: str = Query("", description="Activity type filter"),
):
    tours = recommend_tours_by_city(
        city=city,
        persona=persona,
        activity_type=activity_type,
    )
    return {"city": city, "persona": persona, "tours": tours}

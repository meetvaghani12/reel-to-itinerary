from pydantic import BaseModel
from typing import Optional


class TourRecommendation(BaseModel):
    id: str
    title: str
    description: str = ""
    location: dict = {}
    category: str = ""
    duration: str = ""
    price: float = 0.0
    currency: str = "USD"
    rating: float = 0.0
    review_count: int = 0
    match_score: float = 0.0
    booking_url: str = ""

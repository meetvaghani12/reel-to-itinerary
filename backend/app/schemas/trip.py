from pydantic import BaseModel
from typing import Optional


class TourStop(BaseModel):
    place_name: str
    activity: str
    duration: str = ""
    description: str = ""
    tours: list[dict] = []
    cost_estimate: float = 0.0


class ItineraryDay(BaseModel):
    day: int
    theme: str = ""
    stops: list[TourStop] = []
    meals: dict = {}
    transport: dict = {}
    daily_cost: float = 0.0


class TripPlan(BaseModel):
    persona: str
    title: str = ""
    summary: str = ""
    days: list[ItineraryDay] = []
    total_cost_per_person: float = 0.0
    cost_breakdown: dict = {}

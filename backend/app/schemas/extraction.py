from pydantic import BaseModel, Field
from typing import Optional


class PersonaInput(BaseModel):
    travel_style: str = Field(default="comfort", description="Travel style: budget, comfort, or luxury")
    budget_range: str = Field(default="mid", description="Budget range: low, mid, high")
    group_type: str = Field(default="solo", description="Group type: solo, couple, family, friends")
    party_size: int = Field(default=1, ge=1, le=16, description="Number of travellers — refines per-person accommodation via room sharing")
    pace_preference: str = Field(default="moderate", description="Pace: relaxed, moderate, packed")


class ExtractRequest(BaseModel):
    url: str = Field(..., description="YouTube or Instagram URL")
    persona: PersonaInput = Field(default_factory=PersonaInput)


class PlaceExtracted(BaseModel):
    name: str
    type: str = ""
    description: str = ""
    estimated_location: str = ""
    activity_type: str = ""
    duration: str = ""


class ExtractionResponse(BaseModel):
    extraction_id: str
    status: str
    platform: str
    title: Optional[str] = None
    places: list[PlaceExtracted] = []
    vibe: str = ""
    trips: list[dict] = []
    total_cost_per_person: float = 0.0

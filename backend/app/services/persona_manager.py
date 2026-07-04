from app.schemas.persona import Persona

PERSONAS = {
    "budget_backpacker": Persona(
        travel_style="budget",
        budget_range="low",
        group_type="solo",
        pace_preference="packed",
    ),
    "comfort_traveller": Persona(
        travel_style="comfort",
        budget_range="mid",
        group_type="couple",
        pace_preference="moderate",
    ),
    "luxury_escape": Persona(
        travel_style="luxury",
        budget_range="high",
        group_type="couple",
        pace_preference="relaxed",
    ),
}


def get_persona_profile(persona_name: str) -> Persona:
    return PERSONAS.get(persona_name, PERSONAS["comfort_traveller"])


def get_all_personas() -> dict[str, Persona]:
    return PERSONAS.copy()

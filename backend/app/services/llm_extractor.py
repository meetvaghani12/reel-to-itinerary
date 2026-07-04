import json
import logging
from openai import AsyncOpenAI
from app.core.config import get_settings
from app.core.exceptions import ExtractionError

logger = logging.getLogger(__name__)
settings = get_settings()

EXTRACTION_PROMPT = """You are a travel content analyst. Extract ALL specific places, activities, and locations mentioned in this travel video content.

Return a JSON object with this exact structure:
{
  "places": [
    {
      "name": "Place Name",
      "type": "restaurant|hotel|landmark|neighborhood|activity|viewpoint|market|beach|temple|other",
      "description": "Brief description of why this place matters",
      "estimated_location": "City, Country",
      "activity_type": "food|cultural|adventure|relaxation|sightseeing|shopping|nightlife|other",
      "duration": "1-2 hours|half day|full day|other"
    }
  ],
  "vibe": "adventure|cultural|relaxation|foodie|luxury|budget|mixed",
  "summary": "One paragraph summary of the travel experience"
}

RULES:
- Extract EVERY specific place mentioned, even if briefly
- Use the actual name as mentioned in the content
- If a place type is unclear, use "other"
- Estimate location as "City, Country" format
- The vibe should reflect the overall tone of the content
- IMPORTANT — vague captions: Instagram reels often name a destination without
  listing venues (e.g. "Let's explore Delhi in one day!" or hashtags like
  #delhidiaries). In that case, still return the destination as a SINGLE place
  with type "neighborhood", name = the city/region, and estimated_location =
  "City, Country". Also set "destination_only": true at the top level.
- Only return an empty "places" array when there is NO identifiable travel
  destination at all (e.g. a non-travel video).
- Return ONLY valid JSON, no markdown or extra text"""


async def extract_places(title: str, description: str, transcript: str) -> dict:
    if not settings.openai_api_key:
        logger.warning("OpenAI API key not set, using mock extraction")
        return _mock_extraction(title, description)

    content = f"Title: {title}\n\nDescription: {description}\n"
    if transcript:
        content += f"\nTranscript:\n{transcript[:8000]}"

    client = AsyncOpenAI(
        api_key=settings.openai_api_key,
        base_url=settings.openai_base_url,
    )

    try:
        response = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[
                {"role": "system", "content": EXTRACTION_PROMPT},
                {"role": "user", "content": content},
            ],
            response_format={"type": "json_object"},
            temperature=0.3,
            max_tokens=2000,
        )

        result_text = response.choices[0].message.content
        result = json.loads(result_text)

        logger.info(f"Extracted {len(result.get('places', []))} places from content")
        return result

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse LLM response: {e}")
        raise ExtractionError("Failed to parse extraction results")
    except Exception as e:
        logger.error(f"LLM extraction failed: {e}")
        raise ExtractionError(f"Extraction failed: {str(e)}")


def _mock_extraction(title: str, description: str) -> dict:
    combined = f"{title} {description}".lower()

    places = []
    vibes = []

    place_hints = {
        "paris": {"name": "Paris", "type": "neighborhood", "location": "Paris, France"},
        "tokyo": {"name": "Tokyo", "type": "neighborhood", "location": "Tokyo, Japan"},
        "bali": {"name": "Bali", "type": "neighborhood", "location": "Bali, Indonesia"},
        "bangkok": {"name": "Bangkok", "type": "neighborhood", "location": "Bangkok, Thailand"},
        "new york": {"name": "New York City", "type": "neighborhood", "location": "New York, USA"},
        "barcelona": {"name": "Barcelona", "type": "neighborhood", "location": "Barcelona, Spain"},
        "rome": {"name": "Rome", "type": "neighborhood", "location": "Rome, Italy"},
    }

    for keyword, info in place_hints.items():
        if keyword in combined:
            places.append({
                "name": info["name"],
                "type": info["type"],
                "description": f"Destination mentioned in content",
                "estimated_location": info["location"],
                "activity_type": "sightseeing",
                "duration": "full day",
            })

    if not places:
        places.append({
            "name": "Unknown Destination",
            "type": "other",
            "description": "Could not extract specific places from content",
            "estimated_location": "Unknown",
            "activity_type": "sightseeing",
            "duration": "full day",
        })

    food_words = ["food", "eat", "restaurant", "cafe", "coffee", "dinner", "lunch", "breakfast"]
    adventure_words = ["hike", "trek", "surf", "dive", "climb", "adventure"]
    cultural_words = ["temple", "museum", "history", "culture", "art"]

    if any(w in combined for w in food_words):
        vibes.append("foodie")
    if any(w in combined for w in adventure_words):
        vibes.append("adventure")
    if any(w in combined for w in cultural_words):
        vibes.append("cultural")

    vibe = vibes[0] if vibes else "mixed"

    return {
        "places": places,
        "vibe": vibe,
        "summary": f"Travel content about {places[0]['estimated_location']}",
    }

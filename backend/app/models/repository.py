"""Persistence layer for extractions, resolved places and generated trips.

Uses the async SQLAlchemy session. All writes are best-effort: a DB failure is
logged but never breaks the API response (the result is still cached + returned).
"""
import logging
import uuid
from sqlalchemy import select, delete

from app.models.database import async_session
from app.models.extraction import Extraction, Trip, ResolvedPlace

logger = logging.getLogger(__name__)


async def save_extraction_result(
    extraction_id: str,
    url: str,
    raw_content: dict,
    extracted: dict,
    resolved: list[dict],
    trips: list[dict],
) -> None:
    """Persist a full extraction result. Idempotent per extraction_id."""
    try:
        async with async_session() as session:
            # Replace any prior rows for this extraction_id (idempotent re-runs).
            await session.execute(delete(Trip).where(Trip.extraction_id == extraction_id))
            await session.execute(delete(ResolvedPlace).where(ResolvedPlace.extraction_id == extraction_id))
            await session.execute(delete(Extraction).where(Extraction.id == extraction_id))

            session.add(Extraction(
                id=extraction_id,
                url=url,
                platform=raw_content.get("platform", "unknown"),
                title=raw_content.get("title", ""),
                description=raw_content.get("description", ""),
                transcript=raw_content.get("transcript", ""),
                raw_places=extracted.get("places", []),
                vibe=extracted.get("vibe", ""),
            ))

            for p in resolved:
                session.add(ResolvedPlace(
                    id=str(uuid.uuid4()),
                    extraction_id=extraction_id,
                    name=p.get("name", ""),
                    category=p.get("type", ""),
                    lat=p.get("lat"),
                    lng=p.get("lng"),
                    rating=p.get("rating"),
                    price_level=p.get("price_level"),
                    google_place_id=p.get("google_place_id"),
                    data=p,
                ))

            for plan in trips:
                session.add(Trip(
                    id=str(uuid.uuid4()),
                    extraction_id=extraction_id,
                    persona=plan.get("persona", ""),
                    title=plan.get("title", ""),
                    days=plan.get("days", []),
                    total_cost_per_person=float(plan.get("total_cost_per_person", 0) or 0),
                    data=plan,
                ))

            await session.commit()
            logger.info("Persisted extraction %s (%d places, %d trips)",
                        extraction_id, len(resolved), len(trips))
    except Exception as e:
        logger.warning("Persistence failed for %s: %s", extraction_id, e)


async def get_extraction(extraction_id: str) -> dict | None:
    """Return the saved extraction with its resolved places and trips, or None."""
    try:
        async with async_session() as session:
            ext = await session.get(Extraction, extraction_id)
            if ext is None:
                return None

            places = (await session.execute(
                select(ResolvedPlace).where(ResolvedPlace.extraction_id == extraction_id)
            )).scalars().all()
            trips = (await session.execute(
                select(Trip).where(Trip.extraction_id == extraction_id)
            )).scalars().all()

            return {
                "extraction_id": ext.id,
                "url": ext.url,
                "platform": ext.platform,
                "title": ext.title,
                "vibe": ext.vibe,
                "places": [p.data or {"name": p.name} for p in places],
                "trips": [t.data or {"persona": t.persona, "days": t.days} for t in trips],
                "created_at": ext.created_at.isoformat() if ext.created_at else None,
            }
    except Exception as e:
        logger.warning("Read failed for extraction %s: %s", extraction_id, e)
        return None


async def get_trip(trip_id: str) -> dict | None:
    try:
        async with async_session() as session:
            t = await session.get(Trip, trip_id)
            if t is None:
                return None
            return t.data or {
                "persona": t.persona,
                "title": t.title,
                "days": t.days,
                "total_cost_per_person": t.total_cost_per_person,
            }
    except Exception as e:
        logger.warning("Read failed for trip %s: %s", trip_id, e)
        return None


async def list_extractions(limit: int = 50) -> list[dict]:
    try:
        async with async_session() as session:
            rows = (await session.execute(
                select(Extraction).order_by(Extraction.created_at.desc()).limit(limit)
            )).scalars().all()
            return [
                {
                    "extraction_id": r.id,
                    "url": r.url,
                    "platform": r.platform,
                    "title": r.title,
                    "vibe": r.vibe,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                }
                for r in rows
            ]
    except Exception as e:
        logger.warning("List extractions failed: %s", e)
        return []

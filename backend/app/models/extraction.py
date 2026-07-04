import uuid
from datetime import datetime, timezone
from sqlalchemy import String, Text, DateTime, Float, Integer, JSON
from sqlalchemy.orm import Mapped, mapped_column
from app.models.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Extraction(Base):
    __tablename__ = "extractions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    url: Mapped[str] = mapped_column(Text, nullable=False)
    platform: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=True)
    transcript: Mapped[str] = mapped_column(Text, nullable=True)
    raw_places: Mapped[dict] = mapped_column(JSON, nullable=True)
    vibe: Mapped[str] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    extraction_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    persona: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=True)
    days: Mapped[dict] = mapped_column(JSON, nullable=False)
    total_cost_per_person: Mapped[float] = mapped_column(Float, nullable=False)
    # Full plan dict (summary, cost_breakdown, tours, ...) for exact retrieval.
    data: Mapped[dict] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)


class ResolvedPlace(Base):
    __tablename__ = "resolved_places"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    extraction_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=True)
    lat: Mapped[float] = mapped_column(Float, nullable=True)
    lng: Mapped[float] = mapped_column(Float, nullable=True)
    rating: Mapped[float] = mapped_column(Float, nullable=True)
    price_level: Mapped[int] = mapped_column(Integer, nullable=True)
    google_place_id: Mapped[str] = mapped_column(String(100), nullable=True)
    data: Mapped[dict] = mapped_column(JSON, nullable=True)

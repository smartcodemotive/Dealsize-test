"""SQLAlchemy models for events and sync state."""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Date, DateTime, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Event(Base):
    """Unified market event. Deduplicated by (symbol, event_type, event_date)."""

    __tablename__ = "events"
    __table_args__ = (
        UniqueConstraint("symbol", "event_type", "event_date", name="uq_event_natural_key"),
        Index("ix_events_symbol_type_date", "symbol", "event_type", "event_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    event_date: Mapped[datetime] = mapped_column(Date, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    details: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.id),
            "symbol": self.symbol,
            "event_type": self.event_type,
            "event_date": self.event_date.isoformat() if self.event_date else None,
            "title": self.title,
            "details": self.details or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class SymbolSync(Base):
    """Tracks last sync time per symbol for rate-limiting (skip if synced in last hour)."""

    __tablename__ = "symbol_syncs"

    symbol: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_synced_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

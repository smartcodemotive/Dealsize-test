"""Pydantic schemas for API request/response."""

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EventResponse(BaseModel):
    id: UUID
    symbol: str
    event_type: str
    event_date: date
    title: str
    details: dict = Field(default_factory=dict)
    created_at: datetime

    model_config = {"from_attributes": True}


class EventsListResponse(BaseModel):
    data: list[EventResponse]
    total: int
    limit: int
    offset: int
    has_more: bool


class SyncRequest(BaseModel):
    symbols: list[str] = Field(default_factory=list, description="Symbols to sync")
    force: bool = False


class SyncResponse(BaseModel):
    status: str  # "completed" or "partial"
    symbols_synced: list[str] = Field(default_factory=list)
    symbols_skipped: list[str] = Field(default_factory=list)
    events_created: int = 0
    events_updated: int = 0
    errors: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str  # "ok" or "degraded"
    redis: str  # "up" / "down"
    database: str  # "up" / "down"

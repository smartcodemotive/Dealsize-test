"""Events API routes."""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas import EventResponse, EventsListResponse, SyncRequest, SyncResponse
from app.services.cache import (
    get_event_cached,
    get_events_list_cached,
    set_event_cached,
    set_events_list_cached,
)
from app.services.event_repository import get_event_by_id, list_events
from app.services.sync_service import run_sync

router = APIRouter(prefix="/api/v1/events", tags=["events"])

EVENT_TYPES = {"earnings", "dividend", "economic", "split"}
DEFAULT_LIMIT = 50
MAX_LIMIT = 500


@router.get("")
async def list_events_handler(
    symbols: str | None = Query(None, description="Comma-separated symbols"),
    event_type: str | None = Query(None, description="earnings, dividend, economic, split"),
    from_date: str | None = Query(None, description="YYYY-MM-DD"),
    to_date: str | None = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List events with optional filters. Response includes X-Cache: HIT or MISS."""
    symbol_list = [s.strip() for s in symbols.split(",")] if symbols else None
    if event_type and event_type.strip().lower() not in EVENT_TYPES:
        event_type = None
    from_date_parsed = None
    to_date_parsed = None
    if from_date:
        try:
            from_date_parsed = datetime.strptime(from_date, "%Y-%m-%d").date()
        except ValueError:
            pass
    if to_date:
        try:
            to_date_parsed = datetime.strptime(to_date, "%Y-%m-%d").date()
        except ValueError:
            pass

    cached = await get_events_list_cached(
        symbol_list, event_type, from_date, to_date, limit, offset
    )
    if cached is not None:
        return JSONResponse(
            content=cached,
            headers={"X-Cache": "HIT"},
        )

    events, total = await list_events(
        db,
        symbols=symbol_list,
        event_type=event_type.strip().lower() if event_type else None,
        from_date=from_date_parsed,
        to_date=to_date_parsed,
        limit=limit,
        offset=offset,
    )
    data = [EventResponse.model_validate(e.to_dict()) for e in events]
    payload = {
        "data": [d.model_dump(mode="json") for d in data],
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": offset + len(events) < total,
    }
    await set_events_list_cached(
        payload, symbol_list, event_type, from_date, to_date, limit, offset
    )
    return JSONResponse(
        content=payload,
        headers={"X-Cache": "MISS"},
    )


@router.get("/{event_id}")
async def get_event_handler(
    event_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get a single event by ID. Response includes X-Cache: HIT or MISS."""
    cached = await get_event_cached(str(event_id))
    if cached is not None:
        return JSONResponse(content=cached, headers={"X-Cache": "HIT"})
    event = await get_event_by_id(db, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    out = event.to_dict()
    await set_event_cached(str(event_id), out)
    return JSONResponse(
        content=out,
        headers={"X-Cache": "MISS"},
    )


@router.post("/sync", response_model=SyncResponse)
async def sync_events_handler(
    body: SyncRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger sync from providers for the given symbols. force=true ignores last-hour skip."""
    result = await run_sync(db, body.symbols, force=body.force)
    return SyncResponse(**result)

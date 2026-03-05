"""Event and sync state repository (DB access)."""

from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Event, SymbolSync


async def list_events(
    session: AsyncSession,
    *,
    symbols: list[str] | None = None,
    event_type: str | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = 50,
    offset: int = 0,
) -> tuple[list[Event], int]:
    """Return (events, total_count) with filters and pagination."""
    base = select(Event)
    count_stmt = select(func.count()).select_from(Event)

    if symbols:
        sym_upper = [s.strip().upper() for s in symbols if s.strip()]
        if sym_upper:
            base = base.where(Event.symbol.in_(sym_upper))
            count_stmt = count_stmt.where(Event.symbol.in_(sym_upper))
    if event_type:
        base = base.where(Event.event_type == event_type)
        count_stmt = count_stmt.where(Event.event_type == event_type)
    if from_date:
        base = base.where(Event.event_date >= from_date)
        count_stmt = count_stmt.where(Event.event_date >= from_date)
    if to_date:
        base = base.where(Event.event_date <= to_date)
        count_stmt = count_stmt.where(Event.event_date <= to_date)

    total = (await session.execute(count_stmt)).scalar() or 0

    base = base.order_by(Event.event_date.asc(), Event.symbol.asc())
    base = base.limit(limit).offset(offset)
    result = await session.execute(base)
    events = list(result.scalars().all())
    return events, total


async def get_event_by_id(session: AsyncSession, event_id: UUID) -> Event | None:
    """Fetch a single event by UUID."""
    stmt = select(Event).where(Event.id == event_id)
    result = await session.execute(stmt)
    return result.scalars().one_or_none()


async def upsert_events(session: AsyncSession, normalized_list: list[dict]) -> tuple[int, int]:
    """
    Upsert events by (symbol, event_type, event_date). Returns (created_count, updated_count).
    Each dict in normalized_list must have symbol, event_type, event_date, title, details.
    """
    created = 0
    updated = 0
    for n in normalized_list:
        stmt = select(Event).where(
            Event.symbol == n["symbol"],
            Event.event_type == n["event_type"],
            Event.event_date == n["event_date"],
        )
        existing = (await session.execute(stmt)).scalars().one_or_none()
        if existing:
            existing.title = n["title"]
            existing.details = n.get("details") or {}
            existing.updated_at = datetime.now(timezone.utc)
            updated += 1
        else:
            session.add(
                Event(
                    symbol=n["symbol"],
                    event_type=n["event_type"],
                    event_date=n["event_date"],
                    title=n["title"],
                    details=n.get("details") or {},
                )
            )
            created += 1
    await session.commit()
    return created, updated


async def get_symbols_synced_recently(
    session: AsyncSession, symbols: list[str], within_hours: float = 1.0
) -> list[str]:
    """Return symbols that have been synced within the last `within_hours`."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=within_hours)
    stmt = select(SymbolSync.symbol).where(
        SymbolSync.symbol.in_([s.upper() for s in symbols if s.strip()]),
        SymbolSync.last_synced_at >= cutoff,
    )
    result = await session.execute(stmt)
    return [row[0] for row in result.fetchall()]


async def mark_symbols_synced(session: AsyncSession, symbols: list[str]) -> None:
    """Update last_synced_at for given symbols."""
    now = datetime.now(timezone.utc)
    for sym in symbols:
        stmt = pg_insert(SymbolSync).values(
            symbol=sym.upper(),
            last_synced_at=now,
        ).on_conflict_do_update(
            index_elements=["symbol"],
            set_={"last_synced_at": now},
        )
        await session.execute(stmt)
    await session.commit()

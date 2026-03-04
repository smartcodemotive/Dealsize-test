"""Redis cache for events list and single event."""

import json
from typing import Any

from redis.asyncio import Redis

from app.config import settings

# Cache TTL in seconds (e.g. 5 minutes)
EVENTS_LIST_TTL = 300
EVENT_SINGLE_TTL = 600


def _cache_key_events_list(
    symbols: list[str] | None,
    event_type: str | None,
    from_date: str | None,
    to_date: str | None,
    limit: int,
    offset: int,
) -> str:
    parts = ["events", "list"]
    if symbols:
        parts.append("_".join(sorted(s.strip().upper() for s in symbols if s.strip())))
    if event_type:
        parts.append(event_type)
    if from_date:
        parts.append(str(from_date))
    if to_date:
        parts.append(str(to_date))
    parts.extend([str(limit), str(offset)])
    return ":".join(parts)


def _cache_key_event(event_id: str) -> str:
    return f"events:single:{event_id}"


async def get_redis() -> Redis:
    """Return async Redis client (caller should close or use as context manager)."""
    return Redis.from_url(settings.redis_url, decode_responses=True)


async def get_events_list_cached(
    symbols: list[str] | None,
    event_type: str | None,
    from_date: str | None,
    to_date: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any] | None:
    """Return cached list response or None if miss."""
    try:
        redis = await get_redis()
        try:
            key = _cache_key_events_list(symbols, event_type, from_date, to_date, limit, offset)
            raw = await redis.get(key)
            if raw is None:
                return None
            return json.loads(raw)
        finally:
            await redis.aclose()
    except Exception:
        return None


async def set_events_list_cached(
    payload: dict[str, Any],
    symbols: list[str] | None,
    event_type: str | None,
    from_date: str | None,
    to_date: str | None,
    limit: int,
    offset: int,
) -> None:
    """Store list response in cache."""
    try:
        redis = await get_redis()
        try:
            key = _cache_key_events_list(symbols, event_type, from_date, to_date, limit, offset)
            await redis.setex(key, EVENTS_LIST_TTL, json.dumps(payload, default=str))
        finally:
            await redis.aclose()
    except Exception:
        pass


async def get_event_cached(event_id: str) -> dict[str, Any] | None:
    """Return cached single event or None."""
    try:
        redis = await get_redis()
        try:
            raw = await redis.get(_cache_key_event(event_id))
            if raw is None:
                return None
            return json.loads(raw)
        finally:
            await redis.aclose()
    except Exception:
        return None


async def set_event_cached(event_id: str, payload: dict[str, Any]) -> None:
    """Store single event in cache."""
    try:
        redis = await get_redis()
        try:
            await redis.setex(_cache_key_event(event_id), EVENT_SINGLE_TTL, json.dumps(payload, default=str))
        finally:
            await redis.aclose()
    except Exception:
        pass


async def redis_ping() -> bool:
    """Return True if Redis is reachable."""
    try:
        redis = await get_redis()
        try:
            await redis.ping()
            return True
        finally:
            await redis.aclose()
    except Exception:
        return False

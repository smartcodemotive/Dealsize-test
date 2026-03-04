"""Sync market events from both providers into the database."""

from typing import Any

from providers.provider_a import ProviderA, ProviderUnavailableError as AUnavailable, RateLimitError as ARateLimit
from providers.provider_b import ProviderB, ProviderTimeoutError as BTimeout, RateLimitError as BRateLimit

from app.config import settings
from app.services.event_repository import get_symbols_synced_recently, mark_symbols_synced, upsert_events
from app.services.normalizers import deduplication_key, normalize_provider_a, normalize_provider_b
from sqlalchemy.ext.asyncio import AsyncSession

DAYS_AHEAD = 90
SKIP_WITHIN_HOURS = 1.0


async def run_sync(
    session: AsyncSession,
    symbols: list[str],
    force: bool = False,
) -> dict[str, Any]:
    """
    Fetch from both providers for the given symbols, normalize, deduplicate, and upsert.
    Returns dict with status, symbols_synced, symbols_skipped, events_created, events_updated, errors.
    """
    symbols = [s.strip().upper() for s in symbols if s.strip()]
    if not symbols:
        return {
            "status": "completed",
            "symbols_synced": [],
            "symbols_skipped": [],
            "events_created": 0,
            "events_updated": 0,
            "errors": [],
        }

    to_sync = symbols
    skipped: list[str] = []
    if not force:
        recently = await get_symbols_synced_recently(session, symbols, within_hours=SKIP_WITHIN_HOURS)
        skipped = recently
        to_sync = [s for s in symbols if s not in recently]

    if not to_sync:
        return {
            "status": "completed",
            "symbols_synced": [],
            "symbols_skipped": symbols,
            "events_created": 0,
            "events_updated": 0,
            "errors": [],
        }

    all_normalized: dict[tuple[str, str, str], dict[str, Any]] = {}
    errors: list[str] = []

    # Provider A
    try:
        async with ProviderA(api_key=settings.provider_a_api_key) as pa:
            raw_a = await pa.fetch_events(to_sync, days_ahead=DAYS_AHEAD)
            for raw in raw_a:
                n = normalize_provider_a(raw)
                if n:
                    key = deduplication_key(n)
                    if key not in all_normalized:
                        all_normalized[key] = n
    except ARateLimit as e:
        errors.append(f"Provider A: rate limit - {e}")
    except AUnavailable as e:
        errors.append(f"Provider A: unavailable - {e}")
    except Exception as e:
        errors.append(f"Provider A: {type(e).__name__} - {e}")

    # Provider B (paginated)
    try:
        async with ProviderB(api_key=settings.provider_b_api_key) as pb:
            cursor: str | None = None
            while True:
                result = await pb.fetch_events(to_sync, days_ahead=DAYS_AHEAD, cursor=cursor, page_size=20)
                for raw in result.get("events") or []:
                    n = normalize_provider_b(raw)
                    if n:
                        key = deduplication_key(n)
                        if key not in all_normalized:
                            all_normalized[key] = n
                pag = result.get("pagination") or {}
                if not pag.get("has_next"):
                    break
                cursor = pag.get("next_cursor")
                if not cursor:
                    break
    except BRateLimit as e:
        errors.append(f"Provider B: rate limit - {e}")
    except BTimeout as e:
        errors.append(f"Provider B: timeout - {e}")
    except Exception as e:
        errors.append(f"Provider B: {type(e).__name__} - {e}")

    normalized_list = list(all_normalized.values())
    created, updated = 0, 0
    if normalized_list:
        created, updated = await upsert_events(session, normalized_list)
    await mark_symbols_synced(session, to_sync)

    return {
        "status": "completed" if not errors else "partial",
        "symbols_synced": to_sync,
        "symbols_skipped": skipped,
        "events_created": created,
        "events_updated": updated,
        "errors": errors,
    }

"""Health check endpoint."""

from fastapi import APIRouter
from sqlalchemy import text

from app.database import _get_engine
from app.schemas import HealthResponse
from app.services.cache import redis_ping

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health():
    """Service health with Redis and DB status."""
    redis_ok = await redis_ping()
    db_ok = False
    try:
        async with _get_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass
    status = "ok" if (redis_ok and db_ok) else "degraded"
    return HealthResponse(
        status=status,
        redis="up" if redis_ok else "down",
        database="up" if db_ok else "down",
    )

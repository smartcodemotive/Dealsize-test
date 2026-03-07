"""Async database engine and session.

Engine and session maker are created in lifespan so they are bound to the
app's event loop (fixes pytest + asyncpg "attached to a different loop").
"""

from collections.abc import AsyncGenerator

from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine, async_sessionmaker, create_async_engine

from app.config import settings


class Base(DeclarativeBase):
    """SQLAlchemy declarative base."""


_engine: AsyncEngine | None = None
_async_session_maker: async_sessionmaker[AsyncSession] | None = None


def _get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Database not initialized; app lifespan has not run.")
    return _engine


def _get_async_session_maker() -> async_sessionmaker[AsyncSession]:
    if _async_session_maker is None:
        raise RuntimeError("Database not initialized; app lifespan has not run.")
    return _async_session_maker


# Set by init_db(); health endpoint uses this.
engine: AsyncEngine | None = None


async def init_db() -> None:
    """Create engine, session maker, and tables. Called from app lifespan."""
    global _engine, _async_session_maker, engine
    if _engine is not None:
        return
    _engine = create_async_engine(
        settings.database_url,
        echo=settings.env == "development",
    )
    _async_session_maker = async_sessionmaker(
        _engine, class_=AsyncSession, expire_on_commit=False
    )
    from app import models  # noqa: F401 - register models with Base
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    engine = _engine


async def shutdown_db() -> None:
    """Dispose engine and clear globals. Called when app lifespan exits (e.g. between tests)."""
    global _engine, _async_session_maker, engine
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _async_session_maker = None
    engine = None


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with _get_async_session_maker()() as session:
        try:
            yield session
        finally:
            await session.close()

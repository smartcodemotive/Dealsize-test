from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import events, health
from app.database import init_db, shutdown_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    try:
        yield
    finally:
        await shutdown_db()


app = FastAPI(
    title="Market Events Service",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(events.router)

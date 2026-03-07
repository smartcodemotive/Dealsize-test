"""API tests using AsyncClient so app and DB run in the same event loop."""

import pytest
import httpx
from httpx import ASGITransport

from app.main import app, lifespan


@pytest.fixture
async def client():
    """Async client; lifespan runs here so engine is created in the test's event loop."""
    async with lifespan(app):
        transport = ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac


@pytest.mark.asyncio
async def test_health_returns_ok(client: httpx.AsyncClient):
    """Health endpoint returns status and component status."""
    r = await client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")
    assert data.get("redis") in ("up", "down")
    assert data.get("database") in ("up", "down")


@pytest.mark.asyncio
async def test_events_list_empty(client: httpx.AsyncClient):
    """GET /api/v1/events returns 200 and list shape (may be empty)."""
    r = await client.get("/api/v1/events")
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "has_more" in data
    assert data["limit"] == 50
    assert "X-Cache" in r.headers


@pytest.mark.asyncio
async def test_events_list_with_params(client: httpx.AsyncClient):
    """GET /api/v1/events with symbols and limit."""
    r = await client.get("/api/v1/events?symbols=AAPL,MSFT&limit=10&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["data"], list)
    assert data["limit"] == 10
    assert data["offset"] == 0


@pytest.mark.asyncio
async def test_events_sync_accepts_body(client: httpx.AsyncClient):
    """POST /api/v1/events/sync accepts symbols and force."""
    r = await client.post("/api/v1/events/sync", json={"symbols": ["AAPL", "MSFT"], "force": False})
    # May be 200 even if providers fail (partial)
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] in ("completed", "partial")
    assert "symbols_synced" in data
    assert "symbols_skipped" in data
    assert "events_created" in data
    assert "events_updated" in data
    assert "errors" in data


@pytest.mark.asyncio
async def test_events_get_404_for_unknown_id(client: httpx.AsyncClient):
    """GET /api/v1/events/{id} returns 404 for non-existent UUID."""
    r = await client.get("/api/v1/events/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404

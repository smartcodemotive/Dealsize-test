"""API tests using TestClient (mocked or real DB/Redis - use env or in-memory for CI)."""

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_returns_ok(client: TestClient):
    """Health endpoint returns status and component status."""
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] in ("ok", "degraded")
    assert data.get("redis") in ("up", "down")
    assert data.get("database") in ("up", "down")


def test_events_list_empty(client: TestClient):
    """GET /api/v1/events returns 200 and list shape (may be empty)."""
    r = client.get("/api/v1/events")
    assert r.status_code == 200
    data = r.json()
    assert "data" in data
    assert "total" in data
    assert "limit" in data
    assert "offset" in data
    assert "has_more" in data
    assert data["limit"] == 50
    assert "X-Cache" in r.headers


def test_events_list_with_params(client: TestClient):
    """GET /api/v1/events with symbols and limit."""
    r = client.get("/api/v1/events?symbols=AAPL,MSFT&limit=10&offset=0")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["data"], list)
    assert data["limit"] == 10
    assert data["offset"] == 0


def test_events_sync_accepts_body(client: TestClient):
    """POST /api/v1/events/sync accepts symbols and force."""
    r = client.post("/api/v1/events/sync", json={"symbols": ["AAPL", "MSFT"], "force": False})
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


def test_events_get_404_for_unknown_id(client: TestClient):
    """GET /api/v1/events/{id} returns 404 for non-existent UUID."""
    r = client.get("/api/v1/events/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404

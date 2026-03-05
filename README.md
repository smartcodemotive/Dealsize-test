# Market Events Service

Build a FastAPI service that aggregates financial market events (earnings, dividends, splits) from multiple providers and exposes a unified API.

**Time:** 2-3 days

## What You're Building

A service that:
- Fetches events from two external providers (simulated in `providers/`)
- Normalizes their different formats into a unified schema
- Stores in PostgreSQL with deduplication
- Caches with Redis
- Exposes a REST API

## API Spec

### `GET /api/v1/events`

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `symbols` | string | No | Comma-separated (e.g., `AAPL,MSFT`) |
| `event_type` | string | No | `earnings`, `dividend`, `economic`, `split` |
| `from_date` | string | No | YYYY-MM-DD |
| `to_date` | string | No | YYYY-MM-DD |
| `limit` | int | No | Default 50, max 500 |
| `offset` | int | No | Pagination offset |

Response:
```json
{
  "data": [
    {
      "id": "uuid",
      "symbol": "AAPL",
      "event_type": "earnings",
      "event_date": "2026-02-20",
      "title": "Q1 2026 Earnings Release",
      "details": {},
      "created_at": "2026-02-15T10:30:00Z"
    }
  ],
  "total": 150,
  "limit": 50,
  "offset": 0,
  "has_more": true
}
```

Include `X-Cache: HIT` or `X-Cache: MISS` header.

### `GET /api/v1/events/{event_id}`

Single event by ID.

### `POST /api/v1/events/sync`

```json
{
  "symbols": ["AAPL", "MSFT"],
  "force": false
}
```

Response:
```json
{
  "status": "completed",
  "symbols_synced": ["AAPL", "MSFT"],
  "symbols_skipped": [],
  "events_created": 12,
  "events_updated": 3,
  "errors": []
}
```

- `force: false` skips symbols synced in the last hour
- `force: true` always fetches fresh

### `GET /api/v1/health`

Service health with Redis/DB status.

## Providers

The `providers/` folder contains two simulated external APIs. They have different interfaces and return different data formats.

**Don't modify anything in `providers/`** - treat them like external APIs you can't control.


Check the docstrings for details on rate limits and error handling.

## Data Model

Design your schema considering:
- Both providers might return the same real-world event with different IDs
- You need deduplication
- Query by symbol, date range, type

## Deliverables

1. Working service (`docker-compose up` should work)
2. Your README with setup instructions and architecture notes
3. Tests for core logic

## Setup

```bash
docker-compose up -d
cp .env.example .env
poetry install
poetry run uvicorn app.main:app --reload --port 8000
```

## Setup (detailed)

1. **Start dependencies** (PostgreSQL and Redis):
   ```bash
   docker-compose up -d
   ```

2. **Configure environment**:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` if your DB/Redis ports differ (default: Postgres on 5433, Redis on 6380).

3. **Install and run**:
   ```bash
   poetry install
   poetry run uvicorn app.main:app --reload --port 8000
   ```

4. **Verify**: Open http://localhost:8000/docs for Swagger, or:
   - `GET http://localhost:8000/api/v1/health` — health check
   - `POST http://localhost:8000/api/v1/events/sync` with `{"symbols": ["AAPL", "MSFT"], "force": true}` — sync events
   - `GET http://localhost:8000/api/v1/events` — list events

**Tests** (Postgres and Redis should be running for full integration):
```bash
poetry run pytest tests/ -v
```

---

## Architecture notes

- **Data model**: Two tables — `events` (unified events) and `symbol_syncs` (last sync time per symbol). Events are deduplicated by natural key `(symbol, event_type, event_date)` so the same real-world event from different providers is stored once. Unique constraint and index support fast upserts and filtered queries.

- **Normalization**: Provider A (flat, `ticker`/`type`/`date`) and Provider B (nested, `instrument.symbol`/`event.category`/`event.scheduled_at`) are mapped to a single schema. Provider B categories are mapped as: `earnings_release` → `earnings`, `dividend_payment` → `dividend`, `stock_split` → `split`, `economic_indicator` → `economic`.

- **Sync**: `POST /api/v1/events/sync` fetches from both providers (Provider B pagination is followed until `has_next` is false), normalizes, deduplicates in memory by `(symbol, event_type, event_date)`, then upserts into Postgres. With `force: false`, symbols synced in the last hour are skipped. Provider rate limits and errors are caught; sync continues and errors are returned in the response (`status: "partial"` if any errors).

- **Caching**: List and single-event GETs are cached in Redis (key from query params for list, event id for single). Responses set `X-Cache: HIT` or `X-Cache: MISS` accordingly. TTLs: list 5 min, single event 10 min.

- **Assumptions**: (1) Event “identity” is symbol + type + date; (2) Sync marks all requested symbols as synced even if one provider fails; (3) Health is “degraded” if Redis or DB is down but the service still responds.

---

## Questions?

If something's unclear, document your assumptions and move on.

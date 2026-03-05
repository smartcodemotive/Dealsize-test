"""Tests for provider normalizers and deduplication."""

import pytest
from datetime import date

from app.services.normalizers import (
    deduplication_key,
    normalize_provider_a,
    normalize_provider_b,
)


class TestNormalizeProviderA:
    def test_valid_earnings(self):
        raw = {
            "event_id": "pa-AAPL-earnings-202602",
            "ticker": "AAPL",
            "type": "earnings",
            "date": "2026-02-20",
            "time": "10:00:00",
            "title": "AAPL Earnings - Feb 2026",
            "details": {"eps_estimate": 1.5, "revenue_estimate": 50000000000},
        }
        out = normalize_provider_a(raw)
        assert out is not None
        assert out["symbol"] == "AAPL"
        assert out["event_type"] == "earnings"
        assert out["event_date"] == date(2026, 2, 20)
        assert out["title"] == "AAPL Earnings - Feb 2026"
        assert out["details"] == raw["details"]

    def test_valid_dividend(self):
        raw = {
            "event_id": "pa-MSFT-dividend-202603",
            "ticker": "MSFT",
            "type": "dividend",
            "date": "2026-03-15",
            "time": None,
            "title": "MSFT Dividend",
            "metadata": {},
        }
        out = normalize_provider_a(raw)
        assert out is not None
        assert out["symbol"] == "MSFT"
        assert out["event_type"] == "dividend"
        assert out["event_date"] == date(2026, 3, 15)
        assert out["details"] == {}

    def test_invalid_type_ignored(self):
        raw = {
            "ticker": "AAPL",
            "type": "unknown",
            "date": "2026-02-20",
            "title": "X",
        }
        assert normalize_provider_a(raw) is None

    def test_missing_date_returns_none(self):
        raw = {"ticker": "AAPL", "type": "earnings", "title": "X"}
        assert normalize_provider_a(raw) is None

    def test_symbol_uppercased(self):
        raw = {"ticker": "aapl", "type": "split", "date": "2026-01-10", "title": "Split"}
        out = normalize_provider_a(raw)
        assert out is not None
        assert out["symbol"] == "AAPL"


class TestNormalizeProviderB:
    def test_valid_earnings_release(self):
        raw = {
            "id": "pb_AAPL_earnings_20260220_1234",
            "instrument": {"symbol": "AAPL", "exchange": "NASDAQ"},
            "event": {
                "category": "earnings_release",
                "scheduled_at": "2026-02-20T14:00:00Z",
                "title": "AAPL - Earnings Release",
                "earnings_data": {
                    "eps_consensus": 2.1,
                    "revenue_consensus": 100e9,
                    "period": "FY2026Q1",
                },
            },
            "provider_metadata": {"source": "provider_b"},
        }
        out = normalize_provider_b(raw)
        assert out is not None
        assert out["symbol"] == "AAPL"
        assert out["event_type"] == "earnings"
        assert out["event_date"] == date(2026, 2, 20)
        assert out["title"] == "AAPL - Earnings Release"
        assert "eps_consensus" in out["details"]

    def test_economic_indicator_mapped(self):
        raw = {
            "id": "pb_CPI_econ_20260301_5678",
            "instrument": {"symbol": "CPI", "exchange": "NYSE"},
            "event": {
                "category": "economic_indicator",
                "scheduled_at": "2026-03-01T09:00:00Z",
                "title": "CPI - Economic Indicator",
                "economic_data": {
                    "indicator_name": "CPI",
                    "previous_value": 3.2,
                    "forecast_value": 3.0,
                },
            },
        }
        out = normalize_provider_b(raw)
        assert out is not None
        assert out["event_type"] == "economic"
        assert out["details"].get("indicator_name") == "CPI"

    def test_stock_split_mapped(self):
        raw = {
            "id": "pb_GOOG_split_20260401_9999",
            "instrument": {"symbol": "GOOG"},
            "event": {
                "category": "stock_split",
                "scheduled_at": "2026-04-01T08:00:00Z",
                "title": "GOOG - Stock Split",
            },
        }
        out = normalize_provider_b(raw)
        assert out is not None
        assert out["event_type"] == "split"
        assert out["symbol"] == "GOOG"

    def test_missing_instrument_returns_none(self):
        raw = {"id": "x", "event": {"category": "earnings_release", "scheduled_at": "2026-02-20T10:00:00Z"}}
        assert normalize_provider_b(raw) is None

    def test_unknown_category_returns_none(self):
        raw = {
            "instrument": {"symbol": "AAPL"},
            "event": {"category": "unknown_type", "scheduled_at": "2026-02-20T10:00:00Z"},
        }
        assert normalize_provider_b(raw) is None


class TestDeduplicationKey:
    def test_key_from_normalized(self):
        n = {"symbol": "AAPL", "event_type": "earnings", "event_date": date(2026, 2, 20)}
        assert deduplication_key(n) == ("AAPL", "earnings", "2026-02-20")

    def test_same_key_same_event(self):
        n1 = {"symbol": "msft", "event_type": "DIVIDEND", "event_date": date(2026, 3, 1)}
        n2 = {"symbol": "MSFT", "event_type": "dividend", "event_date": date(2026, 3, 1)}
        assert deduplication_key(n1) == deduplication_key(n2)

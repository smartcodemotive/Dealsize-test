"""Normalize provider-specific event formats to unified schema."""

from datetime import datetime
from typing import Any

# Unified internal shape (before DB): symbol, event_type, event_date (date), title, details
EVENT_TYPES = {"earnings", "dividend", "economic", "split"}

# Provider B category -> API event_type
PROVIDER_B_TYPE_MAP = {
    "earnings_release": "earnings",
    "dividend_payment": "dividend",
    "stock_split": "split",
    "economic_indicator": "economic",
}


def normalize_provider_a(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convert Provider A event to unified format. Returns None if invalid."""
    try:
        event_type = (raw.get("type") or "").strip().lower()
        if event_type not in ("earnings", "dividend", "split"):
            return None
        date_str = raw.get("date")
        if not date_str:
            return None
        event_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        return {
            "symbol": (raw.get("ticker") or "").strip().upper(),
            "event_type": event_type,
            "event_date": event_date,
            "title": (raw.get("title") or "").strip() or f"{raw.get('ticker', '')} {event_type}",
            "details": raw.get("details") or {},
        }
    except (ValueError, TypeError, AttributeError):
        return None


def normalize_provider_b(raw: dict[str, Any]) -> dict[str, Any] | None:
    """Convert Provider B event to unified format. Returns None if invalid."""
    try:
        instrument = raw.get("instrument") or {}
        event_block = raw.get("event") or {}
        symbol = (instrument.get("symbol") or "").strip().upper()
        if not symbol:
            return None
        category = (event_block.get("category") or "").strip().lower()
        event_type = PROVIDER_B_TYPE_MAP.get(category)
        if not event_type:
            return None
        scheduled = event_block.get("scheduled_at")
        if not scheduled:
            return None
        # Parse "2026-02-20T10:00:00Z" or similar
        if "T" in scheduled:
            event_date = datetime.fromisoformat(scheduled.replace("Z", "+00:00")).date()
        else:
            event_date = datetime.strptime(scheduled[:10], "%Y-%m-%d").date()
        title = (event_block.get("title") or "").strip() or f"{symbol} {event_type}"
        details = _extract_provider_b_details(event_block, category)
        return {
            "symbol": symbol,
            "event_type": event_type,
            "event_date": event_date,
            "title": title,
            "details": details,
        }
    except (ValueError, TypeError, AttributeError, KeyError):
        return None


def _extract_provider_b_details(event_block: dict[str, Any], category: str) -> dict[str, Any]:
    """Extract details from Provider B nested event block."""
    details: dict[str, Any] = {}
    if category == "earnings_release" and "earnings_data" in event_block:
        ed = event_block["earnings_data"]
        details = {
            "eps_consensus": ed.get("eps_consensus"),
            "revenue_consensus": ed.get("revenue_consensus"),
            "period": ed.get("period"),
        }
    elif category == "dividend_payment" and "dividend_data" in event_block:
        dd = event_block["dividend_data"]
        details = {
            "amount_per_share": dd.get("amount_per_share"),
            "currency": dd.get("currency"),
            "ex_dividend_date": dd.get("ex_dividend_date"),
        }
    elif category == "economic_indicator" and "economic_data" in event_block:
        ec = event_block["economic_data"]
        details = {
            "indicator_name": ec.get("indicator_name"),
            "previous_value": ec.get("previous_value"),
            "forecast_value": ec.get("forecast_value"),
        }
    elif category == "stock_split" and "event" in event_block:
        # Provider B doesn't add split ratio in the sample; keep empty or merge from A if needed
        pass
    return {k: v for k, v in details.items() if v is not None}


def deduplication_key(normalized: dict[str, Any]) -> tuple[str, str, str]:
    """Return (symbol, event_type, event_date_iso) for deduplication."""
    d = normalized.get("event_date")
    if hasattr(d, "isoformat"):
        date_iso = d.isoformat()
    else:
        date_iso = str(d)
    return (
        (normalized.get("symbol") or "").upper(),
        (normalized.get("event_type") or "").lower(),
        date_iso,
    )

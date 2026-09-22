"""Kalshi scraper: the KXFED series ("Fed funds rate after <Month> meeting?").

Kalshi does not list "what will the Fed do?" as one bucket per outcome. It lists a ladder of
contracts, each asking "will the upper bound of the Fed's target range end ABOVE X%?". The
probabilities must fall as X rises. Differencing neighbouring rungs recovers bucket
probabilities (see ``pmq.pricing.coherence``), which is how we compare with Polymarket.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import httpx

from pmq.ingest.http import get_json
from pmq.ingest.models import Market, Snapshot

BASE_URL = "https://api.elections.kalshi.com/trade-api/v2"
SERIES = "KXFED"
_MONTHS = {
    m: i
    for i, m in enumerate(
        ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], 1
    )
}
_EVENT_TICKER = re.compile(r"^KXFED-(\d{2})([A-Z]{3})$")


def _parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _dollars(value: Any) -> float | None:
    # Kalshi quotes prices as dollar strings ("0.6000") for a contract that pays $1.
    return None if value in (None, "") else float(value)


def event_key_for(event_ticker: str) -> str:
    match = _EVENT_TICKER.match(event_ticker)
    if not match:
        raise ValueError(f"unexpected Kalshi event ticker: {event_ticker}")
    year, month = 2000 + int(match.group(1)), _MONTHS[match.group(2)]
    return f"fomc-{year}-{month:02d}"


def parse_event(event: dict[str, Any], fetched_at: datetime) -> tuple[list[Market], list[Snapshot]]:
    key = event_key_for(event["event_ticker"])
    markets: list[Market] = []
    snapshots: list[Snapshot] = []
    for raw in event.get("markets", []):
        if raw.get("strike_type") != "greater":
            continue  # only "above X" rungs are modelled
        market_id = f"kalshi:{raw['ticker']}"
        result = raw.get("result") or ""
        markets.append(
            Market(
                market_id=market_id,
                venue="kalshi",
                native_id=raw["ticker"],
                event_key=key,
                title=raw["title"],
                outcome_label=raw.get("yes_sub_title", ""),
                kind="threshold",
                strike_pct=float(raw["floor_strike"]),
                resolution_rule=raw.get("rules_primary"),
                close_time=_parse_time(raw.get("close_time")),
                resolved_yes={"yes": True, "no": False}.get(result),
            )
        )
        snapshots.append(
            Snapshot(
                market_id=market_id,
                ts=fetched_at,
                best_bid=_dollars(raw.get("yes_bid_dollars")),
                best_ask=_dollars(raw.get("yes_ask_dollars")),
                bid_size=_dollars(raw.get("yes_bid_size_fp")),
                ask_size=_dollars(raw.get("yes_ask_size_fp")),
                last_price=_dollars(raw.get("last_price_dollars")),
                volume_24h=_dollars(raw.get("volume_24h_fp")),
            )
        )
    return markets, snapshots


def fetch_snapshots(client: httpx.Client) -> tuple[list[Market], list[Snapshot], list[Any]]:
    now = datetime.now(UTC)
    payload = get_json(
        client,
        f"{BASE_URL}/events",
        {"series_ticker": SERIES, "status": "open", "with_nested_markets": "true", "limit": 20},
    )
    events = [e for e in payload["events"] if _EVENT_TICKER.match(e["event_ticker"])]
    markets: list[Market] = []
    snapshots: list[Snapshot] = []
    for event in events:
        m, s = parse_event(event, now)
        markets += m
        snapshots += s
    return markets, snapshots, events

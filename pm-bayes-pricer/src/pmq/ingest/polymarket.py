"""Polymarket scraper: FOMC "Fed Decision in <Month>?" events.

Polymarket lists one yes/no market per possible outcome (no change, 25 bps cut, ...). Their
"Yes" prices across the outcomes should add up to about 100%; they usually add up to a bit more,
and that excess is the venue's cushion (see ``pmq.pricing.clean``).
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from pmq.ingest.http import get_json
from pmq.ingest.models import Market, Snapshot

GAMMA_URL = "https://gamma-api.polymarket.com"
CLOB_URL = "https://clob.polymarket.com"
FED_TAG = "fed-rates"
_FOMC_SLUG = re.compile(r"^fed-decision-in-[a-z]+")

# Polymarket's own wording for each answer -> change in the Fed's upper bound, in basis points.
_BUCKET_BPS = {
    "50+ bps decrease": -50,
    "25 bps decrease": -25,
    "no change": 0,
    "25 bps increase": 25,
    "50+ bps increase": 50,
}


def _parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value.replace("Z", "+00:00")) if value else None


def _to_float(value: Any) -> float | None:
    return None if value is None else float(value)


def event_key_for(event: dict[str, Any]) -> str:
    """'fomc-2026-10' - built from the event's end date, which falls in the meeting month."""
    end = _parse_time(event["endDate"])
    assert end is not None
    return f"fomc-{end.year}-{end.month:02d}"


def parse_event(event: dict[str, Any], fetched_at: datetime) -> tuple[list[Market], list[Snapshot]]:
    """Turn one Polymarket event payload into normalised markets and price snapshots."""
    key = event_key_for(event)
    markets: list[Market] = []
    snapshots: list[Snapshot] = []
    for raw in event["markets"]:
        label = raw.get("groupItemTitle", "")
        bps = _BUCKET_BPS.get(label.strip().lower())
        if bps is None:
            continue  # an outcome we do not model yet; skipping is safer than guessing
        market_id = f"polymarket:{raw['id']}"
        resolved_yes = None
        if raw.get("closed"):
            yes_price = float(json.loads(raw["outcomePrices"])[0])
            resolved_yes = True if yes_price > 0.99 else False if yes_price < 0.01 else None
        markets.append(
            Market(
                market_id=market_id,
                venue="polymarket",
                native_id=str(raw["id"]),
                event_key=key,
                title=raw["question"],
                outcome_label=label,
                kind="bucket",
                bucket_bps=bps,
                resolution_rule=(raw.get("description") or event.get("description")),
                close_time=_parse_time(raw.get("endDate")),
                resolved_yes=resolved_yes,
            )
        )
        snapshots.append(
            Snapshot(
                market_id=market_id,
                ts=fetched_at,
                best_bid=_to_float(raw.get("bestBid")),
                best_ask=_to_float(raw.get("bestAsk")),
                last_price=_to_float(raw.get("lastTradePrice")),
                volume_24h=_to_float(raw.get("volume24hr")),
            )
        )
    return markets, snapshots


def fetch_open_fomc_events(client: httpx.Client) -> list[dict[str, Any]]:
    events = get_json(
        client,
        f"{GAMMA_URL}/events",
        {"closed": "false", "limit": 200, "tag_slug": FED_TAG},
    )
    return [e for e in events if _FOMC_SLUG.match(e.get("slug", ""))]


def fetch_snapshots(client: httpx.Client) -> tuple[list[Market], list[Snapshot], list[Any]]:
    """Return markets, snapshots and the raw payloads they were parsed from."""
    now = datetime.now(UTC)
    events = fetch_open_fomc_events(client)
    markets: list[Market] = []
    snapshots: list[Snapshot] = []
    for event in events:
        m, s = parse_event(event, now)
        markets += m
        snapshots += s
    return markets, snapshots, events


def parse_price_history(payload: dict[str, Any], market_id: str) -> list[Snapshot]:
    """Daily/hourly history from the CLOB ``prices-history`` endpoint (mid-ish price only)."""
    return [
        Snapshot(
            market_id=market_id,
            ts=datetime.fromtimestamp(point["t"], tz=UTC),
            last_price=float(point["p"]),
        )
        for point in payload.get("history", [])
    ]

"""Polymarket "What price will Bitcoin hit ...?" events (touch contracts).

Each market asks: *did Bitcoin touch $X at any moment between this market's start and the
event's end?* The strike title carries the direction as an arrow ("↑ 100,000" or "↓ 85,000").

A quirk found on the live API: when a strike is touched its market resolves Yes immediately,
and Polymarket **lists a fresh market at the same strike**, which only counts touches after its
own start time. So the window start must be the *market's* ``startDate``. Using the event's start
would wrongly treat the fresh market as already hit.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any

import httpx

from pmq.ingest.http import get_json
from pmq.ingest.models import Market, Snapshot
from pmq.ingest.polymarket import GAMMA_URL, _parse_time, _to_float

_TOUCH_SLUG = re.compile(r"^what-price-will-bitcoin-hit")
_STRIKE = re.compile(r"([↑↓])\s*\$?\s*([\d,]+(?:\.\d+)?)")


def parse_strike(title: str) -> tuple[str, float] | None:
    """'↑ 100,000' -> ('up', 100000.0); anything else -> None."""
    match = _STRIKE.search(title)
    if not match:
        return None
    return ("up" if match.group(1) == "↑" else "down"), float(match.group(2).replace(",", ""))


def parse_touch_event(
    event: dict[str, Any], fetched_at: datetime
) -> tuple[list[Market], list[Snapshot]]:
    event_start = _parse_time(event.get("startDate"))
    markets: list[Market] = []
    snapshots: list[Snapshot] = []
    for raw in event["markets"]:
        strike = parse_strike(raw.get("groupItemTitle", ""))
        if strike is None:
            continue
        direction, barrier = strike
        fee = raw.get("feeSchedule") or {}
        resolved_yes = None
        if raw.get("closed") and raw.get("outcomePrices"):
            yes_price = float(json.loads(raw["outcomePrices"])[0])
            resolved_yes = True if yes_price > 0.99 else False if yes_price < 0.01 else None
        market_id = f"polymarket:{raw['id']}"
        markets.append(
            Market(
                market_id=market_id,
                venue="polymarket",
                native_id=str(raw["id"]),
                event_key=f"btc-touch:{event['slug']}",
                title=raw["question"],
                outcome_label=raw["groupItemTitle"],
                kind="touch",
                barrier=barrier,
                direction=direction,  # type: ignore[arg-type]
                window_start=_parse_time(raw.get("startDate")) or event_start,
                fee_rate=_to_float(fee.get("rate")) if raw.get("feesEnabled") else 0.0,
                fee_exponent=_to_float(fee.get("exponent")) if raw.get("feesEnabled") else 1.0,
                resolution_rule=event.get("description"),
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


def fetch_open_btc_touch_events(client: httpx.Client) -> list[dict[str, Any]]:
    events = get_json(
        client,
        f"{GAMMA_URL}/events",
        {"closed": "false", "limit": 200, "tag_slug": "bitcoin"},
    )
    return [e for e in events if _TOUCH_SLUG.match(e.get("slug", ""))]


def fetch_snapshots(client: httpx.Client) -> tuple[list[Market], list[Snapshot], list[Any]]:
    now = datetime.now(UTC)
    events = fetch_open_btc_touch_events(client)
    markets: list[Market] = []
    snapshots: list[Snapshot] = []
    for event in events:
        m, s = parse_touch_event(event, now)
        markets += m
        snapshots += s
    return markets, snapshots, events

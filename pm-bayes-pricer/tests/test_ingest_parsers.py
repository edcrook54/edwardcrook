"""Contract tests on recorded real API responses: a venue changing format fails loudly."""

import json
from datetime import UTC, datetime
from pathlib import Path

from pmq.ingest import kalshi, polymarket

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 9, 20, tzinfo=UTC)


def _load(name: str):
    return json.loads((FIXTURES / name).read_text())


def test_polymarket_event_parses_into_five_buckets() -> None:
    event = _load("polymarket_fomc_oct_event.json")[0]
    markets, snapshots = polymarket.parse_event(event, NOW)
    assert {m.bucket_bps for m in markets} == {-50, -25, 0, 25, 50}
    assert all(m.event_key == "fomc-2026-10" and m.kind == "bucket" for m in markets)
    assert len(snapshots) == len(markets)
    assert all(s.best_bid is not None and s.best_bid <= s.best_ask for s in snapshots)  # type: ignore[operator]


def test_kalshi_event_parses_into_a_strike_ladder() -> None:
    event = _load("kalshi_kxfed_oct_events.json")["events"][0]
    markets, snapshots = kalshi.parse_event(event, NOW)
    strikes = sorted(m.strike_pct for m in markets if m.strike_pct is not None)
    assert strikes[0] == 2.75 and strikes[-1] == 5.25
    assert all(m.event_key == "fomc-2026-10" and m.kind == "threshold" for m in markets)
    assert all(0 <= (s.last_price or 0) <= 1 for s in snapshots)


def test_both_venues_agree_on_the_event_key() -> None:
    assert kalshi.event_key_for("KXFED-27JAN") == "fomc-2027-01"
    assert kalshi.event_key_for("KXFED-26DEC") == "fomc-2026-12"


def test_price_history_becomes_timestamped_snapshots() -> None:
    history = polymarket.parse_price_history(
        _load("polymarket_prices_history.json"), "polymarket:1"
    )
    assert len(history) > 10
    assert history == sorted(history, key=lambda s: s.ts)

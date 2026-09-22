import json
from datetime import UTC, datetime
from pathlib import Path

from pmq.ingest import binance, kraken_spot, polymarket_crypto

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 9, 21, tzinfo=UTC)


def test_strike_titles_parse_direction_and_price() -> None:
    assert polymarket_crypto.parse_strike("↑ 100,000") == ("up", 100000.0)
    assert polymarket_crypto.parse_strike("↓ 82,500") == ("down", 82500.0)
    assert polymarket_crypto.parse_strike("Yes") is None


def test_monthly_touch_event_becomes_touch_markets_with_event_level_window() -> None:
    event = json.loads((FIXTURES / "polymarket_btc_touch_monthly_event.json").read_text())[0]
    markets, snaps = polymarket_crypto.parse_touch_event(event, NOW)
    assert len(markets) == len(snaps) > 10
    assert all(m.kind == "touch" and m.barrier and m.direction for m in markets)
    ups = [m for m in markets if m.direction == "up"]
    downs = [m for m in markets if m.direction == "down"]
    assert ups and downs
    # Each market's window opens when *it* was listed (a re-listed strike starts later).
    raw = {str(r["id"]): r for r in event["markets"]}
    for m in markets:
        assert m.window_start is not None
        assert m.window_start.isoformat().startswith(raw[m.native_id]["startDate"][:19])
    assert all(m.fee_rate == 0.07 and m.fee_exponent == 1.0 for m in markets)


def test_kraken_ohlc_parses_into_candles() -> None:
    payload = json.loads((FIXTURES / "kraken_ohlc_60.json").read_text())
    candles = kraken_spot.parse_ohlc(payload)
    assert len(candles) == 721
    assert all(c.low <= min(c.open, c.close) <= max(c.open, c.close) <= c.high for c in candles)
    assert candles == sorted(candles, key=lambda c: c.ts)


def test_closed_market_without_prices_does_not_crash_the_parser() -> None:
    event = json.loads((FIXTURES / "polymarket_btc_touch_monthly_event.json").read_text())[0]
    event["markets"][0]["closed"] = True
    event["markets"][0].pop("outcomePrices", None)  # seen on the live API
    markets, _ = polymarket_crypto.parse_touch_event(event, NOW)
    assert markets[0].resolved_yes is None


def test_resolved_market_records_the_outcome() -> None:
    event = json.loads((FIXTURES / "polymarket_btc_touch_monthly_event.json").read_text())[0]
    event["markets"][0]["closed"] = True
    event["markets"][0]["outcomePrices"] = '["1", "0"]'
    event["markets"][1]["closed"] = True
    event["markets"][1]["outcomePrices"] = '["0", "1"]'
    markets, _ = polymarket_crypto.parse_touch_event(event, NOW)
    assert markets[0].resolved_yes is True and markets[1].resolved_yes is False


def test_binance_klines_parse_and_cover_the_expected_hours() -> None:
    rows = json.loads((FIXTURES / "binance_klines_1h.json").read_text())
    candles = binance.parse_klines(rows)
    assert len(candles) == 1000
    gaps = {(b.ts - a.ts).total_seconds() for a, b in zip(candles, candles[1:], strict=False)}
    assert gaps == {3600.0}
    assert all(c.low <= c.high for c in candles)

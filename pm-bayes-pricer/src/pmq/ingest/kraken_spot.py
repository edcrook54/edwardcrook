"""Live spot prices from Kraken's public API (no key needed).

The OHLC endpoint returns only the most recent 720 candles per interval, which at 1-hour
resolution is exactly 30 days: enough for the volatility features the model needs. The final
candle is still forming, so it is dropped when building features (but its high/low still count
towards "has the barrier already been touched?").
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import httpx

from pmq.ingest.http import get_json

KRAKEN_URL = "https://api.kraken.com/0/public"
PAIRS = {"XBT": "XBTUSD", "ETH": "ETHUSD", "SOL": "SOLUSD"}


@dataclass(frozen=True)
class Candle:
    ts: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float


def parse_ohlc(payload: dict[str, Any]) -> list[Candle]:
    if payload.get("error"):
        raise ValueError(f"Kraken error: {payload['error']}")
    rows = next(v for k, v in payload["result"].items() if k != "last")
    return [
        Candle(
            ts=datetime.fromtimestamp(int(r[0]), tz=UTC),
            open=float(r[1]),
            high=float(r[2]),
            low=float(r[3]),
            close=float(r[4]),
            volume=float(r[6]),
        )
        for r in rows
    ]


def fetch_hourly(client: httpx.Client, asset: str = "XBT") -> list[Candle]:
    payload = get_json(client, f"{KRAKEN_URL}/OHLC", {"pair": PAIRS[asset], "interval": 60})
    return parse_ohlc(payload)


def fetch_last_price(client: httpx.Client, asset: str = "XBT") -> float:
    payload = get_json(client, f"{KRAKEN_URL}/Ticker", {"pair": PAIRS[asset]})
    if payload.get("error"):
        raise ValueError(f"Kraken error: {payload['error']}")
    result = next(iter(payload["result"].values()))
    return float(result["c"][0])

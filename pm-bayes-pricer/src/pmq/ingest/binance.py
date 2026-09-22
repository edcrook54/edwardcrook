"""Binance public market data: the source Polymarket uses to settle Bitcoin touch markets.

Polymarket resolves "will Bitcoin hit $X?" on the **high/low of Binance BTC/USDT 1-minute
candles**. Kraken's BTC/USD price differs from that by tens to a hundred dollars at times, and
for a barrier only a few dollars away that difference decides the contract. Live barrier checks
therefore use Binance; Kraken is kept only as a cross-check (see ``pmq_spot_basis_bps``).

Uses ``data-api.binance.vision``, Binance's public market-data mirror (no key, read-only).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import httpx

from pmq.ingest.http import get_json
from pmq.ingest.kraken_spot import Candle

BASE_URL = "https://data-api.binance.vision/api/v3"
SYMBOLS = {"XBT": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT"}


def parse_klines(rows: list[list[Any]]) -> list[Candle]:
    return [
        Candle(
            ts=datetime.fromtimestamp(int(r[0]) / 1000, tz=UTC),
            open=float(r[1]),
            high=float(r[2]),
            low=float(r[3]),
            close=float(r[4]),
            volume=float(r[5]),
        )
        for r in rows
    ]


def fetch_hourly(client: httpx.Client, asset: str = "XBT", limit: int = 1000) -> list[Candle]:
    """The latest ``limit`` hourly candles (1000 hours = 41 days); the last one is still forming."""
    rows = get_json(
        client,
        f"{BASE_URL}/klines",
        {"symbol": SYMBOLS[asset], "interval": "1h", "limit": limit},
    )
    return parse_klines(rows)


def fetch_minutes(
    client: httpx.Client, asset: str, start: datetime, end: datetime, limit: int = 1000
) -> list[Candle]:
    """1-minute candles in ``[start, end)``; used for the partial hour where a window opens."""
    rows = get_json(
        client,
        f"{BASE_URL}/klines",
        {
            "symbol": SYMBOLS[asset],
            "interval": "1m",
            "startTime": int(start.timestamp() * 1000),
            "endTime": int(end.timestamp() * 1000) - 1,
            "limit": limit,
        },
    )
    return parse_klines(rows)


def fetch_last_price(client: httpx.Client, asset: str = "XBT") -> float:
    payload = get_json(client, f"{BASE_URL}/ticker/price", {"symbol": SYMBOLS[asset]})
    return float(payload["price"])

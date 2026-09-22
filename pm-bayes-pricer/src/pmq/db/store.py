"""Writing scraped records to Postgres. Every write is safe to repeat (idempotent)."""

from __future__ import annotations

import json
from collections.abc import Iterable, Sequence
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from pmq.ingest.models import Market, Snapshot

_UPSERT_MARKET = """
INSERT INTO core.market (
    market_id, venue, native_id, event_key, title, outcome_label, kind, bucket_bps,
    strike_pct, barrier, direction, window_start, fee_rate, fee_exponent,
    resolution_rule, close_time, resolved_at, resolved_yes
) VALUES (
    %(market_id)s, %(venue)s, %(native_id)s, %(event_key)s, %(title)s, %(outcome_label)s,
    %(kind)s, %(bucket_bps)s, %(strike_pct)s, %(barrier)s, %(direction)s, %(window_start)s,
    %(fee_rate)s, %(fee_exponent)s, %(resolution_rule)s, %(close_time)s,
    %(resolved_at)s, %(resolved_yes)s
)
ON CONFLICT (market_id) DO UPDATE SET
    title = EXCLUDED.title,
    close_time = EXCLUDED.close_time,
    resolution_rule = EXCLUDED.resolution_rule,
    resolved_at = COALESCE(EXCLUDED.resolved_at, core.market.resolved_at),
    resolved_yes = COALESCE(EXCLUDED.resolved_yes, core.market.resolved_yes)
"""

_INSERT_SNAPSHOT = """
INSERT INTO core.market_snapshot (
    market_id, ts, best_bid, best_ask, bid_size, ask_size, last_price, volume_24h
) VALUES (
    %(market_id)s, %(ts)s, %(best_bid)s, %(best_ask)s, %(bid_size)s, %(ask_size)s,
    %(last_price)s, %(volume_24h)s
)
ON CONFLICT (market_id, ts) DO NOTHING
"""


def upsert_markets(conn: psycopg.Connection[Any], markets: Sequence[Market]) -> None:
    with conn.cursor() as cur:
        cur.executemany(_UPSERT_MARKET, [m.model_dump() for m in markets])


_UPSERT_SPOT_BAR = """
INSERT INTO core.spot_bar (asset, ts, open, high, low, close, volume)
VALUES (%(asset)s, %(ts)s, %(open)s, %(high)s, %(low)s, %(close)s, %(volume)s)
ON CONFLICT (asset, ts) DO UPDATE SET
    high = EXCLUDED.high, low = EXCLUDED.low, close = EXCLUDED.close, volume = EXCLUDED.volume
"""

_INSERT_FAIR_VALUE = """
INSERT INTO core.fair_value (
    market_id, ts, model_id, p, p_low, p_high, mid, bid, ask, edge_buy, edge_sell,
    implied_vol, spot, sigma_median, already_touched
) VALUES (
    %(market_id)s, %(ts)s, %(model_id)s, %(p)s, %(p_low)s, %(p_high)s, %(mid)s, %(bid)s,
    %(ask)s, %(edge_buy)s, %(edge_sell)s, %(implied_vol)s, %(spot)s, %(sigma_median)s,
    %(already_touched)s
)
ON CONFLICT (market_id, ts, model_id) DO NOTHING
"""


def upsert_spot_bars(conn: psycopg.Connection[Any], rows: Sequence[dict[str, Any]]) -> None:
    with conn.cursor() as cur:
        cur.executemany(_UPSERT_SPOT_BAR, rows)


def insert_fair_values(conn: psycopg.Connection[Any], rows: Sequence[dict[str, Any]]) -> None:
    with conn.cursor() as cur:
        cur.executemany(_INSERT_FAIR_VALUE, rows)


def insert_snapshots(conn: psycopg.Connection[Any], snapshots: Sequence[Snapshot]) -> None:
    with conn.cursor() as cur:
        cur.executemany(_INSERT_SNAPSHOT, [s.model_dump() for s in snapshots])


def insert_raw(
    conn: psycopg.Connection[Any], venue: str, endpoint: str, payloads: Iterable[Any]
) -> None:
    """Keep the untouched API response so a parsing bug can be fixed and replayed later."""
    with conn.cursor() as cur:
        cur.executemany(
            "INSERT INTO raw.api_payload (venue, endpoint, http_status, payload)"
            " VALUES (%s, %s, 200, %s)",
            [(venue, endpoint, Jsonb(json.loads(json.dumps(p)))) for p in payloads],
        )

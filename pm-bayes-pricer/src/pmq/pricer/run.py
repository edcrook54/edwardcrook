"""The live pricer: ``python -m pmq.pricer.run once|loop``.

Every cycle: pull fresh Kraken candles and Polymarket quotes, price every open Bitcoin touch
market with the fitted model, store model-versus-market rows, and publish health metrics.

Safeguards (paper only, no orders are ever placed): if spot data is stale nothing is priced;
one venue failing does not stop the cycle; edges beyond a sanity cap are counted and flagged.
"""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx
import numpy as np
import psycopg
from prometheus_client import start_http_server

from pmq.config import get_settings
from pmq.crypto import live
from pmq.db import store
from pmq.eval import scoring
from pmq.ingest import binance, kraken_spot, polymarket_crypto
from pmq.ingest.http import make_client
from pmq.pricer import metrics

log = logging.getLogger("pmq.pricer")
SANITY_EDGE_CAP = 0.25  # an "edge" this big is more likely a data problem than an opportunity


@dataclass
class CycleStats:
    priced: int
    stale: bool
    max_abs_edge: float


def _next_hour(t: datetime) -> datetime:
    return t.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)


def _partial_candles(
    client: httpx.Client,
    asset: str,
    window_start: datetime,
    cache: dict[datetime, list[Any] | None],
) -> list[Any] | None:
    """1-minute Binance candles for the partial hour in which a window opened (cached)."""
    if window_start.minute == 0 and window_start.second == 0:
        return None
    if window_start not in cache:
        try:
            cache[window_start] = binance.fetch_minutes(
                client, asset, window_start, _next_hour(window_start)
            )
        except httpx.HTTPError:
            log.warning("could not fetch minute candles for %s", window_start)
            cache[window_start] = None
    return cache[window_start]


def _price_open_markets(
    client: httpx.Client,
    artifact: live.ModelArtifact,
    asset: str,
    candles: list[Any],
    spot: float,
    markets: list[Any],
    snapshots: list[Any],
    now: datetime,
) -> list[dict[str, Any]]:
    """Price every open touch market. Shared by the live loop and the dry-run command."""
    inputs = live.live_inputs_from_candles(candles)
    quotes = {q.market_id: q for q in snapshots}
    partial_cache: dict[datetime, list[Any] | None] = {}
    rows: list[dict[str, Any]] = []
    for m in markets:
        if m.barrier is None or m.direction is None or m.window_start is None:
            continue
        if m.close_time is None or m.close_time <= now or m.resolved_yes is not None:
            continue
        q = quotes[m.market_id]
        row = live.evaluate_market(
            artifact,
            inputs,
            spot,
            candles,
            barrier_price=m.barrier,
            direction=m.direction,
            window_start=m.window_start,
            window_end=m.close_time,
            now=now,
            bid=q.best_bid,
            ask=q.best_ask,
            fee_rate=m.fee_rate or 0.0,
            fee_exponent=m.fee_exponent or 1.0,
            partial=_partial_candles(client, asset, m.window_start, partial_cache),
        )
        rows.append(
            {
                **row,
                "market_id": m.market_id,
                "barrier": m.barrier,
                "direction": m.direction,
                "event": m.event_key,
                "days_left": (m.close_time - now).total_seconds() / 86400,
            }
        )
    return rows


def _record_basis(client: httpx.Client, asset: str, binance_spot: float) -> None:
    """Kraken vs Binance, in basis points: how far apart the two 'Bitcoin prices' are."""
    try:
        kraken = kraken_spot.fetch_last_price(client, asset)
    except (httpx.HTTPError, ValueError):
        return
    metrics.SPOT_BASIS_BPS.labels(asset).set((binance_spot / kraken - 1.0) * 1e4)


def price_cycle(
    conn: psycopg.Connection[Any],
    client: httpx.Client,
    artifact: live.ModelArtifact,
    asset: str,
    max_spot_age_seconds: int,
    now: datetime | None = None,
) -> CycleStats:
    now = now or datetime.now(UTC)
    candles = binance.fetch_hourly(client, asset)
    spot = binance.fetch_last_price(client, asset)
    age = (now - (candles[-2].ts + timedelta(hours=1))).total_seconds()
    metrics.CANDLE_AGE.labels(asset).set(age)
    metrics.SPOT.labels(asset).set(spot)
    _record_basis(client, asset, spot)
    with conn.transaction():
        store.upsert_spot_bars(
            conn,
            [
                {
                    "asset": asset,
                    "ts": c.ts,
                    "open": c.open,
                    "high": c.high,
                    "low": c.low,
                    "close": c.close,
                    "volume": c.volume,
                }
                for c in candles
            ],
        )
    if age > max_spot_age_seconds:
        log.warning("spot candles are %.0f s old; not pricing", age)
        return CycleStats(0, True, 0.0)

    markets, snapshots, raw = polymarket_crypto.fetch_snapshots(client)
    with conn.transaction():
        store.insert_raw(conn, "polymarket", "events:btc-touch", raw)
        store.upsert_markets(conn, markets)
        store.insert_snapshots(conn, snapshots)

    priced = _price_open_markets(client, artifact, asset, candles, spot, markets, snapshots, now)
    columns = (
        "market_id p p_low p_high mid bid ask edge_buy edge_sell implied_vol spot "
        "sigma_median already_touched"
    ).split()
    rows = [
        {**{c: r[c] for c in columns}, "ts": now, "model_id": artifact.model_id} for r in priced
    ]
    with conn.transaction():
        store.insert_fair_values(conn, rows)

    edges_buy = [r["edge_buy"] for r in rows if r["edge_buy"] is not None]
    edges_sell = [r["edge_sell"] for r in rows if r["edge_sell"] is not None]
    gaps = [abs(r["p"] - r["mid"]) for r in rows if r["mid"] is not None]
    all_edges = [abs(e) for e in edges_buy + edges_sell]
    metrics.MARKETS_PRICED.set(len(rows))
    metrics.MODEL_MARKET_GAP.set(float(np.mean(gaps)) if gaps else 0.0)
    metrics.BEST_EDGE_BUY.set(max(edges_buy, default=0.0))
    metrics.BEST_EDGE_SELL.set(max(edges_sell, default=0.0))
    metrics.SUSPICIOUS_EDGES.set(sum(e > SANITY_EDGE_CAP for e in all_edges))
    return CycleStats(len(rows), False, max(all_edges, default=0.0))


def _fmt(v: float | None) -> str:
    return "   -  " if v is None else f"{v:6.3f}"


def dry_run(client: httpx.Client, artifact: live.ModelArtifact, asset: str) -> list[dict[str, Any]]:
    """Price every open market and return the rows without touching any database."""
    now = datetime.now(UTC)
    candles = binance.fetch_hourly(client, asset)
    spot = binance.fetch_last_price(client, asset)
    markets, snapshots, _ = polymarket_crypto.fetch_snapshots(client)
    return _price_open_markets(client, artifact, asset, candles, spot, markets, snapshots, now)


_SCORE_SQL = """
WITH last_fv AS (
    SELECT DISTINCT ON (fv.market_id) fv.market_id, fv.p, fv.mid
    FROM core.fair_value fv JOIN core.market m USING (market_id)
    WHERE m.resolved_yes IS NOT NULL AND fv.mid IS NOT NULL
      AND fv.ts <= m.close_time - interval '1 day'
      AND m.close_time >= now() - interval '90 days'
    ORDER BY fv.market_id, fv.ts DESC
)
SELECT l.p, l.mid, m.resolved_yes::int
FROM last_fv l JOIN core.market m USING (market_id)
"""


def refresh_settlements_and_scores(conn: psycopg.Connection[Any], client: httpx.Client) -> int:
    """Pick up resolved outcomes, then score model and market on contracts priced 1 day out."""
    slugs = [
        r[0].split(":", 1)[1]
        for r in conn.execute(
            "SELECT DISTINCT event_key FROM core.market WHERE kind = 'touch'"
            " AND resolved_yes IS NULL AND close_time < now()"
        ).fetchall()
    ]
    now = datetime.now(UTC)
    for slug in slugs:
        events = client.get("https://gamma-api.polymarket.com/events", params={"slug": slug}).json()
        for event in events:
            markets, _ = polymarket_crypto.parse_touch_event(event, now)
            store.upsert_markets(conn, [m for m in markets if m.resolved_yes is not None])
    rows = conn.execute(_SCORE_SQL).fetchall()
    metrics.SCORED_CONTRACTS.set(len(rows))
    if rows:
        p, mid, y = (np.array(c, dtype=float) for c in zip(*rows, strict=True))
        metrics.BRIER_MODEL.set(scoring.brier(p, y))
        metrics.BRIER_MARKET.set(scoring.brier(mid, y))
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(prog="pmq.pricer.run")
    parser.add_argument("mode", choices=["once", "loop", "dry"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()
    artifact = live.ModelArtifact.load(settings.model_path)
    log.info("model %s trained through %s", artifact.model_id, artifact.trained_through)
    if args.mode == "dry":
        with make_client(settings.http_timeout_seconds) as client:
            rows = dry_run(client, artifact, settings.asset)
        for r in sorted(rows, key=lambda x: (x["event"], x["barrier"])):
            print(
                f"{r['event'][-34:]:34} {r['direction']:4} {r['barrier']:>9,.0f} "
                f"{r['days_left']:5.1f}d  model {_fmt(r['p'])} "
                f"[{_fmt(r['p_low'])},{_fmt(r['p_high'])}] "
                f"mid {_fmt(r['mid'])}  edge buy {_fmt(r['edge_buy'])} sell {_fmt(r['edge_sell'])} "
                f"iv {_fmt(r['implied_vol'])} touched={r['already_touched']}"
            )
        return
    if args.mode == "loop":
        start_http_server(settings.metrics_port)
    cycles = 0
    with (
        make_client(settings.http_timeout_seconds) as client,
        psycopg.connect(settings.database_url, autocommit=True) as conn,
    ):
        while True:
            started = time.monotonic()
            try:
                stats = price_cycle(
                    conn, client, artifact, settings.asset, settings.max_spot_age_seconds
                )
                if cycles % 60 == 0:
                    refresh_settlements_and_scores(conn, client)
                metrics.CYCLES.labels("ok").inc()
                if not stats.stale:
                    metrics.LAST_SUCCESS.set_to_current_time()
                log.info("priced %d markets (max |edge| %.3f)", stats.priced, stats.max_abs_edge)
            except Exception:
                metrics.CYCLES.labels("error").inc()
                log.exception("pricing cycle failed; will retry")
            metrics.CYCLE_SECONDS.observe(time.monotonic() - started)
            cycles += 1
            if args.mode == "once":
                return
            time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()

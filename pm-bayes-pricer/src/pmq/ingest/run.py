"""Command line entry point: ``python -m pmq.ingest once|loop``."""

from __future__ import annotations

import argparse
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx
import psycopg

from pmq.config import get_settings
from pmq.db import store
from pmq.ingest import kalshi, polymarket
from pmq.ingest.models import Market, Snapshot

log = logging.getLogger("pmq.ingest")

Fetcher = Callable[[httpx.Client], tuple[list[Market], list[Snapshot], list[Any]]]
VENUES: dict[str, Fetcher] = {
    "polymarket": polymarket.fetch_snapshots,
    "kalshi": kalshi.fetch_snapshots,
}


def collect_once(conn: psycopg.Connection[Any], client: httpx.Client) -> dict[str, int]:
    """Scrape every venue once. One venue failing must not stop the others."""
    stored: dict[str, int] = {}
    for venue, fetch in VENUES.items():
        try:
            markets, snapshots, raw = fetch(client)
        except Exception:
            log.exception("%s: fetch failed; will retry next cycle", venue)
            stored[venue] = 0
            continue
        with conn.transaction():
            store.insert_raw(conn, venue, "events", raw)
            store.upsert_markets(conn, markets)
            store.insert_snapshots(conn, snapshots)
        stored[venue] = len(snapshots)
        log.info("%s: stored %d snapshots", venue, len(snapshots))
    return stored


def main() -> None:
    parser = argparse.ArgumentParser(prog="pmq.ingest")
    parser.add_argument("mode", choices=["once", "loop"])
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    settings = get_settings()

    from pmq.ingest.http import make_client

    with (
        make_client(settings.http_timeout_seconds) as client,
        psycopg.connect(settings.database_url, autocommit=True) as conn,
    ):
        while True:
            collect_once(conn, client)
            if args.mode == "once":
                return
            time.sleep(settings.poll_interval_seconds)


if __name__ == "__main__":
    main()

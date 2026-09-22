"""Needs a real Postgres: skipped unless PMQ_TEST_DATABASE_URL is set (CI sets it)."""

import json
import os
from datetime import UTC, datetime
from pathlib import Path

import psycopg
import pytest

from pmq.db import store
from pmq.ingest import kalshi, polymarket

URL = os.environ.get("PMQ_TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(URL is None, reason="no test database configured")
FIXTURES = Path(__file__).parent / "fixtures"
SCHEMA = Path(__file__).parents[1] / "src/pmq/db/schema.sql"


def test_repeating_a_scrape_does_not_duplicate_rows() -> None:
    assert URL is not None
    now = datetime(2026, 9, 20, tzinfo=UTC)
    poly = json.loads((FIXTURES / "polymarket_fomc_oct_event.json").read_text())[0]
    kal = json.loads((FIXTURES / "kalshi_kxfed_oct_events.json").read_text())["events"][0]
    with psycopg.connect(URL, autocommit=True) as conn:
        conn.execute(SCHEMA.read_text())
        conn.execute("TRUNCATE core.market_snapshot, core.market CASCADE")
        for _ in range(2):
            for parse, event in ((polymarket.parse_event, poly), (kalshi.parse_event, kal)):
                markets, snaps = parse(event, now)
                store.upsert_markets(conn, markets)
                store.insert_snapshots(conn, snaps)
        n_markets = conn.execute("SELECT count(*) FROM core.market").fetchone()[0]  # type: ignore[index]
        n_snaps = conn.execute("SELECT count(*) FROM core.market_snapshot").fetchone()[0]  # type: ignore[index]
    assert n_markets == n_snaps == 5 + 11

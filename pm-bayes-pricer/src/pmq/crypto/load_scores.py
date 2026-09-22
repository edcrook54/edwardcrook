"""Load backtest results (outputs/*.parquet) into Postgres, for the Grafana research dashboard.

Run after ``make backtest``: ``python -m pmq.crypto.load_scores``.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

import polars as pl
import psycopg

from pmq.config import get_settings
from pmq.crypto import backtest as bt

ASSETS = ("XBT", "ETH", "SOL")


_SCORE_SQL = (
    "INSERT INTO core.backtest_score"
    " (asset, year, model, n, log_loss, brier, brier_skill_vs_naive, calibration_slope)"
    " VALUES (%(asset)s, %(year)s, %(model)s, %(n)s, %(log_loss)s, %(brier)s,"
    " %(brier_skill_vs_naive)s, %(calibration_slope)s)"
)
_DIFF_SQL = (
    "INSERT INTO core.backtest_diff (asset, model, vs, log_loss_diff, ci_low, ci_high)"
    " VALUES (%(asset)s, %(model)s, %(vs)s, %(log_loss_diff)s, %(ci_low)s, %(ci_high)s)"
)


def build_tables(outputs_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    scores: list[dict[str, Any]] = []
    diffs: list[dict[str, Any]] = []
    for asset in ASSETS:
        path = outputs_dir / f"backtest_{asset}.parquet"
        if not path.exists():
            continue
        df = pl.read_parquet(path)
        for row in bt.score_table(df).to_dicts():
            scores.append({"asset": asset, "year": 0, **row})  # year 0 = all years combined
        for row in bt.score_table(df, ["year"]).to_dicts():
            scores.append({"asset": asset, **row})
        for row in bt.loss_difference_table(df, "naive_2x").to_dicts():
            diffs.append({"asset": asset, **row})
    return scores, diffs


def load(database_url: str, outputs_dir: Path) -> tuple[int, int]:
    scores, diffs = build_tables(outputs_dir)
    with psycopg.connect(database_url, autocommit=True) as conn:
        conn.execute("TRUNCATE core.backtest_score, core.backtest_diff")
        with conn.cursor() as cur:
            if scores:
                cur.executemany(_SCORE_SQL, scores)
            if diffs:
                cur.executemany(_DIFF_SQL, diffs)
    return len(scores), len(diffs)


def main() -> None:
    parser = argparse.ArgumentParser(prog="pmq.crypto.load_scores")
    parser.add_argument("--outputs", default="outputs")
    args = parser.parse_args()
    n_scores, n_diffs = load(get_settings().database_url, Path(args.outputs))
    print(f"loaded {n_scores} score rows and {n_diffs} diff rows")


if __name__ == "__main__":
    main()

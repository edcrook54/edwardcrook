"""Kraken tick data -> 1-minute OHLCV bars, cached as Parquet.

The raw exports are headerless CSVs with three columns: ``unixtime, price, volume``. Loading
them with a header guess silently eats the first trade, so the schema is always explicit here.

Why 1-minute bars? The venues we compare against settle "did it hit $X?" contracts on
1-minute candle highs and lows, so a 1-minute high/low bar is exactly the information needed
to label a contract the same way the venue would. Bars are also ~10,000x smaller than ticks,
which is what makes 12 years of research fit in memory.
"""

from __future__ import annotations

from pathlib import Path

import polars as pl

TICK_COLUMNS = ["unixtime", "price", "volume"]
TICK_SCHEMA = {"unixtime": pl.Int64, "price": pl.Float64, "volume": pl.Float64}
BAR_SECONDS = 60


def scan_ticks(path: str | Path) -> pl.LazyFrame:
    """Lazily read one tick CSV (never loads the whole file until collected)."""
    return pl.scan_csv(
        path, has_header=False, new_columns=TICK_COLUMNS, schema_overrides=TICK_SCHEMA
    )


def ticks_to_minute_bars(ticks: pl.LazyFrame) -> pl.LazyFrame:
    """Aggregate ticks into 1-minute open/high/low/close/volume bars.

    Rows are stably sorted by time first so that "open" and "close" mean the first and last
    trade of the minute even if the export has a few out-of-order rows. Minutes with no trades
    simply have no bar (we never invent prices); resampling code forward-fills where needed.
    """
    return (
        ticks.filter((pl.col("price") > 0) & (pl.col("volume") >= 0))
        .sort("unixtime", maintain_order=True)
        .with_columns(((pl.col("unixtime") // BAR_SECONDS) * BAR_SECONDS).alias("minute"))
        .group_by("minute", maintain_order=True)
        .agg(
            pl.col("price").first().alias("open"),
            pl.col("price").max().alias("high"),
            pl.col("price").min().alias("low"),
            pl.col("price").last().alias("close"),
            pl.col("volume").sum().alias("volume"),
            pl.len().alias("n_trades"),
        )
        .with_columns(
            pl.from_epoch("minute", time_unit="s").dt.replace_time_zone("UTC").alias("ts")
        )
        .drop("minute")
        .select("ts", "open", "high", "low", "close", "volume", "n_trades")
    )


def build_bar_cache(csv_path: str | Path, out_path: str | Path) -> Path:
    """Stream a tick CSV into a Parquet file of 1-minute bars."""
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    ticks_to_minute_bars(scan_ticks(csv_path)).sink_parquet(out)
    return out


def load_bars(path: str | Path) -> pl.DataFrame:
    return pl.read_parquet(path).sort("ts")


def resample(bars: pl.DataFrame, every: str) -> pl.DataFrame:
    """Aggregate 1-minute bars to a coarser frequency (e.g. ``"5m"``, ``"1h"``, ``"1d"``)."""
    return (
        bars.sort("ts")
        .group_by_dynamic("ts", every=every, closed="left", label="left")
        .agg(
            pl.col("open").first(),
            pl.col("high").max(),
            pl.col("low").min(),
            pl.col("close").last(),
            pl.col("volume").sum(),
            pl.col("n_trades").sum(),
        )
    )

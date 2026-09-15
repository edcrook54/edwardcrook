"""
Kraken tick data loader.

Kraken time-and-sales CSV exports have NO header row and three columns:
unixtime, price, volume. Always load with header=None and explicit names,
or every downstream step silently mis-parses the first row as data.
"""

import logging
from pathlib import Path

import polars as pl

TICK_COLUMNS = ["unixtime", "price", "volume"]
TICK_SCHEMA = {"unixtime": pl.Int64, "price": pl.Float64, "volume": pl.Float64}

logger = logging.getLogger(__name__)


class KrakenTickLoader:
    """Loads raw Kraken time-and-sales CSV exports into Polars DataFrames.

    Encapsulates the one hard-won rule for this data source: no header row,
    three columns (unixtime, price, volume), and duplicate ticks/out-of-order
    rows do occasionally show up in the raw exports.
    """

    def load(self, path: str | Path) -> pl.DataFrame:
        """Load a single raw Kraken tick CSV into a Polars DataFrame."""
        df = pl.read_csv(
            path,
            has_header=False,
            new_columns=TICK_COLUMNS,
            schema_overrides=TICK_SCHEMA,
        )
        df = (
            df.with_columns(
                pl.from_epoch("unixtime", time_unit="s").alias("timestamp")
            )
            .sort("timestamp")
            .unique(subset=["timestamp", "price", "volume"], keep="first", maintain_order=True)
        )
        return df

    def load_all(self, asset_paths: dict[str, str | Path]) -> dict[str, pl.DataFrame]:
        """Load tick data for multiple assets into the shared assets-dict pattern
        used throughout this project, e.g. {'SOL': df, 'BCH': df, 'ADA': df, 'XRP': df}.
        """
        assets: dict[str, pl.DataFrame] = {}
        for ticker, path in asset_paths.items():
            df = self.load(path)
            start, end = df["timestamp"].min(), df["timestamp"].max()
            logger.info(
                "%s: %d ticks, %s -> %s", ticker, df.height, start, end
            )
            print(f"{ticker}: {df.height:,} ticks | {start} -> {end}")
            assets[ticker] = df
        return assets


def load_kraken_ticks(path: str | Path) -> pl.DataFrame:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return KrakenTickLoader().load(path)


def load_all_assets(asset_paths: dict[str, str | Path]) -> dict[str, pl.DataFrame]:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return KrakenTickLoader().load_all(asset_paths)

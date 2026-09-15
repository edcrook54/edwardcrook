"""
Cross-asset alignment layer.

Dollar bars preserve within-asset IID structure but are NOT simultaneous
across assets - a merge_asof + reduce() join across four independently-
bucketed dollar bar series produced very few matches, because bar
timestamps just don't line up closely enough across assets.

Chosen fix: build a fixed calendar grid (e.g. hourly) and backward-fill
each asset's dollar bars onto it (direction='backward'). This keeps the
within-asset dollar-bar benefit while giving a consistent, shared time
axis to run cointegration tests on. Don't revert to the merge_asof+reduce
approach across raw dollar bars - it was tried and doesn't scale past two
assets cleanly.
"""

from datetime import datetime

import polars as pl


class CalendarAligner:
    """Backward-fills per-asset dollar bars onto a shared fixed-frequency calendar grid."""

    def __init__(self, freq: str = "1h"):
        self.freq = freq

    def build_grid(self, start: datetime, end: datetime) -> pl.DataFrame:
        return pl.DataFrame(
            {"timestamp": pl.datetime_range(start, end, interval=self.freq, eager=True)}
        )

    def align(self, assets: dict[str, pl.DataFrame], grid: pl.DataFrame | None = None) -> pl.DataFrame:
        """Backward-fill each asset's dollar bars onto the shared calendar grid,
        then combine into one wide DataFrame keyed on grid timestamp
        (columns: timestamp, <ticker>_price, <ticker>_return per asset).
        """
        if grid is None:
            start = min(df["timestamp"].min() for df in assets.values())
            end = max(df["timestamp"].max() for df in assets.values())
            grid = self.build_grid(start, end)

        aligned = grid
        for ticker, df in assets.items():
            asset_bars = df.select(["timestamp", "close"]).sort("timestamp").rename({"close": f"{ticker}_price"})
            aligned = aligned.sort("timestamp").join_asof(
                asset_bars, on="timestamp", strategy="backward"
            )

        # Drop grid rows before every asset has had at least one bar.
        price_cols = [f"{ticker}_price" for ticker in assets]
        aligned = aligned.drop_nulls(subset=price_cols)

        for ticker in assets:
            aligned = aligned.with_columns(
                pl.col(f"{ticker}_price").log().diff().alias(f"{ticker}_return")
            )
        return aligned


def build_calendar_grid(start: datetime, end: datetime, freq: str = "1h") -> pl.DataFrame:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return CalendarAligner(freq).build_grid(start, end)


def align_assets_to_grid(assets: dict[str, pl.DataFrame], grid: pl.DataFrame) -> pl.DataFrame:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return CalendarAligner().align(assets, grid)

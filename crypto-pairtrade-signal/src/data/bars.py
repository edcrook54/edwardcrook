"""
Dollar bar construction.

Dollar bars sample by cumulative dollar volume rather than clock time,
which improves the IID properties of returns within a single asset -
this is the reason to use them at all over plain time bars. It also
mirrors how activity is actually sampled in production: execution
schedules (VWAP, percentage-of-volume) and desk risk refreshes are paced
by traded value, not the clock, because price impact and information
content scale with participation in the market's activity rather than
with elapsed time. Dollar bars specifically (not volume bars) matter for
assets whose price moves by an order of magnitude over the sample, since
a volume bar's dollar risk isn't comparable before and after a move like
that, while a dollar bar's is.

Known failure mode (hit during exploration, keep this fix in place):
assets have different history lengths - SOL from 2021, BCH/ADA/XRP from
2017. Bucketing each asset independently to the same target_bars count
over its own full history produces bars with very different calendar
spacing per asset, which breaks cross-asset alignment downstream. Trim
every asset to the common date window FIRST (SOL's 2021 start is the
binding constraint), then size the dollar thresholds.
"""

import polars as pl


class CommonWindowTrimmer:
    """Trims a dict of per-asset tick DataFrames down to their shared date range."""

    def fit_transform(self, assets: dict[str, pl.DataFrame]) -> dict[str, pl.DataFrame]:
        common_start = max(df["timestamp"].min() for df in assets.values())
        common_end = min(df["timestamp"].max() for df in assets.values())
        if common_start >= common_end:
            raise ValueError("No overlapping date window across assets.")
        return {
            ticker: df.filter(
                pl.col("timestamp").is_between(common_start, common_end)
            )
            for ticker, df in assets.items()
        }, common_start, common_end


class DollarBarBuilder:
    """Buckets tick data into dollar bars via cumulative dollar volume.

    threshold = total dollar volume / target_bars, then each bucket is
    every consecutive run of ticks whose cumulative dollar volume falls
    under one multiple of that threshold.
    """

    def __init__(self, target_bars: int):
        self.target_bars = target_bars

    def build(self, df: pl.DataFrame) -> pl.DataFrame:
        df = df.with_columns((pl.col("price") * pl.col("volume")).alias("dollar_volume"))
        total_dollar_volume = df["dollar_volume"].sum()
        threshold = total_dollar_volume / self.target_bars

        df = df.with_columns(
            (pl.col("dollar_volume").cum_sum() // threshold).cast(pl.Int64).alias("bucket")
        )
        bars = (
            df.group_by("bucket", maintain_order=True)
            .agg(
                [
                    pl.col("timestamp").last().alias("timestamp"),
                    pl.col("price").first().alias("open"),
                    pl.col("price").max().alias("high"),
                    pl.col("price").min().alias("low"),
                    pl.col("price").last().alias("close"),
                    pl.col("volume").sum().alias("volume"),
                    pl.col("dollar_volume").sum().alias("dollar_volume"),
                    pl.len().alias("n_ticks"),
                ]
            )
            .sort("timestamp")
            .drop("bucket")
        )
        return bars


def dollar_bars(df: pl.DataFrame, target_bars: int) -> pl.DataFrame:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return DollarBarBuilder(target_bars).build(df)


def trim_to_common_window(assets: dict[str, pl.DataFrame]) -> dict[str, pl.DataFrame]:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    trimmed, _, _ = CommonWindowTrimmer().fit_transform(assets)
    return trimmed

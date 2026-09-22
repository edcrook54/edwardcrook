"""An hourly grid of price facts, and fast "highest/lowest price in a window" queries.

Contracts are labelled by asking whether the price touched a level inside a window. With 1-minute
bars that means a range-maximum over up to 43,000 minutes (30 days), for hundreds of thousands
of contracts. The trick used here:

1. Collapse minutes into hours (max of the minute highs = the hour's high, and likewise the low),
   so a window is a run of whole hours and the label stays *exactly* what 1-minute monitoring
   would say.
2. Answer "max over hours i..j" in constant time with a **sparse table**: precompute the max over
   every block of 1, 2, 4, 8, ... hours; any window is then covered by two overlapping blocks.

Hours with no trades carry no high/low (they cannot touch anything) and a forward-filled close
(the last known price), which is what a trader looking at the screen would see.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import cast

import numpy as np
import polars as pl
from numpy.typing import NDArray

FloatArray = NDArray[np.float64]
HOURS_PER_YEAR = 365.0 * 24.0


@dataclass(frozen=True)
class HourlyGrid:
    """Dense hourly arrays. Index ``i`` is the hour ``[t0 + i h, t0 + (i + 1) h)``."""

    t0: np.datetime64
    high: FloatArray  # -inf where the hour had no trades
    low: FloatArray  # +inf where the hour had no trades
    close: FloatArray  # last known price (forward-filled)
    rv: FloatArray  # realised variance from 5-minute returns inside the hour
    traded: NDArray[np.bool_]  # did any trade happen this hour?

    def __len__(self) -> int:
        return int(self.close.size)

    def timestamp(self, i: int | NDArray[np.int64]) -> NDArray[np.datetime64]:
        return np.asarray(self.t0 + np.asarray(i) * np.timedelta64(1, "h"))


def build_hourly_grid(
    bars: pl.DataFrame, start: str | None = None, end: str | None = None
) -> HourlyGrid:
    """Turn 1-minute OHLC bars into the dense hourly grid used by the backtest."""
    b = bars.sort("ts")
    if start:
        b = b.filter(pl.col("ts") >= pl.lit(start).str.to_datetime(time_zone="UTC"))
    if end:
        b = b.filter(pl.col("ts") < pl.lit(end).str.to_datetime(time_zone="UTC"))
    first = cast(datetime, b["ts"].min()).replace(minute=0, second=0, microsecond=0)
    last = cast(datetime, b["ts"].max())

    # 5-minute closes on a complete grid, forward-filled, for realised variance.
    five = (
        b.group_by_dynamic("ts", every="5m", closed="left", label="left")
        .agg(pl.col("close").last())
        .upsample("ts", every="5m")
        .with_columns(pl.col("close").forward_fill())
        .with_columns((pl.col("close") / pl.col("close").shift(1)).log().alias("r5"))
        .with_columns(pl.col("r5").fill_null(0.0))
    )
    rv_hour = five.group_by_dynamic("ts", every="1h", closed="left", label="left").agg(
        (pl.col("r5") ** 2).sum().alias("rv")
    )
    hourly = b.group_by_dynamic("ts", every="1h", closed="left", label="left").agg(
        pl.col("high").max(), pl.col("low").min(), pl.col("close").last(), pl.len().alias("n")
    )
    full = pl.DataFrame(
        {"ts": pl.datetime_range(first, last, interval="1h", time_zone="UTC", eager=True)}
    )
    grid = (
        full.join(hourly, on="ts", how="left")
        .join(rv_hour, on="ts", how="left")
        .with_columns(
            pl.col("close").forward_fill(),
            pl.col("n").fill_null(0),
            pl.col("rv").fill_null(0.0),
        )
    )
    traded = (grid["n"] > 0).to_numpy()
    high = grid["high"].fill_null(float("-inf")).to_numpy().astype(float)
    low = grid["low"].fill_null(float("inf")).to_numpy().astype(float)
    return HourlyGrid(
        t0=np.datetime64(first.replace(tzinfo=None), "h"),
        high=high,
        low=low,
        close=grid["close"].to_numpy().astype(float),
        rv=grid["rv"].to_numpy().astype(float),
        traded=traded,
    )


class SparseTable:
    """Constant-time range max (or min) over a fixed array."""

    def __init__(self, values: FloatArray, use_max: bool = True) -> None:
        self._op = np.maximum if use_max else np.minimum
        levels = [np.asarray(values, dtype=float)]
        j = 1
        while (1 << j) <= values.size:
            prev = levels[-1]
            half = 1 << (j - 1)
            levels.append(self._op(prev[:-half], prev[half:]))
            j += 1
        self._levels = levels

    def query(self, start: NDArray[np.int64], length: NDArray[np.int64]) -> FloatArray:
        """Extreme over ``values[start : start + length]`` for arrays of windows."""
        start = np.asarray(start, dtype=np.int64)
        length = np.asarray(length, dtype=np.int64)
        k = np.floor(np.log2(length)).astype(np.int64)
        out = np.empty(start.shape, dtype=float)
        for level in np.unique(k):
            m = k == level
            block = self._levels[int(level)]
            a = block[start[m]]
            b = block[start[m] + length[m] - (1 << int(level))]
            out[m] = self._op(a, b)
        return out


class WindowExtremes:
    """Highest high and lowest low inside a window of whole hours."""

    def __init__(self, grid: HourlyGrid) -> None:
        self._max = SparseTable(grid.high, use_max=True)
        self._min = SparseTable(grid.low, use_max=False)

    def highest(self, start: NDArray[np.int64], hours: int | NDArray[np.int64]) -> FloatArray:
        n = np.broadcast_to(np.asarray(hours, dtype=np.int64), np.shape(start))
        return self._max.query(start, n)

    def lowest(self, start: NDArray[np.int64], hours: int | NDArray[np.int64]) -> FloatArray:
        n = np.broadcast_to(np.asarray(hours, dtype=np.int64), np.shape(start))
        return self._min.query(start, n)

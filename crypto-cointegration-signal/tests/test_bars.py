"""
Tests for dollar_bars() and trim_to_common_window(), using small synthetic
tick series rather than the real Kraken CSVs (which are gigabytes and not
suitable for a fast unit test).
"""

from datetime import datetime, timedelta

import polars as pl

from src.data.bars import DollarBarBuilder, CommonWindowTrimmer


def _synthetic_ticks(start: datetime, n: int, price: float = 100.0, step: timedelta = timedelta(minutes=1)) -> pl.DataFrame:
    timestamps = [start + step * i for i in range(n)]
    return pl.DataFrame(
        {
            "timestamp": timestamps,
            "price": [price + (i % 5) for i in range(n)],
            "volume": [1.0 + (i % 3) for i in range(n)],
        }
    )


def test_dollar_bars_produces_roughly_target_bars():
    ticks = _synthetic_ticks(datetime(2024, 1, 1), n=5000)
    target_bars = 100
    bars = DollarBarBuilder(target_bars).build(ticks)

    # Bucketing by cumulative dollar volume is approximate at the edges
    # (partial final bucket), so allow some slack either side of the target.
    assert abs(bars.height - target_bars) <= 2
    assert bars["timestamp"].is_sorted()
    assert set(["open", "high", "low", "close", "volume", "dollar_volume"]).issubset(bars.columns)


def test_dollar_bars_ohlc_consistency():
    ticks = _synthetic_ticks(datetime(2024, 1, 1), n=2000)
    bars = DollarBarBuilder(50).build(ticks)

    assert (bars["high"] >= bars["low"]).all()
    assert (bars["high"] >= bars["open"]).all()
    assert (bars["high"] >= bars["close"]).all()
    assert (bars["low"] <= bars["open"]).all()
    assert (bars["low"] <= bars["close"]).all()


def test_trim_to_common_window_aligns_start_and_end():
    # SOL-like asset: starts later (2024), one tick per day.
    sol = _synthetic_ticks(datetime(2024, 1, 1), n=200, step=timedelta(days=1))
    # BCH-like asset: starts earlier (2023) but runs long enough to overlap SOL's window.
    bch = _synthetic_ticks(datetime(2023, 1, 1), n=500, step=timedelta(days=1))

    trimmed, common_start, common_end = CommonWindowTrimmer().fit_transform(
        {"SOL": sol, "BCH": bch}
    )

    for df in trimmed.values():
        assert df["timestamp"].min() >= common_start
        assert df["timestamp"].max() <= common_end

    # The later-starting asset (SOL) should bind the common start.
    assert common_start == sol["timestamp"].min()

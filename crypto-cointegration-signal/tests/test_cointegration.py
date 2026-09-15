from datetime import datetime, timedelta

import numpy as np
import polars as pl

from src.signals.cointegration import RandomWindowSampler, EngleGrangerTester, CointegrationScanner


def test_random_window_sampler_returns_valid_windows():
    sampler = RandomWindowSampler(window_length=100, n_windows=20, seed=42)
    windows = sampler.sample(n_obs=1000)

    assert len(windows) == 20
    for start, end in windows:
        assert end - start == 100
        assert 0 <= start < end <= 1000


def test_random_window_sampler_is_reproducible_with_seed():
    a = RandomWindowSampler(100, 20, seed=1).sample(1000)
    b = RandomWindowSampler(100, 20, seed=1).sample(1000)
    assert a == b


def test_engle_granger_detects_cointegrated_series():
    rng = np.random.default_rng(0)
    n = 500
    common = np.cumsum(rng.normal(size=n))
    series_a = common + rng.normal(scale=0.1, size=n)
    series_b = common + rng.normal(scale=0.1, size=n)

    result = EngleGrangerTester().test(series_a, series_b)
    assert result["pvalue"] < 0.05


def test_engle_granger_rejects_independent_random_walks():
    rng = np.random.default_rng(1)
    n = 500
    series_a = np.cumsum(rng.normal(size=n))
    series_b = np.cumsum(rng.normal(size=n))

    result = EngleGrangerTester().test(series_a, series_b)
    assert result["pvalue"] > 0.05


def test_scan_pairs_uses_distinct_windows_per_pair():
    # Regression test: scan_pair used to build its RandomWindowSampler from
    # the scanner's single base seed every time, so every pair sampled the
    # exact same calendar windows - collapsing what should be independent
    # per-pair evidence into one shared set of windows re-tested 6 times.
    rng = np.random.default_rng(4)
    n = 2000
    timestamps = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(n)]
    common = np.cumsum(rng.normal(size=n)) + 100
    aligned = pl.DataFrame(
        {
            "timestamp": timestamps,
            "A_price": common + rng.normal(scale=0.1, size=n),
            "B_price": common + rng.normal(scale=0.1, size=n),
            "C_price": common + rng.normal(scale=0.1, size=n),
        }
    )
    scanner = CointegrationScanner(n_windows=10, window_length_days=1, bars_per_day=50, seed=42)
    result = scanner.scan_pairs(aligned, pairs=[("A", "B"), ("A", "C")])

    starts_ab = set(result.filter(pl.col("pair") == "A-B")["window_start"].to_list())
    starts_ac = set(result.filter(pl.col("pair") == "A-C")["window_start"].to_list())
    assert starts_ab != starts_ac


def test_scan_pairs_returns_expected_columns():
    rng = np.random.default_rng(2)
    n = 300
    timestamps = [datetime(2024, 1, 1) + timedelta(hours=i) for i in range(n)]
    common = np.cumsum(rng.normal(size=n)) + 100
    aligned = pl.DataFrame(
        {
            "timestamp": timestamps,
            "A_price": common + rng.normal(scale=0.1, size=n),
            "B_price": common + rng.normal(scale=0.1, size=n),
        }
    )
    scanner = CointegrationScanner(n_windows=5, window_length_days=1, bars_per_day=50, seed=3)
    result = scanner.scan_pairs(aligned, pairs=[("A", "B")])

    assert result.height == 5
    assert set(["pair", "window_start", "window_end", "stat", "pvalue"]).issubset(result.columns)

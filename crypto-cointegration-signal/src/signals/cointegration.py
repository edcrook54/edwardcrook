"""
Engle-Granger cointegration scanning across asset pairs.

Design choice: test cointegration on many RANDOM rolling windows across
history per pair, not one fixed window. A single window can look
cointegrated by chance; reporting the distribution of test statistics /
p-values across windows is the honest version of this analysis and is
what should drive the plots.
"""

import numpy as np
import polars as pl
from statsmodels.tsa.stattools import coint


class RandomWindowSampler:
    """Samples random (start_idx, end_idx) windows of a fixed length over a series length."""

    def __init__(self, window_length: int, n_windows: int, seed: int | None = None):
        self.window_length = window_length
        self.n_windows = n_windows
        self.seed = seed

    def sample(self, n_obs: int) -> list[tuple[int, int]]:
        if self.window_length >= n_obs:
            raise ValueError(
                f"window_length ({self.window_length}) must be < n_obs ({n_obs})"
            )
        rng = np.random.default_rng(self.seed)
        max_start = n_obs - self.window_length
        n_windows = min(self.n_windows, max_start + 1)
        starts = rng.choice(max_start + 1, size=n_windows, replace=False)
        return [(int(s), int(s + self.window_length)) for s in sorted(starts)]


class EngleGrangerTester:
    """Wraps statsmodels' Engle-Granger cointegration test for a single pair/window."""

    def test(self, series_a: np.ndarray, series_b: np.ndarray) -> dict:
        stat, pvalue, crit_values = coint(series_a, series_b)
        return {"stat": float(stat), "pvalue": float(pvalue), "crit_values": crit_values.tolist()}


class CointegrationScanner:
    """Runs the Engle-Granger test across all pairs over many random rolling windows,
    producing a long-format result table that the rolling-cointegration plots are built from.

    Each pair gets its own derived seed (base seed + pair index) rather than
    reusing one seed across every pair. Reusing a single seed makes every
    pair sample the exact same calendar windows - not a cosmetic issue: it
    collapses what looks like 6 x n_windows independent tests down to just
    n_windows distinct calendar periods, so a shared market-wide regime in
    one window shows up as "significant" for several pairs simultaneously,
    contaminating the cross-pair stability comparison this scan exists to
    produce. Per-pair seeds are still fully deterministic given the base
    seed, so results stay reproducible.
    """

    def __init__(
        self,
        n_windows: int = 50,
        window_length_days: int = 30,
        bars_per_day: float = 24.0,
        seed: int | None = None,
    ):
        self.n_windows = n_windows
        self.window_length = max(int(round(window_length_days * bars_per_day)), 2)
        self.seed = seed
        self.tester = EngleGrangerTester()

    def scan_pair(
        self, aligned: pl.DataFrame, asset_a: str, asset_b: str, seed: int | None = None
    ) -> pl.DataFrame:
        price_a = aligned[f"{asset_a}_price"].to_numpy()
        price_b = aligned[f"{asset_b}_price"].to_numpy()
        timestamps = aligned["timestamp"].to_list()

        effective_seed = self.seed if seed is None else seed
        sampler = RandomWindowSampler(self.window_length, self.n_windows, seed=effective_seed)
        windows = sampler.sample(len(price_a))

        rows = []
        for start, end in windows:
            result = self.tester.test(price_a[start:end], price_b[start:end])
            rows.append(
                {
                    "pair": f"{asset_a}-{asset_b}",
                    "asset_a": asset_a,
                    "asset_b": asset_b,
                    "window_start": timestamps[start],
                    "window_end": timestamps[end - 1],
                    "stat": result["stat"],
                    "pvalue": result["pvalue"],
                }
            )
        return pl.DataFrame(rows)

    def scan_pairs(self, aligned: pl.DataFrame, pairs: list[tuple[str, str]]) -> pl.DataFrame:
        frames = [
            self.scan_pair(aligned, a, b, seed=None if self.seed is None else self.seed + i)
            for i, (a, b) in enumerate(pairs)
        ]
        return pl.concat(frames)


def sample_random_windows(
    n_obs: int, window_length: int, n_windows: int, seed: int | None = None
) -> list[tuple[int, int]]:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return RandomWindowSampler(window_length, n_windows, seed).sample(n_obs)


def engle_granger_pair(series_a, series_b) -> dict:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return EngleGrangerTester().test(np.asarray(series_a), np.asarray(series_b))


def scan_pairs(
    aligned: pl.DataFrame,
    pairs: list[tuple[str, str]],
    n_windows: int,
    window_length: int,
    seed: int | None = None,
) -> pl.DataFrame:
    """Functional convenience wrapper kept for notebook/script ergonomics.
    Note: window_length here is expressed directly in bars (rows of `aligned`),
    unlike CointegrationScanner which takes window_length_days + bars_per_day.
    """
    scanner = CointegrationScanner(n_windows=n_windows, window_length_days=1, bars_per_day=window_length, seed=seed)
    return scanner.scan_pairs(aligned, pairs)

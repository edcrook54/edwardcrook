"""The most important test in the backtest: the future must not leak into a forecast."""

import numpy as np

from pmq.crypto import features
from pmq.crypto.grid import HourlyGrid


def _grid(seed: int, n: int = 3000) -> HourlyGrid:
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(0.004 * rng.standard_normal(n)))
    return HourlyGrid(
        t0=np.datetime64("2020-01-01T00", "h"),
        high=close * 1.001,
        low=close * 0.999,
        close=close,
        rv=(0.004**2) * rng.chisquare(1, n),
        traded=np.ones(n, dtype=bool),
    )


def test_features_at_an_anchor_do_not_change_when_the_future_is_rewritten() -> None:
    g = _grid(0)
    cut = 2000
    shock = np.random.default_rng(9).standard_normal(g.close.size - cut)
    rewritten_close = g.close.copy()
    rewritten_close[cut:] *= np.exp(np.cumsum(0.3 * shock))
    g2 = HourlyGrid(
        t0=g.t0,
        high=g.high,
        low=g.low,
        close=rewritten_close,
        rv=np.concatenate([g.rv[:cut], 50 * g.rv[cut:]]),
        traded=g.traded,
    )
    f1, f2 = features.build_features(g), features.build_features(g2)
    names = ("trailing30_vol", "rv1d_var", "rv7d_var", "rv30d_var", "ewma_vol", "bayes_beta")
    for name in names:
        a, b = getattr(f1, name), getattr(f2, name)
        # An anchor at hour `cut` may use hours < cut only, so everything up to it is identical.
        np.testing.assert_allclose(a[: cut + 1], b[: cut + 1], err_msg=name)
        # Sanity check on the test itself: later values really do respond to the rewrite.
        assert not np.allclose(a[cut + 200 :], b[cut + 200 :], equal_nan=True), name


def test_universe_labels_match_a_brute_force_scan_of_the_raw_hours() -> None:
    from pmq.crypto import backtest

    rng = np.random.default_rng(1)
    n = 24 * 90
    close = 100 * np.exp(np.cumsum(0.004 * rng.standard_normal(n)))
    g = HourlyGrid(
        t0=np.datetime64("2020-01-01T00", "h"),
        high=close * (1 + 0.003 * rng.random(n)),
        low=close * (1 - 0.003 * rng.random(n)),
        close=close,
        rv=(0.004**2) * rng.chisquare(1, n),
        traded=np.ones(n, dtype=bool),
    )
    cfg = backtest.BacktestConfig(horizons_days=(1, 7), z_grid=(0.5, 1.5), anchor_step_hours=5)
    u = backtest.build_universe(g, features.build_features(g), cfg)
    assert u["label"].size > 100
    for i in range(0, u["label"].size, 7):
        a, hours = int(u["anchor"][i]), int(24 * u["horizon_d"][i])
        window_hi = g.high[a : a + hours].max()
        window_lo = g.low[a : a + hours].min()
        expected = window_hi >= u["k"][i] if u["direction"][i] > 0 else window_lo <= u["k"][i]
        assert bool(u["label"][i]) == bool(expected)
        assert u["s0"][i] == g.close[a - 1]  # priced off the last close *before* the anchor

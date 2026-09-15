import numpy as np

from src.backtest.costs import CostModel
from src.backtest.engine import BacktestEngine, WalkForwardSplitter, ZScoreSignalGenerator


def test_zscore_signal_enters_and_exits_on_thresholds():
    spread = np.concatenate(
        [np.zeros(20), np.full(10, 5.0), np.zeros(20)]  # flat, spike, revert
    )
    gen = ZScoreSignalGenerator(lookback=10, entry_z=2.0, exit_z=0.5)
    positions = gen.positions(spread)

    assert len(positions) == len(spread)
    # During the spike the spread is far above its trailing mean -> short spread.
    assert positions[25] == -1.0
    # After reverting back to the trailing mean, position should return to flat.
    assert positions[-1] == 0.0


def test_zscore_signal_does_not_blow_up_on_near_constant_window():
    # Simulates backward-fill duplication: most of the series is a normal
    # random walk, but one stretch is (almost) perfectly flat - as happens
    # when many hourly grid rows backward-fill the same dollar bar. A naive
    # rolling-std z-score divides by that near-zero local sigma and produces
    # huge spurious z-scores right as the flat run ends.
    rng = np.random.default_rng(0)
    spread = np.cumsum(rng.normal(size=200)) + 100
    spread[80:95] = spread[80]  # flat run (duplicated bars)
    spread[94] += 1e-9  # tiny float-level wobble within the flat run

    gen = ZScoreSignalGenerator(lookback=10, entry_z=2.0, exit_z=0.5)
    z = gen.zscore(spread)
    assert np.all(np.abs(z[~np.isnan(z)]) < 100)


def test_zscore_is_causal_prefix_matches_full_series():
    # Regression test: the degenerate-window floor used to be computed once
    # from np.nanstd() over the *entire* input array, so appending future
    # (e.g. out-of-sample) data to the array could change z-scores computed
    # for earlier, in-sample timestamps - a look-ahead leak. The floor must
    # only ever depend on data strictly before the current index.
    rng = np.random.default_rng(2)
    full = np.cumsum(rng.normal(size=300)) + 100
    # Splice in a very different volatility regime for the back half, which
    # would change a whole-array std computed over the full series.
    full[150:] = full[150] + np.cumsum(rng.normal(scale=20, size=150))

    gen = ZScoreSignalGenerator(lookback=10, entry_z=2.0, exit_z=0.5)
    z_prefix_alone = gen.zscore(full[:120])
    z_full = gen.zscore(full)

    assert np.allclose(z_prefix_alone, z_full[:120], equal_nan=True)


def test_walk_forward_split_is_chronological_and_non_overlapping():
    train, test = WalkForwardSplitter(oos_fraction=0.3).split(100)
    assert train.stop == test.start
    assert test.stop == 100
    assert train.start == 0


def test_backtest_engine_produces_expected_shapes():
    n = 50
    rng = np.random.default_rng(0)
    positions = np.sign(rng.normal(size=n))
    price_a = 100 + np.cumsum(rng.normal(scale=0.5, size=n))
    price_b = 50 + np.cumsum(rng.normal(scale=0.3, size=n))
    hedge_ratio = np.full(n, 1.0)

    engine = BacktestEngine(CostModel(cost_bps=5))
    result = engine.run(positions, price_a, price_b, hedge_ratio)

    assert len(result["net_returns"]) == n
    assert len(result["equity_curve"]) == n
    assert np.isclose(
        result["equity_curve"][-1], np.prod(1 + result["net_returns"]) - 1
    )


def test_backtest_engine_flat_position_has_zero_return():
    n = 20
    rng = np.random.default_rng(1)
    positions = np.zeros(n)
    price_a = 100 + np.cumsum(rng.normal(scale=0.5, size=n))
    price_b = 50 + np.cumsum(rng.normal(scale=0.3, size=n))
    hedge_ratio = np.full(n, 1.0)

    engine = BacktestEngine(CostModel(cost_bps=5))
    result = engine.run(positions, price_a, price_b, hedge_ratio)

    assert np.allclose(result["net_returns"], 0.0)
    assert np.allclose(result["equity_curve"], 0.0)

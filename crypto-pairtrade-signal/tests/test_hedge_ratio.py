import numpy as np

from src.signals.hedge_ratio import KalmanHedgeRatioEstimator, spread_from_hedge_ratio


def test_kalman_hedge_ratio_recovers_known_static_ratio():
    rng = np.random.default_rng(0)
    n = 500
    series_b = np.cumsum(rng.normal(size=n)) + 100
    true_ratio = 1.5
    series_a = true_ratio * series_b + rng.normal(scale=0.05, size=n)

    estimator = KalmanHedgeRatioEstimator(delta=1e-5)
    ratios = estimator.hedge_ratio_only(series_a, series_b)

    assert len(ratios) == n
    # After the filter has burned in, the estimate should be close to the true ratio.
    assert abs(np.mean(ratios[-100:]) - true_ratio) < 0.1


def test_spread_from_hedge_ratio_is_near_zero_for_cointegrated_pair():
    rng = np.random.default_rng(1)
    n = 300
    series_b = np.cumsum(rng.normal(size=n)) + 50
    series_a = 2.0 * series_b + rng.normal(scale=0.05, size=n)

    ratios = KalmanHedgeRatioEstimator(delta=1e-5).hedge_ratio_only(series_a, series_b)
    spread = spread_from_hedge_ratio(series_a, series_b, ratios)

    assert np.std(spread[-100:]) < np.std(series_a[-100:])

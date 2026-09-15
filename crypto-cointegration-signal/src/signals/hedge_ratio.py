"""
Kalman filter hedge ratio estimation for cointegrated pairs.

A static OLS hedge ratio goes stale, and the random-window cointegration
scan is expected to show that pair relationships aren't constant over
time anyway - so the hedge ratio should adapt too, via a Kalman filter,
rather than being fit once on the full history.
"""

import numpy as np
from pykalman import KalmanFilter
from sklearn.linear_model import LinearRegression


class KalmanHedgeRatioEstimator:
    """Time-varying hedge ratio via a Kalman filter, in the standard pairs-trading
    formulation: state = [hedge_ratio, intercept], observation = series_a,
    observation matrix = [series_b, 1].

    The state transition covariance (delta) controls how fast the hedge ratio is
    allowed to drift - small delta means a near-static ratio, larger delta tracks
    regime changes faster at the cost of noisier estimates.
    """

    def __init__(self, delta: float = 1e-4, observation_covariance: float = 1e-3):
        self.delta = delta
        self.observation_covariance = observation_covariance

    def _initial_state(self, series_a: np.ndarray, series_b: np.ndarray) -> np.ndarray:
        reg = LinearRegression().fit(series_b.reshape(-1, 1), series_a)
        return np.array([reg.coef_[0], reg.intercept_])

    def estimate(self, series_a: np.ndarray, series_b: np.ndarray, fit_length: int | None = None) -> np.ndarray:
        """Returns an array of shape (n, 2): column 0 is the hedge ratio, column 1
        is the intercept, one row per timestep, same length as the inputs.

        `fit_length`, if given, restricts the static OLS regression used to seed
        the filter's initial state to the first `fit_length` observations (e.g.
        the train window) - the filter itself still runs causally over the full
        series either way, but this keeps the seed itself walk-forward-honest
        when `estimate` is called on a train+test series for OOS evaluation.
        """
        n = len(series_a)
        obs_matrix = np.stack([series_b, np.ones(n)], axis=1)[:, np.newaxis, :]

        trans_cov = self.delta / (1 - self.delta) * np.eye(2)
        fit_n = fit_length or n
        initial_state = self._initial_state(series_a[:fit_n], series_b[:fit_n])

        kf = KalmanFilter(
            n_dim_obs=1,
            n_dim_state=2,
            initial_state_mean=initial_state,
            initial_state_covariance=np.ones((2, 2)),
            transition_matrices=np.eye(2),
            observation_matrices=obs_matrix,
            observation_covariance=self.observation_covariance,
            transition_covariance=trans_cov,
        )
        state_means, _ = kf.filter(series_a)
        return state_means

    def hedge_ratio_only(self, series_a: np.ndarray, series_b: np.ndarray, fit_length: int | None = None) -> np.ndarray:
        return self.estimate(series_a, series_b, fit_length=fit_length)[:, 0]


def kalman_hedge_ratio(series_a: np.ndarray, series_b: np.ndarray) -> np.ndarray:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return KalmanHedgeRatioEstimator().hedge_ratio_only(series_a, series_b)


def spread_from_hedge_ratio(
    series_a: np.ndarray, series_b: np.ndarray, hedge_ratio: np.ndarray
) -> np.ndarray:
    return series_a - hedge_ratio * series_b

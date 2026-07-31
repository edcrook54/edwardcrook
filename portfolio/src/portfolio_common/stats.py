"""Shared statistical helpers used across portfolio projects.

Keeping these in one place means the Newey-West t-stats you report for the
options BMA-SDF project use the exact same implementation as any factor
work in other projects — one tested function instead of five copy-pastes.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import statsmodels.api as sm


def newey_west_tstat(returns: pd.Series, lags: int = 4) -> float:
    """t-stat of the mean of `returns`, HAC-adjusted (Newey-West, given lag length).

    Matches the convention used in the option-factor literature
    (e.g. lag length 4 for monthly factor returns).
    """
    x = np.asarray(returns.dropna())
    model = sm.OLS(x, np.ones_like(x))
    fit = model.fit(cov_type="HAC", cov_kwds={"maxlags": lags})
    return float(fit.tvalues[0])


def annualized_sharpe(returns: pd.Series, periods_per_year: int = 12) -> float:
    """Annualized Sharpe ratio for a return series (no risk-free adjustment)."""
    mu = returns.mean()
    sigma = returns.std(ddof=1)
    if sigma == 0:
        return float("nan")
    return float(mu / sigma * np.sqrt(periods_per_year))


def deflated_sharpe_ratio(
    sharpe: float,
    n_obs: int,
    n_trials: int,
    skew: float = 0.0,
    kurtosis: float = 3.0,
) -> float:
    """Probability the observed Sharpe ratio is genuine, adjusting for multiple
    testing (Bailey & Lopez de Prado, 2014). Useful when reporting the "best"
    factor out of many candidates, to avoid overclaiming significance.
    """
    from scipy.stats import norm

    # expected max Sharpe ratio under the null, across n_trials independent trials
    euler_mascheroni = 0.5772156649
    expected_max_sr = (1 - euler_mascheroni) * norm.ppf(1 - 1 / n_trials) + euler_mascheroni * norm.ppf(
        1 - 1 / (n_trials * np.e)
    )
    sr_std = np.sqrt((1 - skew * sharpe + (kurtosis - 1) / 4 * sharpe**2) / (n_obs - 1))
    if sr_std == 0:
        return float("nan")
    return float(norm.cdf((sharpe - expected_max_sr) / sr_std))


def pricing_error_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, float]:
    """RMSE, MAPE, and R^2 for cross-sectional asset pricing tests
    (same metrics used in the BMA-SDF paper's Table 2).
    """
    actual = np.asarray(actual)
    predicted = np.asarray(predicted)
    errors = actual - predicted
    rmse = float(np.sqrt(np.mean(errors**2)))
    mape = float(np.mean(np.abs(errors) / np.abs(actual)))
    ss_res = np.sum(errors**2)
    ss_tot = np.sum((actual - actual.mean()) ** 2)
    r2 = float(1 - ss_res / ss_tot) if ss_tot != 0 else float("nan")
    return {"rmse": rmse, "mape": mape, "r2": r2}

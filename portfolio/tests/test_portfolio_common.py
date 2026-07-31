import numpy as np
import pandas as pd

from portfolio_common.stats import annualized_sharpe, pricing_error_metrics


def test_annualized_sharpe_positive_returns() -> None:
    returns = pd.Series([0.01, 0.02, 0.015, 0.005, 0.01])
    sharpe = annualized_sharpe(returns)
    assert sharpe > 0


def test_pricing_error_metrics_perfect_fit() -> None:
    actual = np.array([1.0, 2.0, 3.0])
    predicted = np.array([1.0, 2.0, 3.0])
    metrics = pricing_error_metrics(actual, predicted)
    assert metrics["rmse"] == 0
    assert metrics["r2"] == 1

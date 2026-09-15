import numpy as np

from src.evaluation.metrics import PerformanceEvaluator


def test_sharpe_ratio_zero_for_zero_variance():
    evaluator = PerformanceEvaluator(periods_per_year=252)
    assert evaluator.sharpe_ratio(np.zeros(10)) == 0.0


def test_sharpe_ratio_positive_for_positive_drift():
    evaluator = PerformanceEvaluator(periods_per_year=252)
    returns = np.full(100, 0.001)
    assert evaluator.sharpe_ratio(returns) > 0


def test_max_drawdown_on_known_curve():
    evaluator = PerformanceEvaluator(periods_per_year=252)
    equity = np.array([0, 1, 2, 1, 0, 2, 3])
    # Peak of 2 at idx 2, trough of 0 at idx 4 -> drawdown of -2.
    assert evaluator.max_drawdown(equity) == -2.0


def test_hit_rate_ignores_zero_return_periods():
    evaluator = PerformanceEvaluator(periods_per_year=252)
    returns = np.array([0.01, -0.01, 0.0, 0.02, 0.0])
    assert evaluator.hit_rate(returns) == 2 / 3


def test_sharpe_standard_error_shrinks_with_more_periods():
    evaluator = PerformanceEvaluator(periods_per_year=252)
    rng = np.random.default_rng(0)
    short = rng.normal(0.001, 0.01, size=50)
    long = rng.normal(0.001, 0.01, size=5000)
    assert evaluator.sharpe_standard_error(long) < evaluator.sharpe_standard_error(short)


def test_summary_includes_sharpe_se():
    evaluator = PerformanceEvaluator(periods_per_year=252)
    returns = np.full(100, 0.001)
    summary = evaluator.summary(returns, np.cumsum(returns))
    assert "sharpe_se" in summary
    assert summary["sharpe_se"] > 0

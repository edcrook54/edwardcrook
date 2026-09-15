"""
Performance and diagnostic metrics for the backtest and out-of-sample test.

Report these as distributions/percentiles where possible (e.g. across the
random cointegration windows or across pairs), not single cherry-picked
headline numbers.
"""

import numpy as np


class PerformanceEvaluator:
    """Computes standard cost-adjusted performance metrics from a return series
    / equity curve produced by BacktestEngine.
    """

    def __init__(self, periods_per_year: int):
        self.periods_per_year = periods_per_year

    def sharpe_ratio(self, returns: np.ndarray) -> float:
        returns = np.asarray(returns, dtype=float)
        if returns.std() == 0:
            return 0.0
        return float(np.mean(returns) / np.std(returns) * np.sqrt(self.periods_per_year))

    def sharpe_standard_error(self, returns: np.ndarray) -> float:
        """Asymptotic standard error of the annualised Sharpe ratio, via the
        standard `sqrt((1 + 0.5*SR_period^2) / N)` formula (Lo, 2002) on the
        per-period Sharpe, then annualised - a minimum-bar uncertainty
        estimate, not a rigorous one. It assumes IID returns, which returns
        from a strategy that holds positions across multiple consecutive
        bars do not satisfy (those returns are serially correlated), so this
        should be read as an optimistic lower bound on the true uncertainty,
        not a tight confidence interval.
        """
        returns = np.asarray(returns, dtype=float)
        n = len(returns)
        if n < 2 or returns.std() == 0:
            return float("nan")
        sr_period = np.mean(returns) / np.std(returns)
        se_period = np.sqrt((1 + 0.5 * sr_period**2) / n)
        return float(se_period * np.sqrt(self.periods_per_year))

    def max_drawdown(self, equity_curve: np.ndarray) -> float:
        equity_curve = np.asarray(equity_curve, dtype=float)
        running_max = np.maximum.accumulate(equity_curve)
        drawdown = equity_curve - running_max
        return float(drawdown.min())

    def hit_rate(self, returns: np.ndarray) -> float:
        returns = np.asarray(returns, dtype=float)
        active = returns[returns != 0]
        if len(active) == 0:
            return 0.0
        return float(np.mean(active > 0))

    def summary(self, returns: np.ndarray, equity_curve: np.ndarray) -> dict:
        return {
            "sharpe": self.sharpe_ratio(returns),
            "sharpe_se": self.sharpe_standard_error(returns),
            "max_drawdown": self.max_drawdown(equity_curve),
            "hit_rate": self.hit_rate(returns),
            "total_return": float(equity_curve[-1]) if len(equity_curve) else 0.0,
            "n_periods": len(returns),
        }


def sharpe_ratio(returns: np.ndarray, periods_per_year: int) -> float:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return PerformanceEvaluator(periods_per_year).sharpe_ratio(returns)


def max_drawdown(equity_curve: np.ndarray) -> float:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return PerformanceEvaluator(periods_per_year=1).max_drawdown(equity_curve)


def hit_rate(returns: np.ndarray) -> float:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return PerformanceEvaluator(periods_per_year=1).hit_rate(returns)

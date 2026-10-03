import numpy as np
import pytest

from llmsignal.evaluation import max_drawdown, sharpe_ratio


def test_sharpe_ratio_matches_hand_worked_example() -> None:
    returns = np.array([0.01, -0.01, 0.01, -0.01])
    # mean=0, std>0 -> sharpe should be 0 regardless of periods_per_year
    assert sharpe_ratio(returns, periods_per_year=252) == pytest.approx(0.0)


def test_sharpe_ratio_is_zero_for_constant_returns() -> None:
    assert sharpe_ratio(np.array([0.02, 0.02, 0.02]), periods_per_year=12) == 0.0


def test_sharpe_ratio_is_zero_for_empty_returns() -> None:
    assert sharpe_ratio(np.array([]), periods_per_year=12) == 0.0


def test_max_drawdown_matches_hand_worked_example() -> None:
    # equity rises to 0.10, falls to -0.05 relative to that peak -> drawdown -0.15
    equity_curve = np.array([0.0, 0.05, 0.10, 0.02, -0.05])

    assert max_drawdown(equity_curve) == pytest.approx(-0.15)


def test_max_drawdown_is_zero_for_a_monotonically_rising_curve() -> None:
    assert max_drawdown(np.array([0.0, 0.01, 0.02, 0.03])) == pytest.approx(0.0)

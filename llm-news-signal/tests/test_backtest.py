import numpy as np
import pytest

from llmsignal.backtest import WalkForwardSplitter, positions_from_scores, run_backtest


def test_positions_from_scores_thresholds_correctly() -> None:
    scores = np.array([2.0, 0.5, -0.5, -2.0, 1.0])

    positions = positions_from_scores(scores, threshold=1.0)

    assert positions.tolist() == [1.0, 0.0, 0.0, -1.0, 1.0]


def test_run_backtest_matches_hand_worked_single_trade() -> None:
    # One long position (score above threshold), one flat period (no bet).
    # gross = [1*0.02, 0*0.01] = [0.02, 0.0]
    # round-trip cost at cost_bps=100 -> 2*(100/1e4) = 0.02, charged only
    # where a position was actually taken.
    # net = [0.02-0.02, 0.0-0.0] = [0.0, 0.0]
    scores = np.array([2.0, 0.0])
    forward_returns = np.array([0.02, 0.01])

    result = run_backtest(scores, forward_returns, cost_bps=100.0, threshold=1.0)

    assert result["positions"].tolist() == [1.0, 0.0]
    assert result["gross_returns"].tolist() == pytest.approx([0.02, 0.0])
    assert result["net_returns"].tolist() == pytest.approx([0.0, 0.0])
    assert result["equity_curve"][-1] == pytest.approx(0.0)


def test_run_backtest_charges_full_round_trip_cost_on_each_independent_bet() -> None:
    # Two consecutive same-sign signals (as two FOMC meetings ~41 days
    # apart would produce) must each pay the full round-trip cost - this is
    # the regression test for the bug a turnover-diff cost model has: it
    # would treat [1, 1] as one continuously-held position and charge the
    # second bet almost nothing.
    scores = np.array([2.0, 2.0])
    forward_returns = np.array([0.02, 0.03])

    result = run_backtest(scores, forward_returns, cost_bps=100.0, threshold=1.0)

    round_trip_cost = 0.02  # 2 * (100 bps / 1e4)
    assert result["net_returns"].tolist() == pytest.approx(
        [0.02 - round_trip_cost, 0.03 - round_trip_cost]
    )


def test_walk_forward_splitter_is_strictly_chronological() -> None:
    train, test = WalkForwardSplitter(oos_fraction=0.3).split(10)

    assert train == slice(0, 7)
    assert test == slice(7, 10)

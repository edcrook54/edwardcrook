import numpy as np

from src.backtest.costs import CostModel


def test_no_cost_when_position_unchanged():
    model = CostModel(cost_bps=10)
    gross = np.array([0.01, 0.02, -0.01])
    positions = np.array([1.0, 1.0, 1.0])
    net = model.apply(gross, positions)
    # First bar pays entry cost (0 -> 1), subsequent bars with unchanged position pay nothing.
    assert net[1] == gross[1]
    assert net[2] == gross[2]


def test_cost_charged_on_entry_and_flip():
    model = CostModel(cost_bps=10)
    gross = np.array([0.0, 0.0, 0.0])
    positions = np.array([1.0, -1.0, -1.0])
    net = model.apply(gross, positions)

    entry_cost = 10 / 1e4
    flip_cost = 20 / 1e4  # -1 -> 1 change of 2 units of notional

    assert np.isclose(net[0], -entry_cost)
    assert np.isclose(net[1], -flip_cost)
    assert np.isclose(net[2], 0.0)

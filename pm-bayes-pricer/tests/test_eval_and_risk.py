import numpy as np
import pytest

from pmq.eval import scoring
from pmq.risk import kelly


def test_scores_reward_honest_confidence_and_punish_confident_misses() -> None:
    assert scoring.log_loss([0.5, 0.5], [1, 0]) == pytest.approx(np.log(2))
    assert scoring.brier([0.5, 0.5], [1, 0]) == pytest.approx(0.25)
    assert scoring.log_loss([0.01], [1]) > 4.0
    assert scoring.log_loss([0.9], [1]) < scoring.log_loss([0.6], [1])


def test_scoring_rules_are_proper() -> None:
    """Reporting the true probability beats shading it, on average."""
    rng = np.random.default_rng(0)
    truth = 0.7
    y = (rng.random(200_000) < truth).astype(float)
    for score in (scoring.log_loss, scoring.brier):
        honest = score(np.full_like(y, truth), y)
        assert honest < score(np.full_like(y, 0.6), y)
        assert honest < score(np.full_like(y, 0.8), y)


def test_brier_decomposition_adds_back_up() -> None:
    rng = np.random.default_rng(1)
    p = rng.uniform(0, 1, 50_000)
    y = (rng.random(50_000) < p).astype(float)
    d = scoring.brier_decomposition(p, y, bins=10)
    total = scoring.brier(p, y)
    assert d.reliability - d.resolution + d.uncertainty == pytest.approx(total, abs=0.005)


def test_calibration_slope_flags_overconfidence() -> None:
    rng = np.random.default_rng(2)
    true_p = rng.uniform(0.2, 0.8, 30_000)
    y = (rng.random(30_000) < true_p).astype(float)
    stretched = 1 / (1 + np.exp(-2.0 * np.log(true_p / (1 - true_p))))  # over-confident
    _, slope = scoring.calibration_slope_intercept(stretched, y)
    assert slope == pytest.approx(0.5, abs=0.06)
    _, slope_ok = scoring.calibration_slope_intercept(true_p, y)
    assert slope_ok == pytest.approx(1.0, abs=0.06)


def test_bootstrap_says_a_clearly_better_forecaster_is_better() -> None:
    rng = np.random.default_rng(4)
    true_p = rng.uniform(0.1, 0.9, 500)
    y = (rng.random(500) < true_p).astype(float)
    good = scoring.log_loss_each(true_p, y)
    bad = scoring.log_loss_each(np.full(500, 0.5), y)
    diff, lo, hi = scoring.paired_bootstrap_difference(good, bad, seed=1)
    assert diff < 0 and hi < 0


def test_kelly_formula_and_symmetry() -> None:
    assert kelly.kelly_fraction(0.60, 0.50) == pytest.approx(0.20)
    assert kelly.kelly_fraction(0.40, 0.50) == pytest.approx(-0.20)  # buy No instead
    assert kelly.kelly_fraction(0.50, 0.50) == 0.0


def test_kelly_stake_maximises_growth() -> None:
    p, c = 0.6, 0.5
    f_star = kelly.kelly_fraction(p, c)
    best = kelly.expected_log_growth(f_star, p, c)
    for f in (0.5 * f_star, 0.8 * f_star, 1.2 * f_star, 1.6 * f_star):
        assert kelly.expected_log_growth(f, p, c) < best


def test_half_kelly_keeps_most_growth_and_slashes_drawdown_risk() -> None:
    p, c = 0.6, 0.5
    f_star = kelly.kelly_fraction(p, c)
    ratio = kelly.expected_log_growth(0.5 * f_star, p, c) / kelly.expected_log_growth(f_star, p, c)
    assert ratio > 0.70
    assert kelly.drawdown_probability(1.0, 0.5) == pytest.approx(0.5)
    assert kelly.drawdown_probability(0.5, 0.5) == pytest.approx(0.125)


def test_multi_outcome_kelly_matches_binary_and_skips_fair_prices() -> None:
    stakes = kelly.kelly_mutually_exclusive([0.6, 0.4], [0.5, 0.5])
    assert stakes[0] == pytest.approx(0.2, abs=0.01)  # same as binary formula
    assert stakes[1] < 0.01
    fair = kelly.kelly_mutually_exclusive([0.5, 0.3, 0.2], [0.5, 0.3, 0.2])
    assert fair.sum() < 0.02  # no edge, no bet

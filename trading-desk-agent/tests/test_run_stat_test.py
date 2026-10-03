import numpy as np
import pytest

from deskagent.tools.run_stat_test import run_stat_test


def test_adf_rejects_a_clearly_stationary_series() -> None:
    rng = np.random.default_rng(0)
    series = list(rng.normal(0, 1, 200))  # white noise - clearly stationary

    result = run_stat_test("adf", series)

    assert result["test"] == "adf"
    assert result["p_value"] < 0.05


def test_adf_does_not_reject_a_random_walk() -> None:
    rng = np.random.default_rng(0)
    series = list(np.cumsum(rng.normal(0, 1, 200)))  # random walk - non-stationary

    result = run_stat_test("adf", series)

    assert result["p_value"] > 0.05


def test_engle_granger_finds_cointegration_in_a_constructed_pair() -> None:
    rng = np.random.default_rng(0)
    common = np.cumsum(rng.normal(0, 1, 300))
    a = common + rng.normal(0, 0.1, 300)
    b = common + rng.normal(0, 0.1, 300)

    result = run_stat_test("engle_granger", list(a), list(b))

    assert result["test"] == "engle_granger"
    assert result["p_value"] < 0.05


def test_engle_granger_requires_series_b() -> None:
    with pytest.raises(ValueError, match="series_b"):
        run_stat_test("engle_granger", [1.0] * 10)


def test_engle_granger_rejects_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="same length"):
        run_stat_test("engle_granger", [1.0] * 10, [1.0] * 9)


def test_newey_west_mean_matches_the_sample_mean() -> None:
    series = [0.01, 0.02, -0.01, 0.015, 0.005, 0.02, -0.005, 0.01, 0.0, 0.01]

    result = run_stat_test("newey_west_mean", series)

    assert result["mean"] == pytest.approx(sum(series) / len(series))
    assert result["n"] == 10


def test_unknown_test_name_raises() -> None:
    with pytest.raises(ValueError, match="unknown test"):
        run_stat_test("not_a_real_test", [1.0] * 10)


def test_rejects_too_short_a_series() -> None:
    with pytest.raises(ValueError, match="at least 8"):
        run_stat_test("adf", [1.0, 2.0, 3.0])

import numpy as np
import pytest

from pmq.crypto import paths
from pmq.crypto.barrier import touch_probability

DAY = 1 / 365


def test_bridge_engine_matches_the_closed_form_even_with_very_few_steps() -> None:
    rng = np.random.default_rng(0)
    sigma, t, k = 0.8, 7 * DAY, 110.0
    exact = float(touch_probability(100.0, k, sigma, t))
    for n_steps in (4, 24):
        inc = paths.gbm_increments(150_000, n_steps, t, sigma, 0.0, rng)
        p, se = paths.mc_touch_probability(inc, np.log(k / 100.0))
        assert abs(p - exact) < 4 * se + 1e-4, (n_steps, p, exact)


def test_engine_handles_down_barriers_and_already_crossed_barriers() -> None:
    rng = np.random.default_rng(1)
    inc = paths.gbm_increments(100_000, 12, 14 * DAY, 0.7, 0.2, rng)
    p, se = paths.mc_touch_probability(inc, np.log(0.9), up=False)
    assert abs(p - float(touch_probability(100.0, 90.0, 0.7, 14 * DAY, mu=0.2))) < 4 * se + 1e-4
    assert paths.mc_touch_probability(inc, -0.1, up=True) == (1.0, 0.0)


def test_merton_with_no_jumps_reduces_to_gbm() -> None:
    rng = np.random.default_rng(2)
    params = paths.MertonParams(0.6, 0.0, 0.0, 1e-9)
    inc = paths.merton_increments(150_000, 24, 10 * DAY, params, 0.0, rng)
    p, se = paths.mc_touch_probability(inc, np.log(1.12))
    assert abs(p - float(touch_probability(100.0, 112.0, 0.6, 10 * DAY))) < 4 * se + 1e-4


def test_jumps_move_probability_from_near_the_money_to_the_far_tail() -> None:
    """Same total variance, but fat tails: fewer modest touches, more extreme ones."""
    rng = np.random.default_rng(3)
    params = paths.MertonParams(0.4, 6.0, 0.0, 0.08)
    sigma_equiv = float(np.sqrt(params.total_variance_rate))
    near = paths.mc_touch_probability(
        paths.merton_increments(120_000, 120, 30 * DAY, params, 0.0, rng), np.log(1.05)
    )
    far = paths.mc_touch_probability(
        paths.merton_increments(200_000, 120, 30 * DAY, params, 0.0, rng), np.log(1.40)
    )
    assert near[0] < float(touch_probability(100.0, 105.0, sigma_equiv, 30 * DAY)) - 3 * near[1]
    assert far[0] > float(touch_probability(100.0, 140.0, sigma_equiv, 30 * DAY)) + 3 * far[1]


def test_merton_fit_recovers_the_parameters_it_was_simulated_from() -> None:
    rng = np.random.default_rng(4)
    dt = 1 / (365 * 24)
    truth = paths.MertonParams(0.4, 6.0, 0.0, 0.08)
    r = paths.merton_increments(1, 400_000, 400_000 * dt, truth, 0.0, rng).dx[0]
    fit = paths.fit_merton(r, dt)
    assert fit.sigma == pytest.approx(0.4, rel=0.05)
    assert fit.jump_rate == pytest.approx(6.0, rel=0.25)
    assert fit.jump_std == pytest.approx(0.08, rel=0.25)


def test_fhs_on_clean_gaussian_history_is_close_to_the_closed_form() -> None:
    rng = np.random.default_rng(5)
    dt = 1 / (365 * 24)
    history = 0.8 * np.sqrt(dt) * rng.standard_normal(20_000)
    inc = paths.ewma_fhs_increments(history, 40_000, 24 * 7, rng, lam=0.995)
    p, se = paths.mc_touch_probability(inc, np.log(1.10))
    assert abs(p - float(touch_probability(100.0, 110.0, 0.8, 7 * DAY))) < 4 * se + 0.03


def test_fhs_reacts_to_the_volatility_regime_at_the_end_of_history() -> None:
    rng = np.random.default_rng(6)
    calm = 0.004 * rng.standard_normal(3000)
    stormy = 0.02 * rng.standard_normal(100)
    quiet_end = np.concatenate([stormy, calm])
    stormy_end = np.concatenate([calm, stormy])
    p_quiet, _ = paths.mc_touch_probability(
        paths.ewma_fhs_increments(quiet_end, 20_000, 48, rng), np.log(1.06)
    )
    p_storm, _ = paths.mc_touch_probability(
        paths.ewma_fhs_increments(stormy_end, 20_000, 48, rng), np.log(1.06)
    )
    assert p_storm > 2 * p_quiet


def test_garch_fhs_produces_a_sensible_monotone_ladder() -> None:
    rng = np.random.default_rng(7)
    dt = 1 / (365 * 24)
    history = 0.8 * np.sqrt(dt) * rng.standard_normal(4000)
    inc = paths.garch_fhs_increments(history, 3000, 48, seed=1)
    ladder = [paths.mc_touch_probability(inc, np.log(k))[0] for k in (1.02, 1.05, 1.10, 1.20)]
    assert all(0 < p < 1 for p in ladder) and ladder == sorted(ladder, reverse=True)

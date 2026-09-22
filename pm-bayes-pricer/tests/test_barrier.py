"""The maths tests: closed forms are checked against brute-force simulation."""

import numpy as np
import pytest

from pmq.crypto import barrier

DAY = 1 / 365


def simulate_touch(s0, k, sigma, t, mu, n_steps, n_paths, seed, chunk=20_000):
    """Monte Carlo: fraction of simulated paths whose *sampled* maximum reaches the barrier."""
    rng = np.random.default_rng(seed)
    dt = t / n_steps
    nu = mu - 0.5 * sigma**2
    b = np.log(k / s0)
    hits = 0
    for start in range(0, n_paths, chunk):
        n = min(chunk, n_paths - start)
        steps = nu * dt + sigma * np.sqrt(dt) * rng.standard_normal((n, n_steps))
        path = np.cumsum(steps, axis=1)
        hits += int(np.sum(path.max(axis=1) >= b) if b > 0 else np.sum(path.min(axis=1) <= b))
    p = hits / n_paths
    return p, np.sqrt(p * (1 - p) / n_paths)


def test_reflection_principle_touch_is_twice_terminal_when_log_price_is_driftless() -> None:
    sigma = 0.7
    mu = 0.5 * sigma**2  # makes the LOG price driftless (nu = 0)
    for k in (105.0, 120.0, 150.0):
        touch = float(barrier.touch_probability(100.0, k, sigma, 30 * DAY, mu))
        end_above = float(barrier.terminal_probability(100.0, k, sigma, 30 * DAY, mu))
        assert touch == pytest.approx(2 * end_above, rel=1e-9)


def test_closed_form_matches_monte_carlo_with_the_discrete_monitoring_correction() -> None:
    sigma, t, s0 = 0.8, 7 * DAY, 100.0
    n_steps = 400
    for k, mu in [(105.0, 0.0), (110.0, 0.5), (95.0, -0.3), (90.0, 0.0)]:
        p_mc, se = simulate_touch(s0, k, sigma, t, mu, n_steps, 120_000, seed=1)
        p_bgk = float(barrier.touch_probability(s0, k, sigma, t, mu, monitor_dt_years=t / n_steps))
        assert abs(p_bgk - p_mc) < 4 * se + 0.004, (k, mu, p_bgk, p_mc)


def test_bgk_correction_is_a_real_improvement_over_ignoring_discreteness() -> None:
    sigma, t, s0, k = 0.8, 7 * DAY, 100.0, 105.0
    n_steps = 40  # coarse monitoring: the bias is large
    p_mc, _ = simulate_touch(s0, k, sigma, t, 0.0, n_steps, 200_000, seed=2)
    plain = float(barrier.touch_probability(s0, k, sigma, t))
    corrected = float(barrier.touch_probability(s0, k, sigma, t, monitor_dt_years=t / n_steps))
    assert plain > p_mc  # continuous monitoring over-states the chance of a touch
    assert abs(corrected - p_mc) < 0.35 * abs(plain - p_mc)


def test_touch_is_monotone_in_barrier_distance_horizon_and_volatility() -> None:
    ks = np.array([102, 105, 110, 120, 150.0])
    p = barrier.touch_probability(100.0, ks, 0.6, 14 * DAY)
    assert np.all(np.diff(p) < 0)  # farther away = less likely
    assert np.all(
        np.diff(barrier.touch_probability(100.0, 110.0, 0.6, np.array([1, 7, 30, 90]) * DAY)) > 0
    )
    assert np.all(
        np.diff(barrier.touch_probability(100.0, 110.0, np.array([0.2, 0.4, 0.8, 1.6]), 14 * DAY))
        > 0
    )


def test_touch_is_never_below_terminal_and_already_crossed_is_certain() -> None:
    ks = np.array([90.0, 99.0, 101.0, 110.0, 140.0])
    touch = barrier.touch_probability(100.0, ks, 0.5, 30 * DAY)
    end = np.where(
        ks > 100,
        barrier.terminal_probability(100.0, ks, 0.5, 30 * DAY),
        barrier.terminal_probability(100.0, ks, 0.5, 30 * DAY, above=False),
    )
    assert np.all(touch >= end - 1e-12)
    assert float(barrier.touch_probability(100.0, 100.0, 0.5, DAY)) == 1.0


def test_up_and_down_barriers_are_mirror_images_under_a_flipped_drift() -> None:
    sigma, t = 0.6, 20 * DAY
    up = barrier.touch_probability(100.0, 100.0 * np.exp(0.1), sigma, t, mu=0.3)
    down = barrier.touch_probability(100.0, 100.0 * np.exp(-0.1), sigma, t, mu=-0.3 + sigma**2)
    assert float(up) == pytest.approx(float(down), rel=1e-9)


def test_extreme_inputs_do_not_overflow() -> None:
    p = barrier.touch_probability(100.0, 100.0 * np.exp(5.0), 0.05, 400 * DAY, mu=50.0)
    assert 0.0 <= float(p) <= 1.0 and np.isfinite(float(p))


def test_two_barrier_exit_matches_simulation_and_the_fair_game_case() -> None:
    assert barrier.first_exit_upper_probability(100.0, 90.0, 120.0, 0.6, mu=0.18) == pytest.approx(
        (np.log(100 / 90)) / np.log(120 / 90)
    )
    rng = np.random.default_rng(3)
    sigma, mu, dt = 0.6, 0.0, 1 / (365 * 24 * 2)
    nu = mu - 0.5 * sigma**2
    lo, hi = np.log(90 / 100), np.log(115 / 100)
    n, wins = 4000, 0
    for _ in range(n):
        x = 0.0
        while lo < x < hi:
            x += nu * dt + sigma * np.sqrt(dt) * rng.standard_normal()
        wins += x >= hi
    exact = barrier.first_exit_upper_probability(100.0, 90.0, 115.0, sigma, mu)
    assert abs(wins / n - exact) < 4 * np.sqrt(exact * (1 - exact) / n) + 0.01


def test_implied_volatility_inverts_the_pricing_formula() -> None:
    for sigma in (0.3, 0.7, 1.4):
        price = float(
            barrier.touch_probability(
                100.0, 115.0, sigma, 30 * DAY, monitor_dt_years=barrier.MINUTE_YEARS
            )
        )
        assert barrier.implied_volatility(
            price, 100.0, 115.0, 30 * DAY, monitor_dt_years=barrier.MINUTE_YEARS
        ) == pytest.approx(sigma, rel=1e-6)
    assert np.isnan(barrier.implied_volatility(0.999999, 100.0, 300.0, DAY))

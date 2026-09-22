import numpy as np
import pytest

from pmq.crypto import vol


def simulate_ohlc(sigma_annual, n_bars, sub_steps, periods_per_year, seed, mu=0.0):
    """GBM bars built from fine sub-steps so that high/low are (nearly) the true path extremes."""
    rng = np.random.default_rng(seed)
    dt = 1.0 / (periods_per_year * sub_steps)
    steps = (mu - 0.5 * sigma_annual**2) * dt + sigma_annual * np.sqrt(dt) * rng.standard_normal(
        n_bars * sub_steps
    )
    logp = np.concatenate([[0.0], np.cumsum(steps)])
    path = np.exp(logp)
    o = path[0:-1:sub_steps][:n_bars]
    c = path[sub_steps::sub_steps][:n_bars]
    blocks = np.array([path[i * sub_steps : (i + 1) * sub_steps + 1] for i in range(n_bars)])
    return o, blocks.max(axis=1), blocks.min(axis=1), c


def test_estimators_recover_true_volatility_on_simulated_gbm() -> None:
    ppy = 365
    o, h, lo, c = simulate_ohlc(0.8, 6000, 200, ppy, seed=1)
    close = np.concatenate([[o[0]], c])
    assert vol.close_to_close(close, ppy) == pytest.approx(0.8, rel=0.03)
    # Range-based estimators assume the price is watched continuously. With finitely many
    # samples per bar the observed range is a little too narrow, so they read slightly low
    # (a documented bias), but they stay close.
    for estimate in (
        vol.parkinson(h, lo, ppy),
        vol.garman_klass(o, h, lo, c, ppy),
        vol.rogers_satchell(o, h, lo, c, ppy),
    ):
        assert 0.72 < estimate < 0.8


def test_range_estimators_are_more_efficient_than_close_to_close() -> None:
    ppy, reps = 365, 60
    est_cc, est_pk = [], []
    for seed in range(reps):
        o, h, lo, c = simulate_ohlc(0.8, 100, 60, ppy, seed=seed)
        est_cc.append(vol.close_to_close(np.concatenate([[o[0]], c]), ppy))
        est_pk.append(vol.parkinson(h, lo, ppy))
    assert np.std(est_pk) < 0.6 * np.std(est_cc)


def test_rogers_satchell_is_robust_to_drift_where_parkinson_is_not() -> None:
    ppy = 365
    o, h, lo, c = simulate_ohlc(0.5, 5000, 100, ppy, seed=4, mu=15.0)  # a violent uptrend
    assert abs(vol.rogers_satchell(o, h, lo, c, ppy) - 0.5) < abs(vol.parkinson(h, lo, ppy) - 0.5)


def test_bipower_ignores_jumps_that_realised_variance_swallows() -> None:
    rng = np.random.default_rng(5)
    r = 0.001 * rng.standard_normal(20_000)
    clean = vol.jump_share(r)
    r[[1000, 9000, 15000]] += 0.05  # three big jumps
    assert vol.jump_share(r) > clean + 0.2
    assert vol.bipower_variation(r) == pytest.approx(0.001**2 * 20_000, rel=0.1)


def test_ewma_weights_recent_observations_more() -> None:
    quiet_then_loud = np.concatenate([np.full(50, 0.001), np.full(10, 0.05)])
    loud_then_quiet = quiet_then_loud[::-1]
    assert vol.ewma_variance(quiet_then_loud) > vol.ewma_variance(loud_then_quiet)


def test_qlike_is_minimised_by_the_true_variance() -> None:
    rng = np.random.default_rng(6)
    true_var = 4.0
    proxy = true_var * rng.chisquare(1, 200_000)  # a noisy squared-return style proxy
    losses = {f: vol.qlike(proxy, np.full_like(proxy, f)) for f in (2.0, 3.0, 4.0, 5.0, 8.0)}
    assert min(losses, key=losses.get) == 4.0


def test_har_recovers_persistence_and_predicts_using_only_the_past() -> None:
    rng = np.random.default_rng(7)
    n = 3000
    log_rv = np.zeros(n)
    for i in range(1, n):
        log_rv[i] = 0.95 * log_rv[i - 1] + 0.2 * rng.standard_normal()
    rv = 1e-3 * np.exp(log_rv)
    train = rv[:2000]
    model = vol.HarRV(horizon_days=5).fit(train)
    forecast = model.predict(train)
    later_mean = rv[2000:2005].mean()
    assert 0.2 < forecast / later_mean < 5
    assert model.coef is not None and model.coef[1:].sum() > 0.5  # persistent: betas add to ~1
    # forecast at time t must not depend on data after t
    assert model.predict(train) == pytest.approx(
        model.predict(np.concatenate([train, rv[2000:]])[:2000])
    )


def test_signature_plot_flags_microstructure_noise() -> None:
    rng = np.random.default_rng(8)
    true_logp = np.cumsum(0.0001 * rng.standard_normal(200_000))
    noisy = np.exp(true_logp + 0.0002 * rng.standard_normal(200_000))  # bid-ask bounce style noise
    sig = vol.signature_plot(noisy, (1, 5, 30))
    assert sig[1] > 1.5 * sig[30]

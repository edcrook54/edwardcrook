import numpy as np
import pytest
from scipy import stats

from pmq.crypto import bayes_vol, vol
from pmq.crypto.barrier import touch_probability

DAY = 1 / 365


def test_posterior_matches_brute_force_numerical_integration() -> None:
    """The conjugate formula must agree with 'multiply prior by likelihood and normalise'."""
    rng = np.random.default_rng(1)
    prior = bayes_vol.VarianceBelief(alpha=3.0, beta=0.004)
    data = 0.05 * rng.standard_normal(40)
    post = prior.update(data)

    grid = np.linspace(1e-5, 0.02, 200_000)
    log_prior = stats.invgamma.logpdf(grid, prior.alpha, scale=prior.beta)
    log_lik = np.sum(stats.norm.logpdf(data[:, None], scale=np.sqrt(grid)[None, :]), axis=0)
    weights = np.exp(log_prior + log_lik - (log_prior + log_lik).max())
    weights /= weights.sum()
    numeric_mean = float(np.sum(weights * grid))
    assert post.mean_variance == pytest.approx(numeric_mean, rel=1e-3)


def test_more_data_narrows_the_volatility_range_and_it_covers_the_truth() -> None:
    rng = np.random.default_rng(2)
    prior = bayes_vol.VarianceBelief.from_annual_vol(0.6, 365, strength=4)
    true_sigma, hits, trials = 0.9, 0, 300
    widths = []
    for _ in range(trials):
        data = true_sigma / np.sqrt(365) * rng.standard_normal(60)
        lo, hi = prior.update(data).credible_interval_vol(365, level=0.9)
        hits += lo <= true_sigma <= hi
        widths.append(hi - lo)
    assert 0.84 < hits / trials < 0.96  # a 90% interval should cover ~90% of the time
    narrow = prior.update(true_sigma / np.sqrt(365) * rng.standard_normal(600))
    lo, hi = narrow.credible_interval_vol(365)
    assert hi - lo < np.mean(widths)


def test_discounted_filter_matches_step_by_step_updates() -> None:
    rng = np.random.default_rng(3)
    r = 0.02 * rng.standard_normal(200)
    prior = bayes_vol.VarianceBelief(2.0, 0.001)
    alpha, beta = bayes_vol.filter_discounted(r, 0.97, prior)
    belief = prior
    for x in r:
        belief = belief.discount(0.97).update([x])
    assert alpha[-1] == pytest.approx(belief.alpha)
    assert beta[-1] == pytest.approx(belief.beta)


def test_discounted_bayes_is_ewma_in_disguise() -> None:
    """beta/alpha is exactly the exponentially weighted mean of squared returns (lambda = delta)."""
    rng = np.random.default_rng(4)
    r = 0.02 * rng.standard_normal(1500)
    delta = 0.94
    tiny_prior = bayes_vol.VarianceBelief(1e-9, 1e-12)
    alpha, beta = bayes_vol.filter_discounted(r, delta, tiny_prior)
    assert beta[-1] / alpha[-1] == pytest.approx(vol.ewma_variance(r, lam=delta), rel=1e-6)


def test_simulation_based_calibration_ranks_are_uniform() -> None:
    """If update code were wrong, ranks would pile up in the middle or at the edges."""
    prior = bayes_vol.VarianceBelief(alpha=4.0, beta=0.003)
    ranks = bayes_vol.simulation_based_calibration(
        prior, n_obs=25, n_trials=3000, n_draws=19, seed=5
    )
    counts = np.bincount(ranks, minlength=20)
    assert stats.chisquare(counts).pvalue > 0.001


def test_broken_update_would_be_caught_by_calibration_check() -> None:
    """Sanity-check the checker itself: an overconfident (double-counted) update fails it."""

    class Overconfident(bayes_vol.VarianceBelief):
        def update(self, returns):  # type: ignore[no-untyped-def]
            r = np.asarray(returns, dtype=float)
            return Overconfident(self.alpha + r.size, self.beta + float(np.sum(r**2)))

    prior = Overconfident(alpha=4.0, beta=0.003)
    ranks = bayes_vol.simulation_based_calibration(
        prior, n_obs=25, n_trials=3000, n_draws=19, seed=6
    )
    assert stats.chisquare(np.bincount(ranks, minlength=20)).pvalue < 1e-6


def test_parameter_uncertainty_raises_far_out_touch_probability_by_jensen() -> None:
    belief = bayes_vol.VarianceBelief.from_annual_vol(0.6, 365, strength=10)
    far = bayes_vol.posterior_touch_probability(belief, 365, 100.0, 160.0, 30 * DAY)
    assert far.mean > far.plug_in * 1.05
    assert far.low < far.plug_in < far.high
    # A belief that is very sure of its volatility should collapse onto the plug-in answer.
    firm = bayes_vol.VarianceBelief.from_annual_vol(0.6, 365, strength=20_000)
    sure = bayes_vol.posterior_touch_probability(firm, 365, 100.0, 160.0, 30 * DAY)
    assert sure.mean == pytest.approx(sure.plug_in, rel=0.03)


def test_touch_probability_is_convex_in_sigma_for_far_barriers() -> None:
    sigmas = np.linspace(0.3, 1.2, 10)
    p = touch_probability(100.0, 160.0, sigmas, 30 * DAY)
    assert np.all(np.diff(p, n=2) > 0)

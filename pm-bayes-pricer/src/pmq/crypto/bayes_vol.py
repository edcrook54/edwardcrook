"""A Bayesian belief about volatility, and what it does to a touch probability.

Plain-English version. Volatility is not known; we estimate it from a limited amount of data.
A single estimate ("vol is 55%") hides how unsure we are. Bayes keeps the *whole range* of
plausible volatilities, each with a probability, and the forecast averages over all of them.

**The update rule.** Model each period's return as ``r ~ Normal(0, s2)`` where ``s2`` is the
unknown per-period variance. Hold a belief about ``s2`` as an *Inverse-Gamma(alpha, beta)*
distribution. After seeing ``n`` returns the belief is again Inverse-Gamma (conjugacy):

    alpha' = alpha + n / 2          beta' = beta + (1/2) * sum(r_i ** 2)

Reading it: ``alpha`` counts how many observations of evidence you hold, ``beta`` is the
accumulated squared movement. The posterior mean variance is ``beta / (alpha - 1)``.

**Forgetting.** Volatility changes over time, so old data should fade. Before each update,
multiply ``alpha`` and ``beta`` by a discount ``delta`` slightly below 1 (West & Harrison's
"discount" method). The effective memory is ``1 / (1 - delta)`` observations, which also
stops the belief from becoming falsely certain. A neat consequence: with this rule the
posterior mean is (almost exactly) the classic EWMA / RiskMetrics variance with ``lambda = delta``.
So EWMA is Bayesian updating in disguise.

**Why the touch probability rises.** A barrier several standard deviations away is much more
likely to be hit if volatility turns out high than it is *unlikely* if volatility turns out
low: the probability is a **convex** function of ``sigma`` there. Averaging a convex function over
uncertainty gives a *larger* number than plugging in the average (Jensen's inequality). So
honest uncertainty about volatility pushes far-out touch probabilities **up**.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.signal import lfilter
from scipy.stats import invgamma

from pmq.crypto.barrier import touch_probability

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class VarianceBelief:
    """Inverse-Gamma belief about the per-period return variance ``s2``."""

    alpha: float
    beta: float

    def __post_init__(self) -> None:
        if self.alpha <= 0 or self.beta <= 0:
            raise ValueError("alpha and beta must be positive")

    @classmethod
    def from_annual_vol(
        cls, annual_vol: float, periods_per_year: float, strength: float
    ) -> VarianceBelief:
        """Prior centred on ``annual_vol`` and worth ``strength`` observations of evidence."""
        per_period_var = annual_vol**2 / periods_per_year
        alpha = strength / 2.0
        return cls(alpha, per_period_var * (alpha + 1.0))  # puts the *mode* at per_period_var

    def update(self, returns: ArrayLike) -> VarianceBelief:
        r = np.asarray(returns, dtype=float)
        return VarianceBelief(self.alpha + r.size / 2.0, self.beta + 0.5 * float(np.sum(r**2)))

    def discount(self, delta: float) -> VarianceBelief:
        """Forget: multiply alpha and beta by ``delta`` (beta/alpha is unchanged)."""
        if not 0.0 < delta <= 1.0:
            raise ValueError("delta must be in (0, 1]")
        return VarianceBelief(self.alpha * delta, self.beta * delta)

    @property
    def mean_variance(self) -> float:
        if self.alpha <= 1:
            return float("inf")
        return self.beta / (self.alpha - 1.0)

    @property
    def effective_observations(self) -> float:
        return 2.0 * self.alpha

    def sample(self, n: int, rng: np.random.Generator) -> FloatArray:
        """Draw plausible per-period variances: beta / Gamma(alpha)."""
        return np.asarray(self.beta / rng.gamma(self.alpha, size=n), dtype=float)

    def credible_interval_vol(
        self, periods_per_year: float, level: float = 0.9
    ) -> tuple[float, float]:
        """Range of annualised volatilities holding ``level`` of the belief."""
        tail = (1 - level) / 2
        q = np.asarray(invgamma.ppf([tail, 1 - tail], self.alpha, scale=self.beta), dtype=float)
        return float(np.sqrt(q[0] * periods_per_year)), float(np.sqrt(q[1] * periods_per_year))


def filter_discounted(
    returns: ArrayLike, delta: float, prior: VarianceBelief
) -> tuple[FloatArray, FloatArray]:
    """Run the discounted update over a whole return series in one pass.

    Returns ``(alpha_t, beta_t)`` after each observation. The recursions are
    ``alpha_t = delta * alpha_{t-1} + 1/2`` and ``beta_t = delta * beta_{t-1} + r_t**2 / 2``,
    which are linear filters, so they run in vectorised C rather than a Python loop.
    """
    r = np.asarray(returns, dtype=float)
    a0, b0 = prior.alpha, prior.beta
    # y_t = delta * y_{t-1} + x_t  with the initial state folded into the first input.
    ones = np.full(r.size, 0.5)
    alpha_in = ones.copy()
    alpha_in[0] += delta * a0
    beta_in = 0.5 * r**2
    beta_in[0] += delta * b0
    alpha = lfilter([1.0], [1.0, -delta], alpha_in)
    beta = lfilter([1.0], [1.0, -delta], beta_in)
    return np.asarray(alpha, dtype=float), np.asarray(beta, dtype=float)


@dataclass(frozen=True)
class PosteriorTouch:
    plug_in: float  # touch probability at the posterior-mean volatility
    mean: float  # the honest answer: averaged over the whole belief
    low: float
    high: float
    draws: FloatArray


def posterior_touch_probability(
    belief: VarianceBelief,
    periods_per_year: float,
    s0: float,
    k: float,
    t_years: float,
    mu: float = 0.0,
    monitor_dt_years: float = 0.0,
    n_draws: int = 4000,
    level: float = 0.9,
    seed: int = 0,
) -> PosteriorTouch:
    """Posterior predictive touch probability: closed form averaged over the volatility belief."""
    rng = np.random.default_rng(seed)
    sigma_draws = np.sqrt(belief.sample(n_draws, rng) * periods_per_year)
    p = touch_probability(s0, k, sigma_draws, t_years, mu, monitor_dt_years)
    plug = float(
        touch_probability(
            s0, k, np.sqrt(belief.mean_variance * periods_per_year), t_years, mu, monitor_dt_years
        )
    )
    tail = (1 - level) / 2
    return PosteriorTouch(
        plug_in=plug,
        mean=float(p.mean()),
        low=float(np.quantile(p, tail)),
        high=float(np.quantile(p, 1 - tail)),
        draws=p,
    )


def simulation_based_calibration(
    prior: VarianceBelief,
    n_obs: int,
    n_trials: int = 1000,
    n_draws: int = 99,
    seed: int = 0,
) -> FloatArray:
    """Check the update code is right by simulation (Talts et al., 2018).

    Repeat many times: (1) draw a true variance from the prior, (2) simulate data from it,
    (3) compute the posterior, (4) record where the true value ranks among posterior draws.
    If the prior/likelihood/update are all consistent, the ranks are **uniform**. A hump or a
    U-shape in their histogram exposes a bug or an over/under-confident posterior.
    Returns integer ranks in ``0..n_draws``.
    """
    rng = np.random.default_rng(seed)
    ranks = np.empty(n_trials, dtype=int)
    for i in range(n_trials):
        true_var = float(prior.sample(1, rng)[0])
        data = np.sqrt(true_var) * rng.standard_normal(n_obs)
        post = prior.update(data)
        draws = post.sample(n_draws, rng)
        ranks[i] = int(np.sum(draws < true_var))
    return ranks

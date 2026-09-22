"""Dirichlet-Multinomial belief over a set of mutually exclusive outcomes.

Plain-English version. Suppose the Fed can do one of K things at a meeting. Before looking at
any evidence you hold a belief about how likely each is. Write that belief as "pseudo-counts":
alpha = (2, 6, 2) reads as "I hold this view as strongly as if I had seen 2 cuts, 6 holds and
2 hikes in 10 past meetings". A bigger total means a firmer view.

Bayes' rule then has a beautifully simple form for this setup. Every time you observe an
outcome, add 1 to its pseudo-count. The result is again a Dirichlet, so you can keep going
forever (this "closed under updating" property is what *conjugate* means).

    prior  Dirichlet(alpha)   +   observed counts n   ->   posterior  Dirichlet(alpha + n)

The forecast for the next event is the posterior mean: alpha_k / sum(alpha).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from numpy.typing import ArrayLike, NDArray
from scipy.special import gammaln
from scipy.stats import beta as beta_dist

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class DirichletBelief:
    labels: tuple[str, ...]
    alpha: FloatArray

    def __post_init__(self) -> None:
        if len(self.labels) != len(self.alpha) or np.any(self.alpha <= 0):
            raise ValueError("need one strictly positive pseudo-count per label")

    @classmethod
    def from_probabilities(
        cls, labels: tuple[str, ...], probs: ArrayLike, strength: float
    ) -> DirichletBelief:
        """Encode a starting forecast ``probs`` held as firmly as ``strength`` past events."""
        p = np.asarray(probs, dtype=float)
        if not np.isclose(p.sum(), 1.0):
            raise ValueError("probabilities must add to 1")
        return cls(labels, np.maximum(p * strength, 1e-6))

    @property
    def strength(self) -> float:
        return float(self.alpha.sum())

    def update(self, counts: ArrayLike) -> DirichletBelief:
        """Bayes' rule: add the observed outcome counts to the pseudo-counts."""
        return DirichletBelief(self.labels, self.alpha + np.asarray(counts, dtype=float))

    def mean(self) -> FloatArray:
        """Forecast for the next event (the posterior predictive probabilities)."""
        return self.alpha / self.alpha.sum()

    def credible_interval(self, level: float = 0.90) -> FloatArray:
        """Range each outcome's probability plausibly lies in. Shape (K, 2): lower, upper.

        Each single outcome's marginal is a Beta(alpha_k, total - alpha_k) distribution.
        """
        tail = (1 - level) / 2
        total = self.alpha.sum()
        lo = beta_dist.ppf(tail, self.alpha, total - self.alpha)
        hi = beta_dist.ppf(1 - tail, self.alpha, total - self.alpha)
        return np.column_stack([lo, hi])

    def sample(self, n: int, rng: np.random.Generator) -> FloatArray:
        """Draw plausible probability vectors, e.g. to push uncertainty through a P&L run."""
        return rng.dirichlet(self.alpha, size=n)

    def log_evidence(self, counts: ArrayLike) -> float:
        """log P(counts | this prior): how well this prior predicted what actually happened.

        Comparing this number between two priors is Bayesian model comparison: the prior that
        put more probability on the data that showed up wins. (Multinomial coefficient omitted;
        it is identical for every prior so it cancels in comparisons.)
        """
        n = np.asarray(counts, dtype=float)
        a0, n0 = self.alpha.sum(), n.sum()
        return float(
            gammaln(a0) - gammaln(a0 + n0) + np.sum(gammaln(self.alpha + n) - gammaln(self.alpha))
        )


def counts_from_outcome(index: int, size: int) -> FloatArray:
    """One-hot count vector for a single observed outcome."""
    out = np.zeros(size)
    out[index] = 1.0
    return out

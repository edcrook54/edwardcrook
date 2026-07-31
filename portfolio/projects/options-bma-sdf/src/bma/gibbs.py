"""Spike-and-slab Gibbs sampler for the Bayesian model averaging SDF.

Follows Bryzgalova, Huang & Julliard (2023, JF) and its application to
options in Käfer, Mörke, Weigert & Wiest (2026). Samples over the space of
factor-inclusion vectors gamma and risk prices lambda, using a
continuous spike-and-slab prior (eq. 3-4 of the options paper) rather than
flat priors, to keep posterior probabilities well-defined under weak
factors.

Reference implementation notes (paper uses these settings):
    - GLS cross-sectional weighting
    - 500,000 Gibbs steps, first 50,000 dropped as burn-in
    - non-informative Beta(1,1) prior on factor inclusion probability
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class BMAConfig:
    n_steps: int = 50_000  # scaled down from paper's 500k for a smaller factor set
    burn_in: int = 5_000
    prior_sharpe_ratio: float = 0.5  # as a fraction of ex-post max achievable SR
    beta_a: float = 1.0
    beta_b: float = 1.0
    spike_r: float = 1e-4  # near-zero prior variance for excluded factors


class BMASDFSampler:
    """Gibbs sampler for the option BMA-SDF.

    TODO:
        - implement conditional posteriors for (lambda | gamma, sigma2, data)
        - implement conditional posterior for gamma (factor inclusion)
        - implement conditional posterior for omega (inclusion probability)
        - track posterior inclusion probabilities E[gamma_j | data]
        - track posterior mean risk prices E[lambda_j | data]
    """

    def __init__(self, factors: np.ndarray, test_asset_returns: np.ndarray, config: BMAConfig | None = None):
        self.factors = factors
        self.test_asset_returns = test_asset_returns
        self.config = config or BMAConfig()

    def run(self) -> dict[str, np.ndarray]:
        raise NotImplementedError("Gibbs sampling loop not yet implemented")

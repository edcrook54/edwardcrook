"""Monte Carlo price paths, for the cases where no closed-form touch formula exists.

The closed forms in ``barrier.py`` assume returns are Gaussian with constant volatility.
Crypto is not like that: it has sudden jumps, and calm periods followed by turbulent ones.
When the model has those features there is no formula, so we simulate many possible futures
and count how many touch the level.

Two ideas make the simulation accurate:

**Brownian-bridge crossing.** We only simulate the price at discrete steps (say hourly), but a
real path can poke through the barrier *between* two steps and come back. Given the two end
points of a step, both below the barrier, the chance the path crossed in between is exactly

    q = exp( -2 * (b - x_i) * (b - x_{i+1}) / v_i )

where ``b`` is the log barrier, ``x`` the log price at the step ends and ``v_i`` the variance
of that step. We combine these step-by-step chances instead of drawing another random number,
which both removes the discretisation bias and lowers the noise ("Rao-Blackwellisation").

**Filtered historical simulation (FHS).** Take the history of returns, divide each by the
volatility that prevailed at the time to get "standardised shocks" (which look identically
distributed), then re-use those shocks in random order while letting a volatility model
(EWMA or GARCH) scale them. The result keeps the *real* fat tails and volatility clustering
without assuming any particular distribution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import ArrayLike, NDArray

FloatArray = NDArray[np.float64]


@dataclass(frozen=True)
class Increments:
    """Simulated log-price increments, ``dx[path, step]``, and each step's variance ``var``."""

    dx: FloatArray
    var: FloatArray


def mc_touch_probability(
    inc: Increments, log_barrier: float, up: bool = True, chunk: int = 20_000
) -> tuple[float, float]:
    """Probability of touching the barrier, and its Monte Carlo standard error.

    ``log_barrier`` is ln(K / S0). Uses the Brownian-bridge crossing chance between steps.
    """
    sign = 1.0 if up else -1.0
    b = sign * log_barrier
    if b <= 0:
        return 1.0, 0.0
    n_paths = inc.dx.shape[0]
    per_path = np.empty(n_paths)
    for lo in range(0, n_paths, chunk):
        dx = sign * inc.dx[lo : lo + chunk]
        var = inc.var[lo : lo + chunk] if inc.var.shape[0] == n_paths else inc.var
        x_end = np.cumsum(dx, axis=1)
        x_start = np.concatenate([np.zeros((dx.shape[0], 1)), x_end[:, :-1]], axis=1)
        crossed = (x_end >= b) | (x_start >= b)
        with np.errstate(over="ignore", invalid="ignore"):
            q = np.exp(-2.0 * (b - x_start) * (b - x_end) / var)
        q = np.where(crossed, 1.0, np.clip(q, 0.0, 1.0))
        with np.errstate(divide="ignore"):
            log_survive = np.sum(np.log1p(-q), axis=1)
        per_path[lo : lo + chunk] = 1.0 - np.exp(log_survive)
    return float(per_path.mean()), float(per_path.std(ddof=1) / np.sqrt(n_paths))


# --- Samplers -----------------------------------------------------------------------------


def gbm_increments(
    n_paths: int,
    n_steps: int,
    t_years: float,
    sigma: float,
    mu: float,
    rng: np.random.Generator,
) -> Increments:
    """Plain Gaussian random walk: the closed form's own model, used to validate the engine."""
    dt = t_years / n_steps
    dx = (mu - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * rng.standard_normal((n_paths, n_steps))
    return Increments(dx, np.full((1, n_steps), sigma**2 * dt))


@dataclass(frozen=True)
class MertonParams:
    """Diffusion volatility, jumps per year, and the jump mean and std (in log-price units)."""

    sigma: float
    jump_rate: float
    jump_mean: float
    jump_std: float

    @property
    def total_variance_rate(self) -> float:
        return self.sigma**2 + self.jump_rate * (self.jump_mean**2 + self.jump_std**2)


def fit_merton(returns: ArrayLike, dt_years: float, threshold: float = 4.5) -> MertonParams:
    """Split returns into "ordinary" and "jump" using a robust scale, then fit each part.

    A return further than ``threshold`` robust standard deviations from zero is called a jump.
    The robust scale is the median absolute deviation, which the jumps themselves cannot inflate.
    Diffusion volatility comes from the ordinary returns; jump rate, mean and spread from the rest.
    """
    r = np.asarray(returns, dtype=float)
    scale = 1.4826 * np.median(np.abs(r - np.median(r)))
    is_jump = np.abs(r) > threshold * scale
    ordinary = r[~is_jump]
    sigma = float(np.std(ordinary, ddof=1) / np.sqrt(dt_years))
    n_jumps = int(is_jump.sum())
    if n_jumps < 3:
        return MertonParams(sigma, 0.0, 0.0, 1e-9)
    jumps = r[is_jump]
    return MertonParams(
        sigma,
        n_jumps / (r.size * dt_years),
        float(jumps.mean()),
        float(max(jumps.std(ddof=1), 1e-9)),
    )


def merton_increments(
    n_paths: int,
    n_steps: int,
    t_years: float,
    params: MertonParams,
    mu: float,
    rng: np.random.Generator,
) -> Increments:
    """Merton (1976) jump-diffusion, with the drift set so the *price* drifts at ``mu``."""
    dt = t_years / n_steps
    kappa = np.exp(params.jump_mean + 0.5 * params.jump_std**2) - 1.0  # mean jump, in price terms
    drift = (mu - 0.5 * params.sigma**2 - params.jump_rate * kappa) * dt
    diffusion = params.sigma * np.sqrt(dt) * rng.standard_normal((n_paths, n_steps))
    n_jumps = rng.poisson(params.jump_rate * dt, size=(n_paths, n_steps))
    jump_total = params.jump_mean * n_jumps + params.jump_std * np.sqrt(
        n_jumps
    ) * rng.standard_normal((n_paths, n_steps))
    var_step = params.sigma**2 * dt  # the bridge only needs the *continuous* part's variance
    return Increments(drift + diffusion + jump_total, np.full((1, n_steps), var_step))


def ewma_volatility_path(returns: FloatArray, lam: float) -> FloatArray:
    """EWMA variance after each return: v_t = lam * v_{t-1} + (1 - lam) * r_t**2."""
    v = np.empty(returns.size)
    v[0] = float(np.mean(returns[: min(50, returns.size)] ** 2))
    for t in range(1, returns.size):
        v[t] = lam * v[t - 1] + (1 - lam) * returns[t - 1] ** 2
    return v


def ewma_fhs_increments(
    history: ArrayLike,
    n_paths: int,
    n_steps: int,
    rng: np.random.Generator,
    lam: float = 0.94,
    block: int = 5,
    drift_per_step: float = 0.0,
) -> Increments:
    """Filtered historical simulation with an EWMA volatility model.

    1. Compute EWMA variance through the history and standardise: ``z_t = r_t / sqrt(v_t)``.
    2. Simulate forward: pick a random *block* of consecutive shocks (blocks preserve any
       short-range dependence), scale it by the current simulated volatility, then update
       the volatility with the simulated return. Repeat for every step of every path.
    """
    r = np.asarray(history, dtype=float)
    v_hist = ewma_volatility_path(r, lam)
    z = r / np.sqrt(v_hist)
    z = (z - z.mean()) / z.std()  # exactly zero mean, unit variance shocks
    v_next = lam * v_hist[-1] + (1 - lam) * r[-1] ** 2

    dx = np.empty((n_paths, n_steps))
    var = np.empty((n_paths, n_steps))
    v = np.full(n_paths, v_next)
    starts = np.zeros(n_paths, dtype=int)
    for step in range(n_steps):
        if step % block == 0:
            starts = rng.integers(0, z.size - block, size=n_paths)
        shock = z[starts + (step % block)]
        var[:, step] = v
        ret = np.sqrt(v) * shock + drift_per_step
        dx[:, step] = ret
        v = lam * v + (1 - lam) * ret**2
    return Increments(dx, var)


def garch_fhs_increments(
    history: ArrayLike, n_paths: int, n_steps: int, seed: int = 0
) -> Increments:
    """Filtered historical simulation from a GARCH(1,1) with Student-t innovations (via ``arch``).

    ``history`` are per-step log returns (e.g. hourly). Returns are rescaled to percent for the
    optimiser (which likes numbers near 1) and converted back afterwards.
    """
    from arch import arch_model

    r = np.asarray(history, dtype=float) * 100.0
    fit = arch_model(r, mean="Zero", vol="GARCH", p=1, q=1, dist="t").fit(disp="off")
    forecast = fit.forecast(
        horizon=n_steps,
        method="bootstrap",
        simulations=n_paths,
        reindex=False,
        rng=np.random.default_rng(seed).standard_normal,
    )
    sims: Any = forecast.simulations
    dx = np.asarray(sims.values[-1], dtype=float) / 100.0
    var = np.asarray(sims.residual_variances[-1], dtype=float) / 1e4
    return Increments(dx, var)

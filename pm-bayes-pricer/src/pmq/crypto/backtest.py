"""Walk-forward backtest of "will it touch the level?" forecasts on Kraken data.

What is being tested. At every anchor time (every few hours) we imagine a venue listing a set of
contracts "will BTC touch $K within the next 1 / 7 / 30 days?" for strikes above and below the
current price. Each model prices every contract using only information available at that
moment. Later we look at the tick data to see what really happened, and grade the forecasts.

Why this is honest:

* **Point-in-time.** Every input is computed from hours before the anchor (see ``features``).
* **Purged walk-forward.** Anything that is *fitted* (HAR coefficients, the volatility-of-
  volatility used for mixing, the recalibration curve, the empirical base rates) is fitted only
  on contracts whose outcome was already known on the first day of the test year.
* **Strikes are not chosen by any model.** They sit on a grid measured in units of the trailing
  30-day volatility, so no model under test decides which questions get asked.
* **Overlap-aware uncertainty.** Contracts opened hours apart are nearly the same bet, so
  confidence intervals come from resampling whole weeks, not individual contracts.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import yaml
from numpy.typing import NDArray
from scipy.stats import invgamma

from pmq.config import get_settings
from pmq.crypto import features as feat
from pmq.crypto import ticks
from pmq.crypto.barrier import MINUTE_YEARS, terminal_probability, touch_probability
from pmq.crypto.grid import HOURS_PER_YEAR, HourlyGrid, WindowExtremes, build_hourly_grid
from pmq.eval import scoring

FloatArray = NDArray[np.float64]
MODELS = (
    "naive_2x",
    "gbm_trailing30",
    "gbm_rv7",
    "gbm_ewma",
    "gbm_har",
    "bayes_disc",
    "har_mix",
    "har_mix_recal",
    "base_rate",
)


@dataclass(frozen=True)
class BacktestConfig:
    asset: str = "XBT"
    start: str = "2017-01-01"
    first_test_year: int = 2019
    end_year: int = 2025
    anchor_step_hours: int = 6
    horizons_days: tuple[int, ...] = (1, 7, 30)
    z_grid: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0, 2.5, 3.0)
    ewma_half_life_days: float = 5.0
    bayes_memory_days: float = 10.0
    min_coverage: float = 0.9
    n_quadrature: int = 15


def load_config(path: str | Path) -> BacktestConfig:
    raw: dict[str, Any] = yaml.safe_load(Path(path).read_text())
    for key in ("horizons_days", "z_grid"):
        if key in raw:
            raw[key] = tuple(raw[key])
    return BacktestConfig(**raw)


# --- Contract universe ----------------------------------------------------------------------


def build_universe(
    grid: HourlyGrid, f: feat.VolFeatures, cfg: BacktestConfig
) -> dict[str, FloatArray]:
    """Every contract that would have been listed, with its true outcome."""
    n = len(grid)
    warmup = 30 * 24
    max_h = 24 * max(cfg.horizons_days)
    anchors = np.arange(warmup, n - max_h, cfg.anchor_step_hours)
    ok = np.isfinite(f.trailing30_vol[anchors]) & (f.coverage30[anchors] >= cfg.min_coverage)
    ok &= np.isfinite(f.rv30d_var[anchors]) & (f.trailing30_vol[anchors] > 0)
    anchors = anchors[ok]
    extremes = WindowExtremes(grid)

    cols: dict[str, list[FloatArray]] = {
        k: []
        for k in (
            "anchor",
            "horizon_d",
            "z",
            "direction",
            "s0",
            "k",
            "sigma_ref",
            "label",
            "resolve",
        )
    }
    for d in cfg.horizons_days:
        hours = 24 * d
        t_years = d / 365.0
        hi = extremes.highest(anchors, hours)
        lo = extremes.lowest(anchors, hours)
        s0 = grid.close[anchors - 1]
        sig_ref = f.trailing30_vol[anchors]
        for z in cfg.z_grid:
            for direction in (1.0, -1.0):
                k = s0 * np.exp(direction * z * sig_ref * np.sqrt(t_years))
                label = (hi >= k) if direction > 0 else (lo <= k)
                for name, val in (
                    ("anchor", anchors.astype(float)),
                    ("horizon_d", np.full(anchors.size, float(d))),
                    ("z", np.full(anchors.size, z)),
                    ("direction", np.full(anchors.size, direction)),
                    ("s0", s0),
                    ("k", k),
                    ("sigma_ref", sig_ref),
                    ("label", label.astype(float)),
                    ("resolve", (anchors + hours).astype(float)),
                ):
                    cols[name].append(val)
    return {k: np.concatenate(v) for k, v in cols.items()}


# --- Model components -----------------------------------------------------------------------


def _touch(u: dict[str, FloatArray], sigma: FloatArray) -> FloatArray:
    """Touch probability under 1-minute monitoring, price drift 0."""
    return touch_probability(u["s0"], u["k"], sigma, u["horizon_d"] / 365.0, 0.0, MINUTE_YEARS)


def _naive_2x(u: dict[str, FloatArray]) -> FloatArray:
    """Rule of thumb: a touch is twice as likely as finishing beyond the level."""
    t = u["horizon_d"] / 365.0
    above = terminal_probability(u["s0"], u["k"], u["sigma_ref"], t, 0.0, above=True)
    end_beyond = np.where(u["direction"] > 0, above, 1.0 - above)
    return np.asarray(np.minimum(1.0, 2.0 * end_beyond), dtype=float)


def _quadrature(n: int) -> tuple[FloatArray, FloatArray]:
    nodes, weights = np.polynomial.hermite_e.hermegauss(n)
    return nodes, weights / weights.sum()


@dataclass
class HarFit:
    """Log-HAR coefficients and the spread of its forecast errors (fitted on training data)."""

    coef: FloatArray
    resid_std: float


_EPS = 1e-12


def _har_design(f: feat.VolFeatures, idx: NDArray[np.int64]) -> FloatArray:
    def lg(x: FloatArray) -> FloatArray:
        return np.log(np.maximum(x, _EPS))

    return np.column_stack(
        [np.ones(idx.size), lg(f.rv1d_var[idx]), lg(f.rv7d_var[idx]), lg(f.rv30d_var[idx])]
    )


def _har_log_median(fit: HarFit, f: feat.VolFeatures, idx: NDArray[np.int64]) -> FloatArray:
    return np.asarray(_har_design(f, idx) @ fit.coef, dtype=float)


def fit_har(
    grid: HourlyGrid, f: feat.VolFeatures, horizon_days: int, cutoff: int, step: int = 24
) -> HarFit:
    """Fit log-HAR on anchors whose whole forecast window ended before ``cutoff`` (the purge)."""
    hours = 24 * horizon_days
    idx = np.arange(30 * 24, cutoff - hours + 1, step)
    idx = idx[np.isfinite(f.rv30d_var[idx])]
    csum = np.concatenate([[0.0], np.cumsum(grid.rv)])
    target = np.log(np.maximum((csum[idx + hours] - csum[idx]) / horizon_days, _EPS))
    x = _har_design(f, idx)
    coef, *_ = np.linalg.lstsq(x, target, rcond=None)
    return HarFit(coef, float(np.std(target - x @ coef)))


def _sigma_from_daily_var(var_day: FloatArray) -> FloatArray:
    return np.asarray(np.sqrt(var_day * 365.0), dtype=float)


def _mixture(u: dict[str, FloatArray], sigmas: FloatArray, weights: FloatArray) -> FloatArray:
    """Average the closed form over a set of volatility scenarios (rows = contracts)."""
    out = np.zeros(sigmas.shape[0])
    for j in range(sigmas.shape[1]):
        out += weights[j] * _touch(u, sigmas[:, j])
    return out


def _har_probabilities(
    us: dict[str, FloatArray],
    idx: NDArray[np.int64],
    f: feat.VolFeatures,
    har: dict[int, HarFit],
    nodes: FloatArray,
    qw: FloatArray,
) -> tuple[FloatArray, FloatArray]:
    """HAR plug-in probability, and the version that mixes over volatility-forecast error.

    Log-HAR gives a *distribution* for the variance over the contract's life: log-normal with
    the median from the regression and the spread measured on the training window. The plug-in
    uses the mean of that distribution as if it were certain. The mixture averages the barrier
    formula over the whole distribution, which fattens the tails (Jensen's inequality).
    """
    d_col = us["horizon_d"]
    log_med = np.empty(d_col.size)
    spread = np.empty(d_col.size)
    for d, fit in har.items():
        sel = d_col == d
        log_med[sel] = _har_log_median(fit, f, idx[sel])
        spread[sel] = fit.resid_std
    mean_var = np.exp(log_med + 0.5 * spread**2)
    plain = _touch(us, _sigma_from_daily_var(mean_var))
    scenarios = np.exp(log_med[:, None] + spread[:, None] * nodes[None, :])
    return plain, _mixture(us, _sigma_from_daily_var(scenarios), qw)


# --- The walk-forward loop ------------------------------------------------------------------


def _year_of(grid: HourlyGrid, idx: FloatArray) -> NDArray[np.int64]:
    stamps = grid.timestamp(idx.astype(np.int64)).astype("datetime64[Y]")
    return np.asarray(stamps.astype(int) + 1970, dtype=np.int64)


def _cutoff_index(grid: HourlyGrid, year: int) -> int:
    return int((np.datetime64(f"{year}-01-01T00", "h") - grid.t0) / np.timedelta64(1, "h"))


def run_backtest(grid: HourlyGrid, cfg: BacktestConfig) -> pl.DataFrame:
    f = feat.build_features(grid, cfg.ewma_half_life_days, cfg.bayes_memory_days)
    u = build_universe(grid, f, cfg)
    n_rows = u["anchor"].size
    years = _year_of(grid, u["anchor"])
    anchor_i = u["anchor"].astype(np.int64)
    label = u["label"]
    nodes, qw = _quadrature(cfg.n_quadrature)
    probs = {m: np.full(n_rows, np.nan) for m in MODELS}

    for year in range(cfg.first_test_year, cfg.end_year + 1):
        cutoff = _cutoff_index(grid, year)
        test = years == year
        train = u["resolve"] < cutoff  # purge: outcome already known on the first day of the year
        if not test.any() or train.sum() < 1000:
            continue

        # Per-horizon fits, using training information only.
        har = {d: fit_har(grid, f, d, cutoff) for d in cfg.horizons_days}

        def sub(mask: NDArray[np.bool_]) -> dict[str, FloatArray]:
            return {k: v[mask] for k, v in u.items()}

        def har_models(
            mask: NDArray[np.bool_], fits: dict[int, HarFit] = har
        ) -> tuple[FloatArray, FloatArray]:
            return _har_probabilities(sub(mask), anchor_i[mask], f, fits, nodes, qw)

        # Recalibration: logistic map on logit(p) fitted on training contracts, per horizon.
        _, mix_train = har_models(train)
        recal = {}
        for d in cfg.horizons_days:
            sel = u["horizon_d"][train] == d
            recal[d] = scoring.calibration_slope_intercept(mix_train[sel], label[train][sel])

        # Base rates by (horizon, direction, z) from the training window.
        rate = {}
        for d in cfg.horizons_days:
            for direction in (1.0, -1.0):
                for z in cfg.z_grid:
                    sel = (
                        train
                        & (u["horizon_d"] == d)
                        & (u["direction"] == direction)
                        & (u["z"] == z)
                    )
                    rate[(d, direction, z)] = float(label[sel].mean()) if sel.any() else np.nan

        us = sub(test)
        idx = anchor_i[test]
        probs["naive_2x"][test] = _naive_2x(us)
        probs["gbm_trailing30"][test] = _touch(us, us["sigma_ref"])
        probs["gbm_rv7"][test] = _touch(us, _sigma_from_daily_var(f.rv7d_var[idx]))
        probs["gbm_ewma"][test] = _touch(us, f.ewma_vol[idx])
        plain, mixed = har_models(test)
        probs["gbm_har"][test] = plain
        probs["har_mix"][test] = mixed

        # Bayesian discounted belief: posterior predictive by quantile quadrature.
        a, b = f.bayes_alpha[idx], f.bayes_beta[idx]
        q = (np.arange(cfg.n_quadrature) + 0.5) / cfg.n_quadrature
        var_h = invgamma.ppf(q[None, :], a[:, None], scale=b[:, None])
        probs["bayes_disc"][test] = _mixture(
            us, np.sqrt(var_h * HOURS_PER_YEAR), np.full(cfg.n_quadrature, 1.0 / cfg.n_quadrature)
        )

        logit = np.log(np.clip(mixed, 1e-6, 1 - 1e-6) / (1 - np.clip(mixed, 1e-6, 1 - 1e-6)))
        recal_p = np.empty_like(mixed)
        for d, (a0, b0) in recal.items():
            sel = us["horizon_d"] == d
            recal_p[sel] = 1.0 / (1.0 + np.exp(-(a0 + b0 * logit[sel])))
        probs["har_mix_recal"][test] = recal_p
        probs["base_rate"][test] = [
            rate[(int(d), dr, z)]
            for d, dr, z in zip(us["horizon_d"], us["direction"], us["z"], strict=True)
        ]

    keep = ~np.isnan(probs["naive_2x"])
    data: dict[str, Any] = {k: v[keep] for k, v in u.items()}
    data["year"] = years[keep]
    data["week"] = (u["anchor"][keep] // (24 * 7)).astype(np.int64)
    for m, p in probs.items():
        data[m] = p[keep]
    return pl.DataFrame(data)


# --- Summaries ------------------------------------------------------------------------------


def score_table(df: pl.DataFrame, by: list[str] | None = None) -> pl.DataFrame:
    """Log loss, Brier, Brier skill vs the naive rule, calibration slope, per model."""
    groups = df.partition_by(by, as_dict=True) if by else {(): df}
    rows = []
    for key, g in groups.items():
        y = g["label"].to_numpy()
        naive_brier = scoring.brier(g["naive_2x"].to_numpy(), y)
        for m in MODELS:
            p = g[m].to_numpy()
            _, slope = scoring.calibration_slope_intercept(p, y)
            row = {
                "model": m,
                "n": g.height,
                "log_loss": scoring.log_loss(p, y),
                "brier": scoring.brier(p, y),
                "brier_skill_vs_naive": scoring.skill_score(scoring.brier(p, y), naive_brier),
                "calibration_slope": slope,
            }
            if by:
                row.update(dict(zip(by, key, strict=True)))
            rows.append(row)
    return pl.DataFrame(rows)


def loss_difference_table(df: pl.DataFrame, baseline: str) -> pl.DataFrame:
    """Mean log-loss difference vs ``baseline`` with a week-clustered bootstrap interval."""
    y = df["label"].to_numpy()
    base = scoring.log_loss_each(df[baseline].to_numpy(), y)
    rows = []
    for m in MODELS:
        if m == baseline:
            continue
        diff, lo, hi = scoring.cluster_bootstrap_difference(
            scoring.log_loss_each(df[m].to_numpy(), y), base, df["week"].to_numpy()
        )
        rows.append(
            {"model": m, "vs": baseline, "log_loss_diff": diff, "ci_low": lo, "ci_high": hi}
        )
    return pl.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(prog="pmq.crypto.backtest")
    parser.add_argument("--config", default="config/btc.yaml")
    parser.add_argument("--out", default="outputs")
    args = parser.parse_args()
    cfg = load_config(args.config)
    settings = get_settings()
    cache = settings.bars_dir / f"{cfg.asset}_1m.parquet"
    if not cache.exists():
        ticks.build_bar_cache(settings.ticks_dir / f"{cfg.asset}USD.csv", cache)
    grid = build_hourly_grid(ticks.load_bars(cache), start=cfg.start)
    df = run_backtest(grid, cfg)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    df.write_parquet(out / f"backtest_{cfg.asset}.parquet")
    print(score_table(df).sort("log_loss"))
    print(loss_difference_table(df, "naive_2x"))


if __name__ == "__main__":
    main()

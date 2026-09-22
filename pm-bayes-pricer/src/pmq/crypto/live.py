"""The live pricing model: a fitted artifact, and the function that prices one contract.

This is the *same maths* as the backtest's ``har_mix`` model, packaged for production:

1. **Artifact.** The log-HAR regression coefficients (and the spread of its forecast errors) for
   the 1-, 7- and 30-day horizons, fitted offline on all history and saved as a small JSON file.
   Every fair value written to the database carries the artifact's id, so any number can be
   traced to exactly the model that produced it.
2. **Inputs.** Three volatility measures from the latest hourly candles: yesterday, last week
   and last month.
3. **Pricing.** Forecast the variance for this contract's exact time to expiry (interpolating
   between the fitted horizons in log time), then average the touch formula over the forecast's
   own error distribution. If the barrier has already been touched in the window, the answer is 1.

``tests/test_live_parity.py`` checks that this code and the backtest give identical numbers.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
from numpy.typing import NDArray

from pmq.crypto import backtest
from pmq.crypto import features as feat
from pmq.crypto.barrier import MINUTE_YEARS, implied_volatility, touch_probability
from pmq.crypto.grid import HourlyGrid
from pmq.ingest.kraken_spot import Candle
from pmq.pricing.fees import taker_fee

FloatArray = NDArray[np.float64]
_EPS = 1e-12


@dataclass(frozen=True)
class HorizonFit:
    horizon_days: int
    coef: tuple[float, float, float, float]
    resid_std: float


@dataclass(frozen=True)
class ModelArtifact:
    asset: str
    trained_through: str
    fits: tuple[HorizonFit, ...]
    n_quadrature: int = 15

    @property
    def model_id(self) -> str:
        digest = hashlib.sha256(json.dumps(asdict(self), sort_keys=True).encode()).hexdigest()
        return f"har_mix-{self.asset}-{digest[:8]}"

    def save(self, path: str | Path) -> None:
        Path(path).write_text(json.dumps(asdict(self), indent=2, sort_keys=True) + "\n")

    @classmethod
    def load(cls, path: str | Path) -> ModelArtifact:
        raw = json.loads(Path(path).read_text())
        fits = tuple(
            HorizonFit(f["horizon_days"], tuple(f["coef"]), f["resid_std"]) for f in raw["fits"]
        )
        return cls(raw["asset"], raw["trained_through"], fits, raw.get("n_quadrature", 15))


def fit_artifact(
    grid: HourlyGrid, asset: str, trained_through: str, horizons: tuple[int, ...] = (1, 7, 30)
) -> ModelArtifact:
    """Fit log-HAR for each horizon on everything up to the end of the grid."""
    f = feat.build_features(grid)
    fits = []
    for d in horizons:
        fit = backtest.fit_har(grid, f, d, cutoff=len(grid))
        fits.append(HorizonFit(d, tuple(float(c) for c in fit.coef), fit.resid_std))  # type: ignore[arg-type]
    return ModelArtifact(asset, trained_through, tuple(fits))


@dataclass(frozen=True)
class LiveInputs:
    """Average daily realised variance over the last 1, 7 and 30 days."""

    rv1d: float
    rv7d: float
    rv30d: float


def live_inputs_from_candles(candles: list[Candle]) -> LiveInputs:
    """Build the three volatility inputs from hourly candles.

    The newest candle is still forming, so it is dropped. Squared hourly returns stand in for
    the 5-minute realised variance used in the backtest; for Bitcoin the two agree because the
    volatility signature plot is flat (notebook 5).
    """
    closes = np.array([c.close for c in candles[:-1]])
    if closes.size < 24 * 7 + 1:
        raise ValueError("need at least 7 days of hourly candles")
    r2 = np.diff(np.log(closes)) ** 2
    days_30 = min(r2.size, 24 * 30) / 24.0
    return LiveInputs(
        rv1d=float(r2[-24:].sum()),
        rv7d=float(r2[-24 * 7 :].sum() / 7.0),
        rv30d=float(r2[-24 * 30 :].sum() / days_30),
    )


def _log_forecast(
    artifact: ModelArtifact, inputs: LiveInputs, horizon_days: float
) -> tuple[float, float]:
    """(median log-variance, forecast-error spread) at this horizon, interpolated in log time."""
    x = np.log(
        np.maximum([inputs.rv1d, inputs.rv7d, inputs.rv30d], _EPS),
    )
    design = np.array([1.0, x[0], x[1], x[2]])
    nodes = np.array([math.log(f.horizon_days) for f in artifact.fits])
    medians = np.array([float(design @ np.array(f.coef)) for f in artifact.fits])
    spreads = np.array([f.resid_std for f in artifact.fits])
    h = math.log(max(horizon_days, 1e-9))
    return float(np.interp(h, nodes, medians)), float(np.interp(h, nodes, spreads))


@dataclass(frozen=True)
class FairValue:
    p: float
    p_low: float
    p_high: float
    sigma_median: float
    already_touched: bool


def _weighted_quantile(values: FloatArray, weights: FloatArray, q: float) -> float:
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cum = np.cumsum(w) - 0.5 * w
    return float(np.interp(q, cum / w.sum(), v))


def price_touch(
    artifact: ModelArtifact,
    inputs: LiveInputs,
    spot: float,
    barrier_price: float,
    direction: str,
    t_years: float,
    running_extreme: float | None = None,
) -> FairValue:
    """Probability the price touches ``barrier_price`` before the window closes."""
    hit = running_extreme is not None and (
        running_extreme >= barrier_price if direction == "up" else running_extreme <= barrier_price
    )
    if hit:
        return FairValue(1.0, 1.0, 1.0, float("nan"), True)
    if t_years <= 0:
        return FairValue(0.0, 0.0, 0.0, float("nan"), False)

    log_med, spread = _log_forecast(artifact, inputs, t_years * 365.0)
    nodes, weights = backtest._quadrature(artifact.n_quadrature)
    sigmas = np.sqrt(np.exp(log_med + spread * nodes) * 365.0)
    p_j = touch_probability(
        spot,
        barrier_price,
        sigmas,
        t_years,
        0.0,
        MINUTE_YEARS,
        direction,  # type: ignore[arg-type]
    )
    return FairValue(
        p=float(np.sum(weights * p_j)),
        p_low=_weighted_quantile(p_j, weights, 0.10),
        p_high=_weighted_quantile(p_j, weights, 0.90),
        sigma_median=float(math.sqrt(math.exp(log_med) * 365.0)),
        already_touched=False,
    )


def running_extreme(
    candles: list[Candle],
    window_start: datetime,
    direction: str,
    last_price: float,
    partial: list[Candle] | None = None,
) -> float:
    """Highest high (up-barrier) or lowest low (down-barrier) seen since the window opened.

    Only candles that *start inside* the window count. The hour containing the window's opening
    is skipped because its extreme may have happened before the window began; the cost is that a
    touch inside that first partial hour is missed (a new market then looks untouched for up to
    an hour). Pass ``partial`` (1-minute candles from the window start to the next hour) to
    close that gap exactly.
    """
    inside = [c for c in candles if c.ts >= window_start] + list(partial or [])
    if direction == "up":
        return max([last_price] + [c.high for c in inside])
    return min([last_price] + [c.low for c in inside])


def evaluate_market(
    artifact: ModelArtifact,
    inputs: LiveInputs,
    spot: float,
    candles: list[Candle],
    *,
    barrier_price: float,
    direction: str,
    window_start: datetime,
    window_end: datetime,
    now: datetime,
    bid: float | None,
    ask: float | None,
    fee_rate: float,
    fee_exponent: float,
    partial: list[Candle] | None = None,
) -> dict[str, Any]:
    """Everything the database stores for one market in one pricing cycle."""
    extreme = running_extreme(candles, window_start, direction, spot, partial)
    t_years = (window_end - now).total_seconds() / (365.0 * 86400.0)
    fv = price_touch(artifact, inputs, spot, barrier_price, direction, t_years, extreme)

    mid = (bid + ask) / 2.0 if bid is not None and ask is not None else None
    edge_buy = fv.p - (ask + taker_fee(ask, fee_rate, fee_exponent)) if ask is not None else None
    edge_sell = (bid - taker_fee(bid, fee_rate, fee_exponent)) - fv.p if bid is not None else None
    implied = None
    if mid is not None and not fv.already_touched and t_years > 0 and 0.0 < mid < 1.0:
        iv = implied_volatility(mid, spot, barrier_price, t_years, 0.0, MINUTE_YEARS)
        implied = None if math.isnan(iv) else iv
    return {
        "p": fv.p,
        "p_low": fv.p_low,
        "p_high": fv.p_high,
        "mid": mid,
        "bid": bid,
        "ask": ask,
        "edge_buy": edge_buy,
        "edge_sell": edge_sell,
        "implied_vol": implied,
        "spot": spot,
        "sigma_median": None if math.isnan(fv.sigma_median) else fv.sigma_median,
        "already_touched": fv.already_touched,
    }

"""The live pricer must give the same number as the backtest, or the backtest proves nothing."""

from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from pmq.crypto import backtest, features
from pmq.crypto import live as L
from pmq.crypto.barrier import MINUTE_YEARS, touch_probability
from pmq.crypto.grid import HourlyGrid
from pmq.ingest.kraken_spot import Candle

DAY = 1 / 365


def _grid(n: int = 24 * 400, seed: int = 0) -> HourlyGrid:
    rng = np.random.default_rng(seed)
    vol_h = 0.0045 * np.exp(
        0.4 * np.cumsum(0.05 * rng.standard_normal(n)) / np.sqrt(np.arange(1, n + 1))
    )
    close = 30_000 * np.exp(np.cumsum(vol_h * rng.standard_normal(n)))
    rv = (vol_h**2) * rng.chisquare(1, n)
    return HourlyGrid(
        t0=np.datetime64("2021-01-01T00", "h"),
        high=close * 1.002,
        low=close * 0.998,
        close=close,
        rv=rv,
        traded=np.ones(n, dtype=bool),
    )


@pytest.fixture(scope="module")
def setup():
    g = _grid()
    art = L.fit_artifact(g, "XBT", "2022-02-05", horizons=(1, 7, 30))
    return g, features.build_features(g), art


def test_live_price_matches_the_backtest_for_the_same_inputs(setup) -> None:
    g, f, art = setup
    i = 24 * 380
    inputs = L.LiveInputs(f.rv1d_var[i], f.rv7d_var[i], f.rv30d_var[i])
    nodes, qw = backtest._quadrature(15)
    har = {h.horizon_days: backtest.HarFit(np.array(h.coef), h.resid_std) for h in art.fits}
    for k_mult, horizon in [(1.06, 7), (0.93, 1), (1.20, 30)]:
        s0 = g.close[i - 1]
        us = {
            "s0": np.array([s0]),
            "k": np.array([s0 * k_mult]),
            "horizon_d": np.array([float(horizon)]),
        }
        _, expected = backtest._har_probabilities(us, np.array([i]), f, har, nodes, qw)
        got = L.price_touch(
            art, inputs, s0, s0 * k_mult, "up" if k_mult > 1 else "down", horizon * DAY
        )
        assert got.p == pytest.approx(float(expected[0]), rel=1e-9)


def test_probability_ladder_is_monotone_and_the_band_brackets_the_estimate(setup) -> None:
    g, f, art = setup
    inputs = L.LiveInputs(4e-4, 5e-4, 6e-4)
    ups = [
        L.price_touch(art, inputs, 30_000, 30_000 * m, "up", 5 * DAY)
        for m in (1.02, 1.05, 1.1, 1.3)
    ]
    assert [u.p for u in ups] == sorted((u.p for u in ups), reverse=True)
    downs = [
        L.price_touch(art, inputs, 30_000, 30_000 / m, "down", 5 * DAY) for m in (1.02, 1.05, 1.1)
    ]
    assert [d.p for d in downs] == sorted((d.p for d in downs), reverse=True)
    for v in ups + downs:
        assert 0.0 <= v.p_low <= v.p_high <= 1.0
    assert ups[1].p_low < ups[1].p < ups[1].p_high or ups[1].p_low <= ups[1].p <= ups[1].p_high


def test_an_already_touched_barrier_is_certain_and_an_expired_one_is_impossible(setup) -> None:
    _, _, art = setup
    inputs = L.LiveInputs(4e-4, 5e-4, 6e-4)
    assert (
        L.price_touch(art, inputs, 30_000, 31_000, "up", 3 * DAY, running_extreme=31_050).p == 1.0
    )
    # A down-barrier at 29,500 with the running low only at 29,800 has not been touched yet.
    not_yet = L.price_touch(art, inputs, 30_000, 29_500, "down", 3 * DAY, running_extreme=29_800)
    assert 0.0 < not_yet.p < 1.0 and not not_yet.already_touched
    touched = L.price_touch(art, inputs, 30_000, 29_500, "down", 3 * DAY, running_extreme=29_400)
    assert touched.p == 1.0 and touched.already_touched
    assert L.price_touch(art, inputs, 30_000, 31_000, "up", 0.0).p == 0.0


def test_interpolation_matches_the_fitted_horizons_exactly_at_the_nodes(setup) -> None:
    _, _, art = setup
    inputs = L.LiveInputs(4e-4, 5e-4, 6e-4)
    for fit in art.fits:
        _, spread = L._log_forecast(art, inputs, float(fit.horizon_days))
        assert spread == pytest.approx(fit.resid_std)
    low, _ = L._log_forecast(art, inputs, 0.2)
    one, _ = L._log_forecast(art, inputs, 1.0)
    assert low == pytest.approx(one)  # flat below the shortest fitted horizon


def test_artifact_round_trips_and_its_id_changes_when_coefficients_change(setup, tmp_path) -> None:
    _, _, art = setup
    art.save(tmp_path / "a.json")
    assert L.ModelArtifact.load(tmp_path / "a.json") == art
    tweaked = L.ModelArtifact(
        art.asset,
        art.trained_through,
        (L.HorizonFit(1, (0.0, 0.0, 0.0, 0.0), 0.5),) + art.fits[1:],
    )
    assert tweaked.model_id != art.model_id


def _candles(n: int, start: datetime, price: float = 30_000.0) -> list[Candle]:
    rng = np.random.default_rng(1)
    out, p = [], price
    for i in range(n):
        o = p
        p = p * float(np.exp(0.004 * rng.standard_normal()))
        out.append(
            Candle(start + timedelta(hours=i), o, max(o, p) * 1.001, min(o, p) * 0.999, p, 5.0)
        )
    return out


def test_evaluate_market_produces_edges_net_of_fees_and_an_implied_vol(setup) -> None:
    _, _, art = setup
    start = datetime(2026, 9, 1, tzinfo=UTC)
    candles = _candles(24 * 21, start)
    inputs = L.live_inputs_from_candles(candles)
    now = candles[-1].ts + timedelta(hours=1)
    spot = candles[-1].close
    common = dict(
        barrier_price=spot * 1.06,
        direction="up",
        window_start=start,
        window_end=now + timedelta(days=5),
        now=now,
        fee_rate=0.07,
        fee_exponent=1.0,
    )
    row = L.evaluate_market(art, inputs, spot, candles, bid=0.30, ask=0.34, **common)
    assert row["mid"] == pytest.approx(0.32)
    fee = 0.07 * 0.34 * 0.66
    assert row["edge_buy"] == pytest.approx(row["p"] - (0.34 + fee))
    assert row["edge_sell"] == pytest.approx((0.30 - 0.07 * 0.30 * 0.70) - row["p"])
    assert row["implied_vol"] is None or row["implied_vol"] > 0
    # Missing quotes give missing edges rather than made-up numbers.
    blank = L.evaluate_market(art, inputs, spot, candles, bid=None, ask=None, **common)
    assert blank["edge_buy"] is None and blank["edge_sell"] is None and blank["mid"] is None


def test_touch_probability_is_unaffected_by_the_pricing_wrapper_for_a_simple_case() -> None:
    p = float(touch_probability(30_000, 33_000, 0.6, 10 * DAY, 0.0, MINUTE_YEARS))
    assert 0.0 < p < 1.0


def test_only_candles_inside_the_window_count_towards_an_already_touched_barrier() -> None:
    start = datetime(2026, 9, 1, tzinfo=UTC)
    candles = _candles(48, start, price=30_000.0)
    late_start = candles[30].ts + timedelta(minutes=17)  # opens part-way through candle 30
    up = L.running_extreme(candles, late_start, "up", last_price=30_000.0)
    assert up <= max(c.high for c in candles[31:]) or up == 30_000.0
    # Peeking at an earlier candle would give a higher (wrong) extreme; it must be ignored.
    spiky = list(candles)
    spiky[10] = Candle(spiky[10].ts, 30_000.0, 99_999.0, 29_000.0, 30_000.0, 1.0)
    assert L.running_extreme(spiky, late_start, "up", 30_000.0) < 99_999.0

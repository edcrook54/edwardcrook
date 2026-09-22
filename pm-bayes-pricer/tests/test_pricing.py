import numpy as np
import pytest

from pmq.pricing import arb, clean, coherence, fees


def test_mid_price_prefers_tight_quotes_else_last_trade() -> None:
    assert clean.mid_price(0.40, 0.44, 0.30) == pytest.approx(0.42)
    assert clean.mid_price(0.01, 0.99, 0.30) == 0.30
    assert clean.mid_price(None, None, None) is None


@pytest.mark.parametrize(
    "method", [clean.normalise_proportional, clean.normalise_power, clean.normalise_shin]
)
def test_every_method_returns_a_proper_distribution(method) -> None:
    q = [0.0035, 0.0055, 0.435, 0.555, 0.0085]  # a real Polymarket quote set, adds to 1.0075
    p = method(q)
    assert p.sum() == pytest.approx(1.0)
    assert np.all(p >= 0)
    assert np.all(p <= np.asarray(q) + 1e-12)  # removing overround only ever lowers a price


def test_power_and_shin_take_more_from_longshots_than_proportional() -> None:
    q = np.array([0.02, 0.48, 0.55])
    prop_ratio = clean.normalise_proportional(q) / q
    for method in (clean.normalise_power, clean.normalise_shin):
        ratio = method(q) / q
        assert ratio[0] < prop_ratio[0]  # longshot shaved harder
        assert ratio[2] > prop_ratio[2]  # favourite shaved less


def test_no_overround_means_no_change() -> None:
    q = [0.2, 0.3, 0.5]
    for method in (clean.normalise_proportional, clean.normalise_power, clean.normalise_shin):
        assert method(q) == pytest.approx(q)


def test_isotonic_repairs_a_ladder_with_minimum_movement() -> None:
    assert coherence.isotonic_decreasing([0.9, 0.5, 0.6, 0.1]).tolist() == pytest.approx(
        [0.9, 0.55, 0.55, 0.1]
    )
    already_ok = [0.9, 0.5, 0.1]
    assert coherence.isotonic_decreasing(already_ok).tolist() == pytest.approx(already_ok)


def test_isotonic_output_is_always_non_increasing() -> None:
    rng = np.random.default_rng(1)
    for _ in range(50):
        fitted = coherence.isotonic_decreasing(rng.random(12))
        assert coherence.ladder_violations(fitted) == 0


def test_ladder_bucket_round_trip() -> None:
    buckets = {-50: 0.01, -25: 0.04, 0: 0.5, 25: 0.4, 50: 0.05}
    ladder = coherence.buckets_to_ladder(buckets, current_upper_pct=4.00)
    assert ladder[3.50] == pytest.approx(0.99)  # P(new bound above 3.50%) = 1 - P(cut of 50+)
    assert ladder[3.75] == pytest.approx(0.95)  # ... = P(no cut at all)
    back = coherence.ladder_to_buckets(ladder, current_upper_pct=4.00)
    assert back == pytest.approx(buckets)


def test_ladder_with_a_stale_rung_never_gives_negative_buckets() -> None:
    ladder = {
        3.50: 0.99,
        3.75: 0.98,
        4.00: 0.30,
        4.25: 0.35,
        4.50: 0.01,
    }  # 4.25 rung priced above 4.00
    buckets = coherence.ladder_to_buckets(ladder, 4.00, bucket_bps=(-50, -25, 0, 25, 50))
    assert min(buckets.values()) >= 0
    assert sum(buckets.values()) == pytest.approx(1.0)


def test_kalshi_fee_matches_published_shape() -> None:
    assert fees.taker_fee(0.5) == pytest.approx(0.0175)
    assert fees.taker_fee(0.0) == 0 and fees.taker_fee(1.0) == 0
    assert fees.kalshi_fee_rounded(0.5, 100) == 1.75
    assert fees.kalshi_fee_rounded(0.5, 1) == 0.02  # 1.75 cents rounded UP to the cent


def test_dutch_book_needs_a_gap_larger_than_fees() -> None:
    assert arb.dutch_book_buy_all([0.30, 0.30, 0.30]) < 0.1  # 10c gross, fees eat some
    assert arb.dutch_book_buy_all([0.30, 0.30, 0.30]) > 0.0
    assert arb.dutch_book_buy_all([0.34, 0.34, 0.33]) < 0.0  # ~1c gross, fees kill it


def test_cross_venue_edge_is_the_gap_less_fees() -> None:
    assert arb.cross_venue_edge(0.40, 0.50) < 0.10
    assert arb.cross_venue_edge(0.50, 0.50) < 0

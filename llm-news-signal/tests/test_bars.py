import pandas as pd
import pytest

from llmsignal.returns.bars import event_time_et_to_utc, forward_return


def test_event_time_et_to_utc_handles_standard_time() -> None:
    # late January is EST (UTC-5), no daylight saving
    result = event_time_et_to_utc("2024-01-31", "14:00")

    assert result == pd.Timestamp("2024-01-31 19:00:00", tz="UTC")


def test_event_time_et_to_utc_handles_daylight_time() -> None:
    # mid-June is EDT (UTC-4), daylight saving in effect
    result = event_time_et_to_utc("2024-06-12", "14:00")

    assert result == pd.Timestamp("2024-06-12 18:00:00", tz="UTC")


def _make_bars(rows: list[tuple[str, float]]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "ts": [pd.Timestamp(t, tz="UTC") for t, _ in rows],
            "close": [p for _, p in rows],
        }
    )


def test_forward_return_matches_hand_worked_example() -> None:
    bars = _make_bars(
        [
            ("2024-01-31 18:59:00", 100.0),  # last bar strictly before the event
            ("2024-01-31 19:00:00", 101.0),  # the event-time bar itself - excluded from "before"
            ("2024-01-31 19:59:00", 108.0),
            ("2024-01-31 20:00:00", 110.0),  # last bar at/before event+1h
        ]
    )
    event_time = pd.Timestamp("2024-01-31 19:00:00", tz="UTC")

    result = forward_return(bars, event_time, horizon_hours=1)

    # before = price STRICTLY before the event = 100.0 (18:59 bar) - the
    # event-time bar's close reflects up to 59s of post-announcement
    # trading (bars are left-labeled), so it must not be used as "before".
    # after = price at/before event+1h (= 20:00 exactly) = 110.0
    assert result == pytest.approx((110.0 - 100.0) / 100.0)


def test_forward_return_excludes_the_event_time_bar_from_the_before_price() -> None:
    # Regression test for the look-ahead bug the project's own audit caught:
    # using "at or before" for the before-price let a bar spanning
    # [event_time, event_time+60s) - which includes post-announcement
    # trades - leak into the pre-event price.
    bars = _make_bars(
        [
            ("2024-01-31 18:59:00", 100.0),
            ("2024-01-31 19:00:00", 999.0),  # a large post-announcement move
            ("2024-01-31 20:00:00", 100.0),
        ]
    )
    event_time = pd.Timestamp("2024-01-31 19:00:00", tz="UTC")

    result = forward_return(bars, event_time, horizon_hours=1)

    # before must be 100.0 (18:59), never 999.0 (the event-time bar)
    assert result == pytest.approx((100.0 - 100.0) / 100.0)


def test_forward_return_is_none_when_horizon_exceeds_available_data() -> None:
    bars = _make_bars([("2024-01-31 19:00:00", 101.0)])
    event_time = pd.Timestamp("2024-01-31 19:00:00", tz="UTC")

    assert forward_return(bars, event_time, horizon_hours=24) is None


def test_forward_return_is_none_when_event_predates_all_data() -> None:
    bars = _make_bars([("2024-02-01 00:00:00", 101.0), ("2024-02-02 00:00:00", 105.0)])
    event_time = pd.Timestamp("2024-01-31 19:00:00", tz="UTC")

    assert forward_return(bars, event_time, horizon_hours=1) is None

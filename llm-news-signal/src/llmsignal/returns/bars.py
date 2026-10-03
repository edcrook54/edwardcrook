"""Joins an FOMC statement's release timestamp to the cached BTC/ETH 1-minute
bars (`pm-bayes-pricer/data/bars/*.parquet`) to compute real forward returns.

The bars are left-labeled: the row with `ts == T` spans `[T, T+60s)` and its
`close` is the last trade *within* that minute - i.e. up to 59 seconds after
`T`, not before it. Every FOMC release time here lands exactly on a minute
boundary (`event_time_et_to_utc` always produces "HH:MM:00"), so a naive
"last bar at-or-before" lookup for the "before" price would land on the
event-time bar itself and leak up to 59 seconds of post-announcement trading
into the pre-event price for every single observation - a real look-ahead
bug this project's own audit caught (see AUDIT.md). `price_before` therefore
uses a *strict* `<` cutoff (the last fully-completed bar strictly before the
event); `price_after` correctly keeps `<=`, since the "after" price is
allowed to be exactly the bar at the target time.
"""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

_ET = ZoneInfo("America/New_York")


def load_bars(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df = df.sort_values("ts").reset_index(drop=True)
    return df


def event_time_et_to_utc(date_str: str, time_str: str) -> pd.Timestamp:
    """`date_str` as "YYYY-MM-DD", `time_str` as "HH:MM" in US Eastern time."""
    local = pd.Timestamp(f"{date_str} {time_str}", tz=_ET)
    return local.tz_convert("UTC")


def _price_at_or_before(bars: pd.DataFrame, when: pd.Timestamp) -> float | None:
    eligible = bars.loc[bars["ts"] <= when]
    if eligible.empty:
        return None
    return float(eligible.iloc[-1]["close"])


def _price_strictly_before(bars: pd.DataFrame, when: pd.Timestamp) -> float | None:
    eligible = bars.loc[bars["ts"] < when]
    if eligible.empty:
        return None
    return float(eligible.iloc[-1]["close"])


def forward_return(
    bars: pd.DataFrame, event_time_utc: pd.Timestamp, horizon_hours: int
) -> float | None:
    """Simple (not log) return from the last bar at/before the event to the
    last bar at/before `event_time_utc + horizon_hours`. Returns None if
    either side falls outside the bars' coverage (e.g. an event too recent
    for a full horizon to have elapsed yet).
    """
    target_time = event_time_utc + pd.Timedelta(hours=horizon_hours)
    if target_time > bars["ts"].max():
        return None  # horizon extends past the end of available data - don't truncate silently

    price_before = _price_strictly_before(bars, event_time_utc)
    price_after = _price_at_or_before(bars, target_time)
    if price_before is None or price_after is None:
        return None
    return (price_after - price_before) / price_before

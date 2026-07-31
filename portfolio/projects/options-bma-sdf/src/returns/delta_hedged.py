"""Delta-hedged option return construction.

Implements the discrete delta-hedged gain (Bakshi & Kapadia, 2003), as used
in Käfer, Mörke, Weigert & Wiest (2026), eq. (5):

    Pi(t, t+tau) = C_{t+tau} - C_t
                   - sum_n Delta_{C,tn} * (S_{tn+1} - S_tn)
                   - sum_n a_n * r_n/365 * (C_tn - Delta_{C,tn} * S_tn)

where the option is hedged on a daily schedule between position initiation
and expiry/close.
"""
from __future__ import annotations

import pandas as pd


def delta_hedged_gain(
    option_prices: pd.Series,
    underlying_prices: pd.Series,
    deltas: pd.Series,
    risk_free_rate: pd.Series,
) -> float:
    """Compute the discrete delta-hedged gain over a hedging window.

    All input Series must share the same DatetimeIndex, one row per
    rehedging date (daily), from position initiation to close.

    TODO: implement eq. (5) — daily delta-hedging schedule, financing
    leg via the risk-free rate, calendar-day weighting for weekends/holidays.
    """
    raise NotImplementedError


def normalize_to_monthly_return(gain: float, delta0: float, s0: float, c0: float) -> float:
    """Divide the delta-hedged gain by the absolute value of the securities
    involved at initiation (Delta_t * S_t - C_t), per the paper's convention.
    """
    raise NotImplementedError

"""Trading fees, expressed per $1 contract.

Both venues charge takers a fee that is largest for 50/50 contracts and shrinks toward zero at
the extremes:

    fee per contract = rate * (p * (1 - p)) ** exponent

At p = 0.50 with Kalshi's rate this is 0.07 * 0.25 = 1.75 cents on a contract worth $1. That is
a big deal when the edge you hope to capture is only a few cents, which is why every edge and
backtest number in this project is quoted *after* fees.

The exact rate and exponent differ by venue and market, and venues change them. Polymarket
publishes them per market in a ``feeSchedule`` field, and Kalshi publishes a fee schedule.
Treat the defaults here as configuration to check against the venue's current documentation.
"""

from __future__ import annotations

import math

KALSHI_RATE = 0.07


def taker_fee(price: float, rate: float = KALSHI_RATE, exponent: float = 1.0) -> float:
    """Fee in dollars for taking one contract at ``price`` (a probability in [0, 1])."""
    if not 0.0 <= price <= 1.0:
        raise ValueError("price must be in [0, 1]")
    return float(rate * (price * (1.0 - price)) ** exponent)


def kalshi_fee_rounded(price: float, contracts: int) -> float:
    """Kalshi rounds the *total* fee for an order up to the next cent."""
    raw = KALSHI_RATE * contracts * price * (1.0 - price)
    return math.ceil(round(raw * 100, 9)) / 100


def cost_to_buy_yes(ask: float, rate: float = KALSHI_RATE, exponent: float = 1.0) -> float:
    """All-in dollars to buy one Yes contract at the ask, including the taker fee."""
    return ask + taker_fee(ask, rate, exponent)

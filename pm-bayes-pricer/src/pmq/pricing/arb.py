"""Mechanical mispricing checks (no forecasting needed).

Two situations lock in profit whatever happens:

* **Dutch book on one venue.** In a market where exactly one outcome will occur, buying one Yes
  contract on *every* outcome costs the sum of the asks and always pays $1. If the asks add to
  less than $1 (after fees) that is free money. The mirror image works on the bids.
* **Cross-venue.** If two venues offer the same yes/no contract, buy Yes where it is cheap and
  sell it (equivalently, buy No) where it is dear. Profit per contract is the gap between the
  higher bid and the lower ask, less fees.

The catch in real life is the phrase "the same contract". Venues word their resolution rules
differently, so a cross-venue gap can be a real difference in what is being bet on. Each
function here returns a number; a human (or a rules-matching table) decides whether it is safe.
"""

from __future__ import annotations

from collections.abc import Sequence

from pmq.pricing.fees import KALSHI_RATE, taker_fee


def dutch_book_buy_all(
    asks: Sequence[float], rate: float = KALSHI_RATE, exponent: float = 1.0
) -> float:
    """Guaranteed profit per full set from buying Yes on every outcome (negative = no arb)."""
    cost = sum(a + taker_fee(a, rate, exponent) for a in asks)
    return 1.0 - cost


def dutch_book_sell_all(
    bids: Sequence[float], rate: float = KALSHI_RATE, exponent: float = 1.0
) -> float:
    """Guaranteed profit per full set from selling Yes on every outcome (negative = no arb)."""
    proceeds = sum(b - taker_fee(b, rate, exponent) for b in bids)
    return proceeds - 1.0


def cross_venue_edge(
    ask_cheap: float,
    bid_dear: float,
    rate_cheap: float = KALSHI_RATE,
    rate_dear: float = KALSHI_RATE,
) -> float:
    """Profit per contract from buying Yes at ``ask_cheap`` and selling it at ``bid_dear``."""
    return (bid_dear - taker_fee(bid_dear, rate_dear)) - (
        ask_cheap + taker_fee(ask_cheap, rate_cheap)
    )

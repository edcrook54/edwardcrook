"""Venue-agnostic records that every scraper produces.

Polymarket and Kalshi describe the same thing in very different shapes. The scrapers translate
both into these two records so everything downstream (database, pricing, models) never needs to
know which venue a number came from.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Market(BaseModel):
    """One tradable yes/no contract.

    A multi-outcome event (e.g. "what will the Fed do?") is a set of these that share an
    ``event_key``. ``kind`` says how the set is laid out:

    * ``bucket``    - mutually exclusive outcomes that should sum to 100% (Polymarket style).
    * ``threshold`` - a ladder of "above X" contracts; probabilities fall as X rises (Kalshi style).
    """

    market_id: str
    venue: Literal["polymarket", "kalshi"]
    native_id: str
    event_key: str
    title: str
    outcome_label: str
    kind: Literal["bucket", "threshold", "touch"]
    bucket_bps: int | None = None
    strike_pct: float | None = None
    # Touch markets ("will BTC hit $X between two dates?"):
    barrier: float | None = None
    direction: Literal["up", "down"] | None = None
    window_start: datetime | None = None
    fee_rate: float | None = None
    fee_exponent: float | None = None
    resolution_rule: str | None = None
    close_time: datetime | None = None
    resolved_at: datetime | None = None
    resolved_yes: bool | None = None


class Snapshot(BaseModel):
    """The quoted prices of one contract at one moment. All prices are probabilities in [0, 1]."""

    market_id: str
    ts: datetime
    best_bid: float | None = Field(default=None, ge=0, le=1)
    best_ask: float | None = Field(default=None, ge=0, le=1)
    bid_size: float | None = None
    ask_size: float | None = None
    last_price: float | None = Field(default=None, ge=0, le=1)
    volume_24h: float | None = None

    @model_validator(mode="after")
    def _bid_not_above_ask(self) -> Snapshot:
        # A crossed book is a data error, not a trading opportunity; drop the quote side.
        if (
            self.best_bid is not None
            and self.best_ask is not None
            and self.best_bid > self.best_ask
        ):
            self.best_bid = self.best_ask = None
        return self

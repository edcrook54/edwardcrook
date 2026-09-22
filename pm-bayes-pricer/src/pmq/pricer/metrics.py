"""Prometheus metrics for the pricer: is it alive, is its data fresh, is the model still good?"""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram

CYCLES = Counter("pmq_pricer_cycles_total", "Pricing cycles run", ["status"])
CYCLE_SECONDS = Histogram("pmq_pricer_cycle_seconds", "Duration of a pricing cycle")
LAST_SUCCESS = Gauge("pmq_pricer_last_success_timestamp_seconds", "Unix time of last good cycle")
SPOT = Gauge("pmq_spot_price", "Latest spot price used by the model", ["asset"])
CANDLE_AGE = Gauge(
    "pmq_spot_candle_age_seconds", "Age of the newest completed hourly candle", ["asset"]
)
MARKETS_PRICED = Gauge("pmq_markets_priced", "Open markets priced in the last cycle")
MODEL_MARKET_GAP = Gauge("pmq_model_market_gap_mean_abs", "Mean |model p - market mid|")
BEST_EDGE_BUY = Gauge("pmq_edge_best_buy", "Largest edge from buying Yes, after fees")
BEST_EDGE_SELL = Gauge("pmq_edge_best_sell", "Largest edge from selling Yes, after fees")
SUSPICIOUS_EDGES = Gauge("pmq_suspicious_edges", "Markets whose |edge| exceeds the sanity cap")
SCORED_CONTRACTS = Gauge("pmq_scored_contracts", "Resolved contracts in the rolling score")
BRIER_MODEL = Gauge(
    "pmq_rolling_brier_model", "Rolling Brier score of the model, 1 day before close"
)
BRIER_MARKET = Gauge(
    "pmq_rolling_brier_market", "Rolling Brier score of the market mid, same contracts"
)
SPOT_BASIS_BPS = Gauge(
    "pmq_spot_basis_bps", "Binance price minus Kraken price, in basis points", ["asset"]
)

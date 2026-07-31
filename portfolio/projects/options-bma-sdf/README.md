# Bayesian SDF for Equity Options

Scoped replication of Käfer, Mörke, Weigert & Wiest (2026), *"A Bayesian
Stochastic Discount Factor for the Cross-Section of Individual Equity
Options,"* JFQA. Applies Bayesian model averaging (Bryzgalova, Huang &
Julliard, 2023) to price delta-hedged single-stock option returns.

**This is a scoped replication, not a full recreation** — the original
paper uses OptionMetrics/CRSP over 1996–2022 with 51 candidate factors.
This project uses a reduced universe, shorter window, and ~5 core factors
(IVRV, option momentum, jump risk, idiosyncratic volatility, embedded
leverage) to keep data costs sane while preserving the methodology.

## Pipeline

1. **Data** (`src/data/`) — pull ATM call option chains + underlying prices
2. **Returns** (`src/returns/`) — delta-hedged gain construction (Bakshi &
   Kapadia, 2003)
3. **Factors** (`src/factors/`) — decile portfolio sorts on characteristics
4. **BMA** (`src/bma/`) — spike-and-slab Gibbs sampler for the SDF
5. **Evaluation** (`src/evaluation/`) — RMSE / MAPE / R² vs. benchmark
   factor models, in- and out-of-sample

## Setup

```bash
uv sync --extra bma-sdf --extra dev
uv run pytest projects/options-bma-sdf/tests
uv run jupyter lab
```

## Data source

TBD — evaluating Polygon.io vs. CBOE DataShop for historical options
chains. See `notebooks/01_data_exploration.ipynb`.

## Status

🚧 Scaffolding stage — data source not yet finalised.

# Setup

No API keys are needed anywhere — Polymarket, Kalshi, Binance and Kraken are all public, read-only APIs.

## Install

```bash
cd pm-bayes-pricer
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
make install
```

`.env` ships with working local defaults. Only `PMQ_TICKS_DIR` (your Kraken tick CSVs) matters,
and only for rebuilding the research below.

## See it working without Docker

```bash
make price-now
```

Prices every open Polymarket "will Bitcoin hit $X?" contract right now. One line per contract,
e.g. `up 95,000 9.3d model 0.224 [0.051,0.426] mid 0.163 edge buy 0.052 ...`: the model gives a
22% chance of touching $95,000 (10th-90th percentile: 5%-43%), the market says 16%, and buying
Yes nets 5 points after fees *if the model is right*.

## Run the full stack

Needs Docker Desktop.

```bash
make up      # Postgres, collectors, pricer, Prometheus, Grafana; waits until healthy
make logs    # watch the Fed/Kalshi collector; Ctrl+C to stop watching (it keeps running)
```

Open Grafana at http://localhost:3000 (`admin` / `$GRAFANA_PASSWORD`, default `admin`) for the
live pricer dashboard and the backtest research dashboard shown in the main README. Prometheus is
at http://localhost:9090. Stop with `make down` (data kept); `docker compose down -v` deletes it.

Inspect the database directly with `make psql`:

```sql
SELECT count(*), max(ts) FROM core.market_snapshot;   -- how much has been collected, and how recent
```

## Notebooks

```bash
make notebooks
```

Read 1-9 in order (listed in the main README). 5-8 need the Kraken tick data to *re-run*; notebook
9 re-runs from its own small committed snapshot. All render fine without any of it.

## Rebuild the research (needs the Kraken tick files)

```bash
make bars          # ticks -> 1-minute bars, ~6s/coin; files are read, never modified
make backtest      # walk-forward backtest for BTC/ETH/SOL -> outputs/
make load-scores   # load those results into Postgres, for the Grafana research dashboard
make train         # refit the shipped model artifact in models/
```

## Checks

```bash
make lint typecheck test
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| `make up`: port 5432 in use | Another Postgres is running; stop it or change the host port in `docker-compose.yml`. |
| Collector logs `fetch failed` | A venue was briefly unreachable; it retries next cycle. |
| Pricer logs `spot candles are ... old; not pricing` | Binance was unreachable for hours — the staleness guard working as intended. |
| Dashboard shows "suspicious edges" > 0 | An edge exceeds the sanity cap (25 points) — check resolution rules and the Kraken/Binance basis panel before trusting it. |
| `make install` fails on `psycopg` | `python -m pip install --upgrade pip`, then retry. |
| Notebooks can't import `pmq` | Launch Jupyter from the venv you ran `make install` in. |

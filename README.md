# Ed Crook

I work in flow dealing, and pricing and hedging FX/crypto flow got
me interested in market microstructure,
order flow, and whether a signal actually survives real trading costs.
This repo is my showcase of library knowledge, project architecture and data visualisation (along with the obvious - models and outcomes) for building out these projects.

## What's in here

### [crypto-cointegration-signal](./crypto-cointegration-signal)

A stat-arb research pipeline built end to end on crypto tick data: raw
Kraken exports → dollar bars → a Kalman-filtered hedge ratio →
walk-forward, cost-adjusted backtest → a self-audit pass before calling
it finished.

The result is reported honestly rather than polished up: the traded pair
is only modestly profitable out-of-sample and loses money in-sample, and
the README says so up front. The audit step (see
[`AUDIT.md`](./crypto-cointegration-signal/AUDIT.md)) caught two real
bugs that had been flattering the original numbers — a seed-reuse bug and
a look-ahead leak — before this version existed.

## Skills this repo is meant to show

- **Time-series / quant methods**: dollar bars (volume-clock sampling
  instead of calendar-clock), Engle-Granger cointegration scanned across
  many random windows rather than one fixed window, Kalman-filtered
  time-varying hedge ratios, proper walk-forward train/test splits.
- **Honest statistics**: unit-root checks on cointegration test inputs,
  reporting distributions of p-values instead of a single pass/fail,
  flagging multiple-comparison risk instead of ignoring it.
- **Software structure**: a real `src/` layout — data loading, bar
  construction, alignment, signals, backtest, evaluation kept as separate,
  testable modules, not one big notebook.
- **Cost-aware backtesting**: every reported number is net of a stated
  transaction cost assumption rather than a gross return.
- **Self-auditing workflow**: four independent review checks (statistical
  validity, AFML methodology, chart honesty, narrative honesty) run
  against the finished project specifically to catch mistakes before
  calling it done, rather than a single self-review pass.

More projects will be added here over time.

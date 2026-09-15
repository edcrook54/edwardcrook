# Ed Crook

I work in trading and got pulled into the crypto side of things — pricing
and hedging FX/crypto flow during the day got me curious about what's
actually going on underneath: market microstructure, order flow, how a
signal survives contact with real costs. This repo is where that curiosity
turns into actual code instead of just opinions.

## What's in here

### [crypto-cointegration-signal](./crypto-cointegration-signal)

A full stat-arb research pipeline, start to finish, on crypto tick data:
raw Kraken exports → dollar bars → a Kalman-filtered hedge ratio →
walk-forward, cost-adjusted backtest → a self-audit pass before calling it
done.

It's deliberately not a highlight reel. The pair that gets traded is only
modestly profitable out-of-sample and loses money in-sample, and the
README says so up front rather than burying it. The audit step (see
[`AUDIT.md`](./crypto-cointegration-signal/AUDIT.md)) actually caught two
bugs that were quietly flattering the original numbers — a seed-reuse bug
and a look-ahead leak — before this version existed.

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
  transaction cost assumption, not a gross-return number dressed up.
- **Self-auditing workflow**: four independent review checks (statistical
  validity, AFML methodology, chart honesty, narrative honesty) run
  against the finished project specifically to catch my own mistakes
  before calling it done, rather than one self-congratulatory pass.

More will land here as I build it — this is a working repo, not a
one-off showcase.

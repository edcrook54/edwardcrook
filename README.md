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

### [pm-bayes-pricer](./pm-bayes-pricer)

Bayesian first-passage pricing for crypto "will it touch $X" prediction-market contracts, built on
92M Kraken ticks: closed-form and simulated touch probabilities, volatility forecasting plus a
Bayesian belief over it, a purged walk-forward backtest, and a live paper-trading pricer against
Polymarket with Postgres, Prometheus and Grafana behind it.

Same honesty rule applies: a log-HAR volatility forecast averaged over its own uncertainty beats a
naive rule of thumb on Bitcoin and Ethereum out-of-sample, is inconclusive for Solana (too little
data yet), and is a wash in the calmest test year — stated plainly rather than smoothed over. Every
formula is derived from scratch across nine notebooks and checked against Monte Carlo simulation
in the test suite.

### [trading-research-rag](./trading-research-rag)

A hybrid BM25 + LSA retrieval service built over this repo's own quant-research
corpus (both projects above) — built and CI-gated as a production service, not a
chatbot demo: from-scratch BM25 and reciprocal-rank-fusion, a two-tier eval set
(hand-labeled + bootstrapped) with bootstrap confidence intervals, and a real
regression gate in CI.

Same honesty rule applies: the headline finding is that plain BM25 beats the
hybrid approach on this corpus, confirmed by a committed, re-runnable parameter
sweep rather than asserted once. The project's own audit (see
[`AUDIT.md`](./trading-research-rag/AUDIT.md)) caught several real bugs before
this version existed — a chunk-id collision across projects, a stale-index bug
where the live service wouldn't pick up a rebuilt index without a restart, and a
mis-chunking bug where a code-fence comment was misread as a markdown header and
actually corrupted citations in the real corpus.

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
- **AI/retrieval engineering**: from-scratch BM25 and reciprocal rank fusion,
  an IR eval methodology (Recall@k/MRR/nDCG with bootstrap CIs) with gold
  labels built independently of the system under test, a CI regression gate
  on retrieval quality, and the same four-checker audit pattern retargeted at
  this project's own failure modes (retrieval validity, production
  robustness, citation provenance).

## Tools I use

- [ponytail](https://github.com/dietrichgebert/ponytail) — an AI coding-agent
  skill that pushes agents to write the minimum code necessary before
  reaching for a new implementation.

More projects will be added here over time.

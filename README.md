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

### [llm-news-signal](./llm-news-signal)

Does an LLM-extracted hawkish/dovish score from real FOMC statement text carry
predictive power for BTC/ETH forward returns — tested with the same
walk-forward, cost-adjusted, multiple-comparison-aware rigor as
`crypto-cointegration-signal`? The LLM is used once as a feature extractor, not
an agent: its reliability as a labeler (Cohen's kappa against 38 independent
hand labels) is validated and enforced as a gate before any downstream claim is
trusted.

**Headline result: pending** — this needs a live Anthropic API call this
environment didn't have a key for. Rather than fake a result, the full
pipeline (38 real FOMC statements compiled verbatim from federalreserve.gov,
EST/EDT-correct event timing, Newey-West rank-IC, Benjamini-Hochberg correction
across all 6 asset×horizon tests, cost-adjusted backtest) is built, tested, and
audited against a placeholder signal instead, and says so plainly. The audit
(see [`AUDIT.md`](./llm-news-signal/AUDIT.md)) caught a real look-ahead bug
(a bar-labeling edge case that leaked up to 59 seconds of post-announcement
trading into the "before" price for every single event) and a real
cost-accounting bug (a vendored cost model wrongly assumed consecutive bets
were one continuously-held position) before this version existed.

### [trading-desk-agent](./trading-desk-agent)

A tool-using research-desk agent over this repo's own quant projects — answers
open-ended questions by actually calling real tools (retrieval, statistical
tests, a sandboxed backtest re-run, restricted file reads) and cites exactly
where every claim came from. Includes a live multi-agent audit-dispatch mode
that productionizes this repo's own project-audit pattern (the one described
above, used to catch real bugs in every other project here) as real
orchestrated code, not just Claude Code instructions.

**Live-agent result: pending**, same honesty rule as `llm-news-signal` — both
the agent loop and the audit-dispatch mode need real API calls this
environment didn't have a key for. What's real right now: all four tools
(including a genuine subprocess call to `pm-bayes-pricer`'s actual backtest CLI
against its real cached data), the bounded tool-use loop's control flow against
a scripted client, and the async multi-checker dispatch's genuine concurrency
(verified by timing). The project's own audit (see
[`AUDIT.md`](./trading-desk-agent/AUDIT.md)) caught a citation-precision metric
that falsely flagged correctly-cited sources ending a sentence, and found that
8 of its 16 gold eval questions expected a tool to find content it was never
actually indexed to reach — both fixed and re-verified before this version
existed.

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
- **LLM-as-labeler validation**: treating an LLM's extracted score as a noisy
  labeler whose reliability (Cohen's kappa, Pearson correlation against
  independent human labels) must clear a stated threshold before being
  trusted in any downstream statistic, enforced as a code-level gate rather
  than a separate step that could be skipped — and refusing to fabricate a
  headline result when the real data dependency (a live API key) wasn't
  available, rather than quietly faking one.
- **Agent engineering**: a bounded tool-use loop built on the raw Anthropic API
  (no framework), four sandboxed tools (subprocess, HTTP, and filesystem access
  each with an enforced allowlist/timeout/path-traversal guard), a live
  multi-agent audit-dispatch mode using genuine `asyncio` concurrency, and an
  eval harness whose metrics (citation precision, tool-usage recall) are
  deliberately scoped to what's mechanically checkable without an unvalidated
  LLM-as-judge.

## Tools I use

- [ponytail](https://github.com/dietrichgebert/ponytail) — an AI coding-agent
  skill that pushes agents to write the minimum code necessary before
  reaching for a new implementation.

More projects will be added here over time.

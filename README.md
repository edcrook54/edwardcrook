# Ed Crook

Trading and Operations graduate at IG Group (FTSE 100 fintech), having
rotated across the Flow (FX & Crypto) Dealing desk and the Consumer AI
team. On the dealing desk I price and build fair value models while
managing the expiry of institutional positions and hedging risk
accordingly — a process that has driven an interest in the microstructure
of crypto markets and the mechanics of algorithmic market making. In the
Consumer AI team, I won a division-wide delivery award (5 of 500) for
transforming AI adoption across Trading & Operations: replacing an
entirely SQL–Excel–pivot table–deck analytical framework with a fully
MCP-based, natural-language-first architecture built on shared Claude
Code infrastructure. Both rotations have given me technical coding and
software knowledge alongside market exposure, drawing me toward
technical, algorithmic trading roles.

This repository is where that interest turns into code: independent
research projects built to be read end-to-end, not just run.

## Featured project

### [crypto-cointegration-signal](./crypto-cointegration-signal)

A research-note-style walkthrough of building a cointegration-based pairs
trading signal on crypto tick data — from raw Kraken exports, through
dollar bars, a Kalman-filtered hedge ratio, and a walk-forward,
cost-adjusted, out-of-sample backtest, to a self-audit stage that
independently checks the statistics, the AFML methodology, the charts and
the narrative before calling it done.

It reports an honest, unflattering result on purpose: the traded pair is
only modestly profitable out-of-sample and loses money in-sample, and
that's stated plainly rather than smoothed over. The audit process itself
caught two real bugs that had been quietly flattering the original
numbers — see [`AUDIT.md`](./crypto-cointegration-signal/AUDIT.md) for the
full trail.

## Professional experience

**IG Group (FTSE 100 Fintech) — Trading & Operations Graduate Analyst**
*Sep 2025 – Present*

**Flow (FX & Cryptocurrency) Dealing** — Graduate Rotation · 2026–Present
- Priced and built fair value models for FX and crypto instruments,
  supporting institutional client flow and intraday risk decisions.
- Responsible for expiring and rolling institutional positions with daily
  notional exposure in the ten figures, hedging residual risk using swaps
  and spot/forward instruments.
- Developed hands-on intuition for crypto market microstructure, order
  flow dynamics, and liquidity provision — forming the basis of the
  ongoing cointegration research above.

**Consumer AI** — Graduate Rotation · 2025–2026
- Won the Trading & Operations division-wide delivery award — one of five
  recipients from a 500-person division — for transforming AI adoption
  across the function.
- Designed and deployed shared Claude Code architecture enabling
  MCP-based, natural-language-first analytics, replacing a legacy
  SQL–Excel–pivot table–deck workflow across the entire division.
- Applied Python and XGBoost to build clustering models for client
  segmentation analysis of trade behaviour.

## Technical skills

- **Programming & data manipulation:** OOP-style Python (pandas, polars,
  numpy, scikit-learn — k-means and XGBoost, seaborn), SQL
- **Data platforms:** Google Cloud Platform (GCP), BigQuery, Looker, LookML
- **Business tools:** Advanced Excel, PowerPoint
- **Languages:** English (native), French (business proficient)

## Education

- **University of Nottingham** (2020–2025) — BSc Economics, Upper Second
  Class (68%)
- **RGS Guildford** (2015–2020) — A Levels: Mathematics and French (A\*),
  Further Mathematics and Economics (A)

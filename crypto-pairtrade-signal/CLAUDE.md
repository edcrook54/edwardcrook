# Project brief for Claude Code

## What this is

A portfolio project demonstrating cross-asset cointegration signal research
on crypto tick data, built to showcase quant research + engineering ability
for algo trading / market-making roles in digital assets (Wintermute-style
employer). It will go on a public GitHub repo linked from the author's
LinkedIn. This particular repo is being built on a tight timeline (roughly
two days), in response to a live job posting. Prioritise a small number
of things that actually work end-to-end over a large number of half-built
things.

The author is technically strong in Python and has domain knowledge of
market microstructure and spreads from their day job, but is newer to
formal cointegration/stat-arb methodology and to C++ (a separate, longer
project). Explanations in code comments and notebook markdown should
assume competent Python but don't need to over-explain basic pandas/polars
mechanics. Do explain the *statistical/financial* reasoning behind each
step, since that's what a reviewer (or the author, revisiting this later)
will actually be evaluated on.

## Non-negotiable values

- **Honesty over impressiveness.** No cherry-picked windows, no silent
  removal of a bad out-of-sample result, no vague "significant" claims
  without the number and the test behind it. If out-of-sample performance
  is worse than in-sample, say so: that's a normal and expected finding,
  not a failure to hide.
- **Cost-adjusted, always.** Every backtest number reported should be net
  of a stated transaction cost assumption, not gross returns.
- **Distributions over single numbers.** The cointegration scan is
  explicitly designed to sample many random windows rather than test one.
  Report and plot the distribution of p-values/statistics, not just a mean
  or a single pass/fail.
- **Research-note tone, not academic thesis.** Concise, direct, structured.
  The README should read like something written for a hiring manager with
  20 minutes, not a paper for a journal.
- **State scope and limitations up front**, not buried at the end as an
  afterthought.

## Data specifics (don't relitigate these)

- Kraken tick CSV exports have **no header row**, three columns in order:
  `unixtime, price, volume`. Always load with `header=None` / explicit
  column names: this has already caused silent bugs once.
- Four assets: SOL, BCH, ADA, XRP. **SOL's history starts in 2021; the
  other three go back to 2017.** This is a binding constraint: trim all
  assets to the common date window *before* sizing dollar bar thresholds,
  not after.
- A `merge_asof` + `reduce()` join across four independently-bucketed
  dollar bar series was tried and produced very few matches, because bar
  timestamps don't line up closely enough across assets with different
  bucket spacing. **Don't redo this approach.** The chosen fix is a
  calendar-grid backward-fill join (see `src/data/alignment.py`): build a
  fixed-frequency grid (e.g. hourly) and backward-fill each asset's dollar
  bars onto it. This keeps the within-asset IID benefit of dollar bars
  while giving a consistent cross-asset time axis.
- Shared iteration pattern: assets live in a dict keyed by ticker, e.g.
  `assets = {'SOL': df, 'BCH': df, 'ADA': df, 'XRP': df}`. Keep using this
  pattern rather than four separate named variables.

## Architecture decisions already made (implement, don't redesign)

1. Dollar bars per asset (`src/data/bars.py`)
2. Trim to common window before bar sizing (`src/data/bars.py`)
3. Calendar-grid backward-fill alignment (`src/data/alignment.py`)
4. Engle-Granger cointegration test, run over many random rolling windows
   per pair, not one fixed window (`src/signals/cointegration.py`)
5. Kalman filter hedge ratio, time-varying (`src/signals/hedge_ratio.py`)
6. Z-score spread signal with entry/exit thresholds (`src/backtest/engine.py`)
7. Cost-adjusted backtest (`src/backtest/costs.py`, `src/backtest/engine.py`)
8. Walk-forward out-of-sample split: train window calibrates everything
   (window choice, hedge ratio, thresholds), test window is untouched
   until final evaluation (`src/backtest/engine.py`)

Preferred stack: Polars for data wrangling, statsmodels for the
Engle-Granger test, pykalman for the Kalman filter, matplotlib/seaborn for
plots. Config lives in `config/config.yaml`, loaded via
`src/utils/config.py`. Read parameters from there rather than
hardcoding them in notebooks, so the config file stays the single source
of truth.

## Suggested build order given the timeline

1. `src/data/loader.py` + `src/data/bars.py` (including the common-window
   trim): get one asset's dollar bars working end to end first.
2. `src/data/alignment.py`: align all four assets onto the calendar grid.
   Sanity-check with a plot before moving on.
3. `src/signals/cointegration.py`: random-window Engle-Granger scan
   across all pairs. This produces the first real result and plot.
4. `src/signals/hedge_ratio.py`: Kalman hedge ratio for the
   strongest pair(s) from step 3.
5. `src/backtest/engine.py` + `src/backtest/costs.py`: signal +
   cost-adjusted backtest on in-sample data.
6. Walk-forward split + out-of-sample evaluation.
7. Fill in notebook markdown + README with real numbers and plots, last.

Work through the notebooks in numeric order (`01` → `05`): each one
maps directly to a step above.

## Explicit non-goals

- Don't add extra assets, extra signals, or extra models "for breadth."
  One pair worked all the way through to an honest out-of-sample result
  beats four pairs half-implemented.
- Don't fabricate or extrapolate results before the code actually runs.
- Don't optimise entry/exit thresholds on the out-of-sample window, even
  a little: that defeats the point of having one.
- Don't remove or soften the limitations section to make the project look
  more finished than it is.

## Final review gate (skills-based audit)

Once the pipeline runs end to end, the notebooks are executed for real,
and the README reflects real numbers (i.e. once the project would
otherwise be called "done"), run the `project-audit` skill
(`.claude/skills/project-audit/`) before treating it as finished. This is
as much a demonstration of agentic-architecture design as it is a QA
step: the point being demonstrated is dispatching independent,
narrowly-scoped reviewers in parallel and synthesizing their findings,
rather than one generalist self-review pass.

`project-audit` dispatches four domain checkers as parallel subagents,
each given only the specific files its lens needs (never the builder's
session history, so it can't just confirm what the builder already
believes):

- **`lopez-de-prado-checker`**: AFML-specific financial-ML rigor. Is bar
  construction genuinely IID-improving, is bet sizing conviction-scaled
  or a naive `{-1,0,1}` flag, is there a purging/embargo gap at the
  train/test boundary, and (critically, since this project selects one
  pair from six candidates) is that selection bias disclosed or
  corrected for (Probability of Backtest Overfitting / Deflated Sharpe
  territory).
- **`probability-test-checker`**: general statistical validity. Are a
  cointegration test's own prerequisites (unit roots on the inputs)
  checked, is the 6-pairs × 50-windows scan corrected or contextualised
  for multiple comparisons, are the "random" windows actually independent
  given their width relative to the series length, and are point
  estimates (Sharpe, hit rate) reported with any sense of uncertainty.
- **`chart-sense-checker`**: visual honesty of every generated figure.
  Scale choices, colour-direction consistency across paired panels, axis
  units, and chart-type fit for the sample size behind it.
- **`narrative-checker`**: does the README/notebook prose match the
  actual numbers in `outputs/tables/`, are limitations stated up front
  rather than buried, and is the "best of N candidates" selection stated
  plainly next to the headline result rather than left implicit.

The four are deliberately allowed to converge on the same root cause from
different angles (e.g. the AFML checker's PBO finding and the narrative
checker's "undisclosed best-of-N" finding are the same underlying gap,
seen two ways). That convergence should be *elevated*, not deduplicated
away, in the synthesized `AUDIT.md`. See `.claude/skills/project-audit/SKILL.md`
for the full dispatch-and-synthesize process, and the other three
SKILL.md files for each checker's complete checklist.

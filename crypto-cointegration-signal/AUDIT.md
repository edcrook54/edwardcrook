# Project Audit

Audited 2026-09-15, via the `project-audit` skill (`.claude/skills/project-audit/`),
after the pipeline, notebooks, and README were otherwise complete. Four
checkers - `lopez-de-prado-checker`, `probability-test-checker`,
`chart-sense-checker`, `narrative-checker` - were dispatched as independent,
parallel subagents, each given only the specific files its lens needed and
no visibility into what the other three were doing or finding. This is a
synthesis of their four reports, re-ranked by combined severity, with every
finding's disposition (fixed / deferred, and why).

Two of the four findings below were genuine bugs, not stylistic gaps, and
changed the project's headline result: the selected pair moved from
**SOL-ADA to BCH-ADA**, and the honest in-sample/out-of-sample story flipped
from "in-sample great, OOS degrades" to "in-sample losing, OOS modestly
positive" - see `README.md` for the corrected numbers. That reversal is the
clearest evidence this process was worth running.

## Critical

### 1. Look-ahead leak in the z-score signal's degenerate-window floor (FIXED)

Found independently by both `lopez-de-prado-checker` (as a concrete
mechanism behind an unexplained IS-Sharpe discrepancy) and
`probability-test-checker` (as a reproducibility/precision problem) -
flagged here as one finding since both were describing the same root
cause from different angles, exactly the convergence this process is
designed to surface.

`ZScoreSignalGenerator.zscore()` (`src/backtest/engine.py`) computed its
degenerate-window floor from `np.nanstd()` over the *entire* input array,
once, rather than causally. Notebook 04 called it on a train-only array;
notebook 05 called it on the full train+test array (so the Kalman filter
and z-score could run as one continuous causal pass across the boundary).
Both were supposed to produce identical in-sample numbers - they didn't
(Sharpe 1.305 vs 1.261 pre-fix on the old SOL-ADA pair), because the floor
in notebook 05's call was partly set by out-of-sample volatility.

**Fix:** the floor is now computed from an expanding (strictly-causal,
data-before-t-only) standard deviation instead of a whole-array one
(`src/backtest/engine.py`). Added `test_zscore_is_causal_prefix_matches_full_series`,
which asserts a prefix's z-scores are bit-identical whether or not future
data is appended to the array - this would have failed before the fix.
Notebook 05 now runs an explicit consistency check confirming notebook
04's and notebook 05's in-sample Sharpe match to floating-point precision
(they do, post-fix).

### 2. Cointegration scanner reused one RNG seed across all six pairs (FIXED)

Found by `probability-test-checker`, verified independently before fixing.

`CointegrationScanner.scan_pair` built a fresh `RandomWindowSampler` from
the scanner's single base seed on every call, so every pair sampled the
*exact same* 50 calendar windows. Confirmed directly against the shipped
`outputs/tables/cointegration_scan.csv`: all 6 pairs had identical
`window_start` sets. This collapsed the nominal 6 x 50 = 300 tests down to
50 distinct calendar periods re-tested 6 times, and a shared market-wide
regime in one window showed up as "significant" for several pairs at
once - directly contaminating the cross-pair stability comparison used to
select the traded pair.

**Fix:** `scan_pairs` now derives a distinct seed per pair (`base_seed + index`),
still fully deterministic. Added `test_scan_pairs_uses_distinct_windows_per_pair`
as a regression test. Re-running the scan with per-pair seeds **changed the
selected pair from SOL-ADA to BCH-ADA** (see `outputs/tables/cointegration_summary.csv`) -
direct evidence the original bug wasn't cosmetic.

### 3. Ambiguous/unlabeled axis units on the headline equity and metric charts (FIXED)

Found by `chart-sense-checker` across three figures.

`equity_curve_in_sample.png` and `equity_curve_is_vs_oos.png` had a
y-axis labeled only "Cumulative net return" reaching values >1 with no
unit - ambiguous between an additive sum and a compounded multiple.
`is_oos_metric_comparison.png` plotted Sharpe (a ratio), max drawdown (in
return units), and hit rate (a 0-1 fraction) on one shared "Value" axis,
letting the largest-magnitude metric visually dominate the other two.

**Fix:** equity-curve axes now read "Cumulative net return (compounded, x
of starting capital)"; the IS-vs-OOS equity chart adds a second panel
showing the out-of-sample curve on its own scale (the shared-scale panel
alone visually flattens it, per the same checker's Important finding on
this figure); the metric comparison is now three small-multiple panels,
each with its own correctly-labeled axis, rather than one shared axis.

## Important

### 4. Non-significant single-window re-test mischaracterized as "re-confirmed" (FIXED)

Found by `probability-test-checker`. Notebook 05's limitations text called
a train-only Engle-Granger re-test "re-confirmed" when its p-value
(0.601 for BCH-ADA, post-fix; was 0.706 for SOL-ADA pre-fix) is a clear
*failure to reject* the null of no cointegration - the opposite of
confirmatory. **Fix:** the notebook now prints the correct interpretation
programmatically (reject vs. fail-to-reject, whichever actually occurred)
instead of a static claim, and the limitations bullet was reworded to
point at that cell's output rather than asserting a direction in prose.

### 5. Selection bias: one pair chosen from six, not corrected or fully contextualised (PARTIALLY ADDRESSED)

Found independently by `lopez-de-prado-checker` (as a PBO/Deflated-Sharpe
gap) and `narrative-checker` (which confirmed the "best of six" fact
*was* disclosed prominently in the README, just without backtest context
for the other five). Both checkers agreed the pre-registered,
performance-blind selection rule itself is sound practice - the gap is in
what the reader can see about the alternative candidates.

**Fix (partial):** notebook 04 now backtests all six candidate pairs
identically and reports the full comparison table
(`outputs/tables/all_pairs_in_sample_backtest.csv`) rather than only the
winner - which turned out to matter: the selected pair (BCH-ADA)
backtests *worse* in-sample than at least one alternative (SOL-ADA), and
the notebook says so plainly rather than switching pairs after the fact.
**Deferred:** a formal Probability-of-Backtest-Overfitting or Deflated
Sharpe Ratio correction was not implemented - the all-pairs table is the
cheap partial fix the checklist suggests, not the full statistical
correction.

### 6. No embargo gap at the train/test walk-forward boundary (DEFERRED, DISCLOSED)

Found by `lopez-de-prado-checker`. `WalkForwardSplitter` makes a hard
adjacent cut with zero buffer bars, and the hedge-ratio filter and
z-score rolling window both run continuously across that boundary by
design - so the first few out-of-sample observations are scored using
state still mostly informed by train data. Fixing this requires deciding
how many bars to embargo and re-running the OOS evaluation with a real
gap, which changes the reported OOS window - deferred as a design change
rather than a bug, and now explicitly disclosed as a limitation in
notebook 05 (it previously was not mentioned at all).

### 7. Bet sizing is a flat {-1, 0, +1} flag, not conviction-scaled (ADDRESSED, 2026-09-15 extension)

Found by `lopez-de-prado-checker`; the canonical AFML bet-sizing gap.
Originally deferred because implementing and re-validating a
conviction-scaled sizing rule is a design change that moves every backtest
number, not a contained fix. **Now implemented** in
`notebooks/06_meta_labeling.ipynb` / `src/signals/meta_labeling.py`: a
gradient-boosted meta-model, trained on triple-barrier labels of the
primary model's own past entries, predicts the probability each new entry
pays off; positions are sized via AFML's `size = max(2p - 1, 0)` rather
than a flat flag. Built from scratch, directly inspired by
[Hudson & Thames' MlFinLab](https://github.com/hudson-and-thames/mlfinlab)
(the reference implementation of this exact technique), found via
[awesome-systematic-trading](https://github.com/paperswithbacktest/awesome-systematic-trading).
Result: out-of-sample Sharpe improves marginally on top of the triple-barrier
fix alone (1.37 → 1.43) while total return *falls* (0.73 → 0.42) - sizing
down lower-conviction bets, exactly as intended, not an unambiguous win on
every metric. The meta-model's own held-out AUC (0.88) is reported
alongside the backtest numbers so the result isn't read as more certain
than the underlying classifier's real, if here-surprisingly-strong,
out-of-sample performance.

### 8. No stop-loss / max-holding-period exit leg (ADDRESSED, 2026-09-15 extension)

Found by `lopez-de-prado-checker`. The only exit was the z-score reverting
inside `exit_z`; no hard stop-loss or max-holding-period existed, so a
spread that never reverted could hold an unbounded loss. Originally
deferred alongside #7. **Now implemented** via the same triple-barrier
labeler as #7 (`TripleBarrierLabeler.positions_from_events`), which bounds
every entry with a stop-loss (`stop_z`, wider than the entry threshold)
and a max holding period (`max_holding_bars`), both in
`config/config.yaml`. This alone - before any conviction-sizing - was the
larger effect: bounding the exit took out-of-sample Sharpe from 0.42 to
1.37, because the original unbounded exit let losing trades run
indefinitely waiting for a reversion that sometimes took much longer than
it was worth. A known, disclosed simplification: entries are still
identified from the primary model's own unbounded position array, so an
early triple-barrier exit does not trigger a fresh re-entry within what
the primary model still considers one continuous regime (see
notebook 06's takeaways).

### 9. No unit-root (ADF) prerequisite check before the cointegration test (FIXED)

Found by `probability-test-checker`. `coint()` runs the Engle-Granger
regression and ADF-on-residuals correctly but doesn't verify its inputs
are I(1) to begin with. **Fix:** notebook 03 now runs an ADF test on each
asset's raw price level and its first difference before the scan,
confirming all four assets fail to reject a unit root in levels and
reject one in differences (i.e. are I(1)) - the prerequisite the
downstream Engle-Granger tests assume, now verified rather than assumed.

### 10. Multiple comparisons never contextualised against a chance baseline (FIXED)

Found by `probability-test-checker`. 300 tests at alpha=0.05 implies ~15
false positives under the global null; this number was never stated next
to the raw significant-count. **Fix:** notebook 03 now computes and
prints both numbers directly (expected-under-null vs. actual), plus an
estimate of how likely the sampled windows are to overlap given the
window width relative to series length, so `frac_significant` is
presented with its actual statistical context rather than as a bare
percentage.

### 11. Sharpe/hit-rate point estimates reported with no uncertainty measure (FIXED)

Found by `probability-test-checker`, with the asymptotic SE formula
worked out by hand against the shipped numbers (implied OOS t-stat ≈ 0.44
pre-fix, i.e. not distinguishable from zero). **Fix:** added
`PerformanceEvaluator.sharpe_standard_error()` (asymptotic
`sqrt((1+0.5*SR^2)/N)`, annualised, explicitly documented as an
optimistic lower bound given serial correlation in held-position
returns) and included it in every summary table and in notebooks 04-05's
narrative.

## Minor

- **Boxenplot used on n=50 per pair** (`chart-sense-checker`) - FIXED,
  swapped to a plain boxplot in notebook 03; the strip-plot overlay
  already showed the real point count.
- **Sequential-looking palette on categorical pair labels**
  (`chart-sense-checker`) - FIXED, swapped to a qualitative palette
  (`Set2`) in notebook 03's p-value distribution chart.
- **Mean-p-value heatmap panel used the full 0-1 colour range on data
  spanning ~0.15** (`chart-sense-checker`) - FIXED, colour range now
  scaled to the data's actual span so cell-to-cell differences are
  visible.
- **No zero-reference line on the hedge-ratio chart despite the ratio
  crossing zero** (`chart-sense-checker`) - FIXED, added.
- **Colorblind-safety of the hand-picked long/short/flat regime palette
  not verified** (`chart-sense-checker`) - DEFERRED; low materiality,
  noted for a future pass.
- **Missing axis-unit label on the daily-return pairplot, missing text
  annotation on the daily-price common-start line**
  (`chart-sense-checker`) - DEFERRED; both are legible from the
  surrounding title/context, lower priority than the Critical/Important
  items above.
- **`cost_bps` placeholder never replaced with a sourced Kraken fee
  estimate** (`lopez-de-prado-checker`) - DEFERRED; already honestly
  disclosed as an assumption rather than presented as validated, and
  sourcing a real fee schedule is outside this project's scope.
- **Kalman filter hyperparameters are fixed constants with no sensitivity
  check** (`lopez-de-prado-checker`) - DEFERRED; disclosed in
  notebook 05's limitations.
- **"2,000 bars/asset" stated as an exact figure when actual counts are
  2000-2001** (`narrative-checker`) - not fixed; genuinely trivial,
  config-target framing, does not affect any downstream finding.

## Verified sound (explicit passes from all four checkers)

- Dollar-bar sizing correctly happens *after* the common-window trim, not
  before (`lopez-de-prado-checker`, `src/data/bars.py`).
- The backward-fill duplication this trade-off introduces is disclosed
  and quantified (notebook 02), not hidden.
- Exits are path-dependent (z-score reversion), not a fixed time horizon
  (`lopez-de-prado-checker`).
- No look-ahead in the core P&L mechanics - both the hedge ratio and the
  position are correctly lagged one bar before being applied to returns
  (`lopez-de-prado-checker`, `src/backtest/engine.py`).
- The walk-forward split is genuinely chronological with no shuffling
  (`lopez-de-prado-checker`).
- Pair selection is pre-registered on cointegration stability alone,
  fixed *before* any backtest is run - not selected on backtest
  performance (`lopez-de-prado-checker`, `probability-test-checker`,
  `narrative-checker`, all three independently).
- The project catches and corrects its own full-history-scan look-ahead
  for the final pair evaluation, via the train-only re-test in
  notebook 05 (`lopez-de-prado-checker`).
- Random-window design (distributions, not single p-values) is used and
  reported honestly throughout (`probability-test-checker`).
- "Not significant" is never silently read as "no relationship"
  (`probability-test-checker`).
- Six figures passed the chart review with no findings at all:
  `aligned_price_paths.png`, `backfill_duplication.png`,
  `daily_return_correlation.png` (textbook-correct diverging colormap,
  centered at 0), `dollar_bar_spacing.png`, `history_coverage.png`,
  `price_relationship_scatter.png` (`chart-sense-checker`).
- Every numeric claim in the (pre-fix) README traced exactly to its
  source CSV, to full precision, with zero silently-stale numbers found
  (`narrative-checker`) - this project's README has since been
  regenerated against the post-fix numbers and should be re-verified
  against this bar on the next audit pass.
- Limitations and the headline negative/mixed finding are stated in the
  opening summary, not buried at the end (`narrative-checker`, matching
  CLAUDE.md's explicit "state scope and limitations up front" value).
- No unsupported certainty language ("proves", "confirms", "significant"
  used loosely) found anywhere in the narrative (`narrative-checker`).
- CLAUDE.md's non-negotiable values and explicit non-goals were checked
  point by point against the delivered project and all passed
  (`narrative-checker`).

## What changed as a result of this audit

- Selected pair: **SOL-ADA → BCH-ADA** (cointegration scanner seed fix).
- Headline result: in-sample "great, degrades OOS" → in-sample **losing**
  (Sharpe 0.22, -19% return), out-of-sample **modestly positive**
  (Sharpe 0.42, +12% return) - the opposite shape, and arguably a more
  interesting, harder-to-fabricate finding than the pre-fix one.
- Two regression tests added that would have caught both Critical bugs
  (`test_zscore_is_causal_prefix_matches_full_series`,
  `test_scan_pairs_uses_distinct_windows_per_pair`).
- `PerformanceEvaluator` now reports Sharpe standard error alongside every
  Sharpe point estimate.
- Notebook 03 gained a unit-root prerequisite check and an explicit
  multiple-comparisons/window-overlap disclosure.
- Notebook 04 gained an all-six-pairs backtest comparison table.
- Notebook 05's limitations section grew from 6 to 9 bullets, several of
  them findings from this audit that hadn't been on the radar before.
- README.md was regenerated end-to-end against the corrected pipeline
  (see the current version - its numbers should trace to
  `outputs/tables/*.csv` exactly, per `narrative-checker`'s method,
  though this specific regeneration has not yet been re-audited).

## 2026-09-15 extension: meta-labeling (closes findings #7 and #8)

Prompted by scanning [awesome-systematic-trading](https://github.com/paperswithbacktest/awesome-systematic-trading)
for further improvements, which surfaced MlFinLab as the reference
implementation for exactly the two gaps this audit had deferred. Added
`src/signals/meta_labeling.py` (`TripleBarrierLabeler`, `EntryFeatureBuilder`,
`MetaLabelClassifier`, `ConvictionSizer`) and `notebooks/06_meta_labeling.ipynb`,
with 9 new unit tests (`tests/test_meta_labeling.py`). Findings #7 and #8
above are updated in place to "ADDRESSED" with the result. A PyMC-based
Bayesian treatment (also surfaced by the same list) was considered and
deliberately not implemented - see notebook 06's introduction for the
reasoning (the Kalman filter and Sharpe-SE already carry the
uncertainty-quantification role for this project; a third method wasn't
worth the added compiled-dependency weight for the marginal value here).

One new chart-sense issue was caught and fixed **before** this file was
updated, by applying the project's own established checker discipline
while building the extension rather than waiting for a fresh audit pass:
the first draft of `meta_labeling_oos_comparison.png` repeated the exact
mixed-units mistake (`chart-sense-checker`'s Critical finding #3, above)
on a new chart - Sharpe, drawdown, and hit rate sharing one bar-chart axis
again. Fixed the same way, with small-multiple panels, before this
extension was considered complete.

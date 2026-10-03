---
name: lopez-de-prado-checker
description: Use when reviewing a quantitative trading strategy's data sampling, labeling, bet sizing, or backtest-selection process for adherence to Marcos Lopez de Prado's Advances in Financial Machine Learning (AFML) - triggers on "dollar bars", "IID", "bet sizing", "position sizing", "meta-labeling", "triple barrier", "purging", "embargo", "sample uniqueness", "deflated Sharpe", "probability of backtest overfitting", "PBO".
---

# Lopez de Prado Checker

## Overview

AFML's central thesis is that most quant backtests fail not because the
signal is wrong, but because the *process* that produced it violates one
of a handful of statistical hygiene rules: non-IID sampling, non-IID
labels, binary bet sizing that throws away conviction information, or
reporting a single backtest's Sharpe without correcting for how many
candidates were tried before this one was selected. This skill checks a
strategy's pipeline against that specific checklist - it is not a general
code review and not a general statistics review (see
`probability-test-checker` and `chart-sense-checker` for those).

## When to Use

Any time you are asked to review, audit, or sanity-check a quantitative
trading strategy's implementation - especially one built on financial ML
or systematic backtesting - for methodological soundness rather than bugs.

## Core Checklist

Work through each item against the actual code and outputs, not from
memory of what the design doc says it should do. Cite `file:line` for
every finding.

### 1. Sampling: is the bar construction actually IID-improving?

- Locate the bar-construction code (e.g. dollar/volume/tick bars). Confirm
  bars are sized *after* any cross-asset date trimming, not before -
  sizing thresholds on mismatched histories then trimming silently
  changes the bar count and defeats the point of a fixed target.
- Check every downstream step that consumes these bars for anything that
  re-introduces serial correlation the bar method was chosen to reduce -
  the most common offender in a multi-asset project is a backward-fill
  join onto a calendar grid, which duplicates a stale bar value across
  many grid rows. If present, this is a genuine, reportable tension: the
  project picked information-driven bars *for* their IID properties, then
  the alignment step partially undoes that. Quantify it if a duplication
  metric already exists (e.g. median run-length); if it doesn't, flag that
  it should.

### 2. Bet sizing: is position size binary, or conviction-scaled?

- Find where the final position array is generated. If it is strictly
  `{-1, 0, +1}` (or `{-1, 0, 1}` scaled by a constant), this is a **naive
  fixed-size bet**, not sized bet sizing. AFML Ch. 10 argues size should
  scale with the estimated probability of being right (e.g.
  `size = 2*Phi(z) - 1` off a calibrated probability, or off the signal's
  own z-score magnitude, capped and rounded) - not a flat flag that treats
  a just-crossed-threshold signal identically to an extreme one.
- This is the single most common AFML violation in a from-scratch
  backtest and should be reported even if everything else passes. Report
  it as: what sizing rule is used today, and the one-line change that
  would make it conviction-scaled (e.g. "size positions by
  `tanh(z / entry_z)` instead of `sign(z)`").

### 3. Labeling: fixed-horizon or path-dependent exit?

- Fixed-time-horizon labels (always exit N bars later regardless of what
  happened) are worse than path-dependent exits (AFML's triple-barrier:
  profit-take / stop-loss / max-holding-period, whichever hits first).
- If the strategy exits on a data-driven condition (e.g. a signal crossing
  back through an exit threshold) rather than a fixed holding period, give
  this a clear **pass** - say so explicitly, don't just list gaps. Then
  check whether a triple-barrier's other two legs (a hard stop-loss, a
  max holding period) are present. If the only exit is "signal reverts,"
  note the missing stop-loss/max-holding-period as a gap, since a spread
  that never reverts within the backtest window can otherwise hold an
  unbounded loss.

### 4. Purging and embargo across the train/test boundary

- If the project uses k-fold cross-validation on overlapping-window
  labels, confirm purging (remove train samples whose label window
  overlaps a test sample) and embargo (a buffer after train before test
  starts) are both implemented - this is one of AFML's most-violated
  rules and silently inflates CV scores.
- If instead the project uses a single chronological walk-forward split
  (no k-fold), purging doesn't apply the same way, but **embargo still
  does**: check whether there is any gap between the end of train and the
  start of test, or whether the split is a hard adjacent cut. A hard cut
  lets information that was still "in flight" at the boundary (e.g. a
  filter's internal state, a rolling window still partially inside train)
  leak a small amount of continuity into the first test observations.
  Report the actual gap (in bars/days) used, or its absence.

### 5. Selection bias: was this the only candidate tried?

- If the reported strategy was chosen from a larger set of candidates
  (multiple asset pairs, multiple parameter sets, multiple lookback
  windows), the reported Sharpe/return on the *winner* is optimistically
  biased relative to what a single, pre-registered candidate would show -
  this is exactly what Bailey & Lopez de Prado's Probability of Backtest
  Overfitting (PBO) and Deflated Sharpe Ratio (DSR) are for.
- Count how many independent candidates were actually compared (e.g. N
  pairs x M parameter combinations). Check whether the reported
  performance numbers are deflated/adjusted for that count in any way, or
  whether the narrative at least states plainly that the reported number
  is the best-of-N and should be read as optimistic. If neither exists,
  this is a **Critical** finding - not because the backtest is wrong, but
  because the number as presented invites the reader to think it's
  unconditional when it's actually a selected maximum. A cheap partial
  fix worth suggesting: report the performance of the *other* candidates
  alongside the winner, so the reader can see the spread themselves.

### 6. Sample uniqueness / serial correlation in reported metrics

- If positions are held for multiple consecutive bars, the per-bar
  returns feeding a Sharpe ratio are serially correlated, which the
  standard Sharpe formula assumes away. Check whether the number of
  *independent* bets is anywhere near the number of *bars* used in the
  Sharpe calculation - if a strategy is in a handful of long-held
  positions across thousands of bars, treating each bar as one
  observation overstates statistical confidence (report this finding but
  leave the precise correction - Newey-West SEs, effective-N adjustment -
  to `probability-test-checker`, and cross-reference it there).

## Quick Reference

| Check | Pass condition | Common failure |
|---|---|---|
| Sampling | Bars sized after trim; duplication quantified | Threshold sized before trim; duplication undisclosed |
| Bet sizing | Size scales with conviction | Flat `{-1,0,1}` |
| Labeling | Path-dependent exit, all 3 barrier legs | Fixed horizon, or missing stop-loss/max-hold |
| Purging/embargo | Explicit gap at train/test boundary | Hard adjacent cut, no gap |
| Selection bias | N candidates disclosed, deflated or contextualised | Single "winner" number presented as unconditional |
| Sample uniqueness | Effective-N acknowledged | Bar count used as if independent |

## Red Flags (in the code or the narrative)

- A position/signal array whose only values are -1, 0, 1.
- A backtest report that names one pair/parameter set without saying how
  many were tried.
- "Purged" or "embargo" nowhere in the codebase despite k-fold CV on
  overlapping labels.
- A Sharpe ratio quoted to two decimal places with no mention of how many
  independent bets it's actually based on.

## Rationalization Table

| Excuse | Reality |
|---|---|
| "It's just a threshold signal, sizing doesn't apply" | Any signal with a continuous underlying statistic (z-score, probability, distance to threshold) can be conviction-scaled; choosing not to is a design decision to disclose, not a reason sizing doesn't apply. |
| "We only tried a few pairs, selection bias is minor" | PBO's whole point is that even a handful of candidates meaningfully inflates the best-of-N result; "a few" is not zero. |
| "The walk-forward split is chronological, so there's no leakage" | Chronological ordering prevents *future* leakage; it doesn't address filter/window continuity *at* the boundary, which embargo is for. |

## Output Format

Report findings as Critical / Important / Minor, each with the specific
`file:line` or notebook cell it applies to, one sentence on why it
matters, and (where possible) a concrete one-line fix. Explicitly list
what *passed* too - a checker that only ever reports problems is less
trustworthy than one that shows its work on the things it verified and
found sound.

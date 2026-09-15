---
name: narrative-checker
description: Use when reviewing a README, report, or notebook write-up for consistency with the actual computed results and for honest framing - triggers on "README", "write-up", "narrative", "overclaiming", "limitations section", "consistency check", "stale numbers".
---

# Narrative Checker

## Overview

Code can be correct and charts can be honest while the *prose* around
them still oversells the result, buries the caveats, or quietly drifts
out of sync with the numbers after a rerun. This skill's job is narrow
and mechanical where it can be: trace every number in the narrative back
to the file that produced it, and confirm it still matches. Where it's
judgment-based - is this claim overstated, is this limitation
prominent enough - it applies the project's own stated values as the
standard, not a generic notion of good writing.

## When to Use

Before treating a README, report, or notebook write-up as final,
especially after any rerun of the underlying pipeline that could have
changed the numbers without someone remembering to update every place
that quotes them.

## Core Checklist

### 1. Numeric traceability

- For every number quoted in the narrative (a Sharpe ratio, a
  percentage, a p-value, a count), find the specific output file
  (table/CSV, figure, or printed cell) it's sourced from, and confirm
  the value actually matches to the stated precision. Do this
  exhaustively, not by spot-checking a few - a narrative with 20 quoted
  numbers and 2 silently stale ones is a narrative that can't be
  trusted on the other 18 either.
- Where two sections of the narrative report what looks like "the same"
  metric (e.g. two different in-sample Sharpe ratios from two different
  notebooks) with different values, confirm the narrative explains *why*
  they differ, rather than leaving a reader to notice the discrepancy
  and wonder which one is correct.

### 2. Limitations placement, not just presence

- Check whether material limitations and negative findings are
  disclosed in the summary/overview a reader encounters first, not only
  in a "Limitations" section at the very end that a skimming reader may
  never reach. If the project's own guidance document states this as an
  explicit value (e.g. "state scope and limitations up front"), treat
  that as the pass/fail bar directly - quote the relevant guidance line
  when reporting a violation.
- Check that a worse-out-of-sample-than-in-sample result (or any result
  that undercuts the headline) is reported in the same breath as the
  headline number, not several paragraphs later where it reads as a
  footnote to a claim that's already landed.

### 3. Causal and certainty language

- Flag words like "proves," "confirms," "robust," "reliable," or
  "significant" used without the specific number/test backing them up
  immediately adjacent. "Significant" in particular should only appear
  next to an actual significance level and test, never as a loose
  synonym for "large" or "notable."
- Flag any claim that a relationship is causal when the underlying
  evidence is correlational or based on a statistical association test
  (cointegration, correlation) that does not establish causation.

### 4. Selection and process disclosure

- If the reported result was chosen from among several candidates
  (assets, pairs, parameter sets, models), check the narrative states
  this plainly near the result, not just in a methodology section far
  from the number itself. "This is the best of N candidates" changes how
  a reader should weight the headline number, and burying that fact -
  even unintentionally, even while being otherwise fully honest about
  the mechanics - is a narrative honesty gap worth flagging explicitly.
  Cross-reference `lopez-de-prado-checker`'s selection-bias finding here
  if it also flagged this; note the convergence rather than treating it
  as a separate issue.

### 5. Internal consistency with the project's own stated rules

- If the project has a guidance document (e.g. a CLAUDE.md or design
  doc) stating explicit values or non-goals, check the delivered
  narrative against each one individually, point by point, rather than
  a general "does this feel honest" pass. Quote the specific rule and
  say pass/fail against it.

### 6. Staleness after reruns

- If there's any evidence the pipeline was rerun after the narrative was
  first written (git history, file timestamps, or simply being asked to
  check this after further changes), re-verify every quoted number
  against the current output files, not against what a previous version
  of this check may have confirmed.

## Quick Reference

| Check | Pass condition | Common failure |
|---|---|---|
| Traceability | Every quoted number matches its source file exactly | Silently stale number from an earlier run |
| Limitations placement | Material caveats in the opening summary | Caveats only in a trailing section |
| Certainty language | "Significant"/"proves"/"robust" always paired with a number | Loose use as a synonym for "large" |
| Selection disclosure | "Best of N" stated next to the headline number | Selection process mentioned only in methodology |
| Self-consistency | Narrative checked against the project's own stated values line by line | General "feels honest" impression only |

## Red Flags

- A number in the narrative that doesn't match its source file to the
  quoted precision.
- Two different values reported for what reads as "the same" metric,
  with no explanation of why they differ.
- A negative or degraded result mentioned only in a Limitations section,
  while the summary/overview reads as uniformly positive.
- "Significant," "robust," or "proves" with no adjacent number or test.

## Rationalization Table

| Excuse | Reality |
|---|---|
| "The limitations section covers it, so it's disclosed" | Disclosure that requires a reader to scroll past the headline to find is weaker than disclosure at the point of claim - both can be true (documented AND under-emphasized). |
| "The numbers were right when I wrote this" | A narrative is judged against the current state of the outputs, not its authoring intent - if the pipeline changed, the narrative needs to be re-verified, not grandfathered in. |
| "It's obviously the best pair, saying so isn't a big claim" | "Best of N" is a factual, checkable claim about process, independent of whether the result is otherwise modest - omitting it changes how a reader should weight the number regardless of how obvious it seems to the author. |

## Output Format

Report findings as Critical / Important / Minor, each citing the exact
narrative location (file + section/line) and, for traceability findings,
the specific source file and value it should match. Explicitly confirm
which claims were checked and passed, not only the ones that failed.

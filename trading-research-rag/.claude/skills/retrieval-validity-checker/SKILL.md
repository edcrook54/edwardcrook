---
name: retrieval-validity-checker
description: Use when reviewing an information-retrieval eval set or metrics implementation for methodological validity - triggers on "recall@k", "precision@k", "MRR", "nDCG", "gold set", "eval leakage", "retrieval eval", "IR metrics".
---

# Retrieval Validity Checker

## Overview

An IR eval can run cleanly, produce plausible-looking Recall@k numbers, and
still be measuring something other than what it claims. That happens when the
gold labels were sourced in a way that leaks the system's own answers into its
own ground truth, or when a metric formula has an off-by-one that happens to
produce reasonable-looking values anyway. This skill checks whether
`trading-research-rag`'s eval set and metric implementations are actually
valid, not just whether `make eval` exits zero.

## When to Use

Before trusting any Recall@k / Precision@k / MRR / nDCG number reported for
this project, and especially before accepting a claim like "hybrid beats
BM25" or vice versa as the headline finding.

## Core Checklist

### 1. Gold-set independence (the most important check)

- For every entry in `config/eval/analyst_gold.json`, confirm the
  `relevant_chunk_ids` could plausibly have been found by reading the
  cited source file/notebook directly. Cross-check a sample against the
  actual corpus content, not against what the retrieval system returns for
  that query. If a label's provenance can only be explained by "the system
  ranked this first, so it must be right," that is a **Critical** finding:
  the eval is circular for that query.
- Check `find_chunk.py` (the tool used to build gold labels) genuinely
  never imports or calls `bm25.py`, `dense.py`, `fusion.py`, or `index.py`.
  If it does, the independence guarantee is void regardless of what the
  docstring claims.
- For `heading_gold.json` (the bootstrapped tier), confirm the README and
  code are explicit that this tier is weak supervision (heading text as its
  own query) and not presented as equivalent evidence to the hand-labeled
  tier. Reporting only the easier tier's numbers, or blending both into one
  number without the breakdown, would overstate retrieval quality.

### 2. Metric formula correctness

- Recall@k: hits in top-k divided by *total relevant*, not by k or by hits
  found overall. Verify against `tests/test_eval_metrics.py`'s hand-worked
  examples, not just by reading the implementation.
- nDCG@k: confirm the discount is `1/log2(rank+1)` (rank starting at 1,
  so the top result gets `1/log2(2) = 1`), and that IDCG is computed from
  `min(|relevant|, k)` ideal hits, not from `k` unconditionally. The latter
  caps nDCG below 1 even for a perfect ranking when there are fewer relevant
  docs than k.
- MRR (`reciprocal_rank`): confirm it stops at the *first* relevant hit per
  query and doesn't average over all relevant hits found.
- Bootstrap CI: confirm resampling is over *queries* (the actual unit of
  measurement), not over some finer-grained unit that would understate the
  true uncertainty.

### 3. Apples-to-apples comparison across BM25/dense/hybrid

- Confirm all three modes are evaluated against the *same* top-k cutoff and
  the *same* gold queries. A hybrid that's evaluated at a different k or
  against a filtered query subset would make any comparison meaningless.
- Confirm the "pooled" metric (combining both gold tiers) is a genuine
  per-query aggregation, not an average-of-averages that implicitly
  reweights the two tiers by something other than query count.

### 4. The "BM25 beats hybrid" claim specifically

- This project's headline finding is that plain BM25 outperforms the
  hybrid fusion. Check the README's claimed parameter sweep (RRF k,
  SVD components) actually appears to have been run, not merely asserted,
  and that the reported ranges are wide enough to rule out "one bad
  default" as the explanation. If no sweep evidence exists beyond the
  README's prose, that's an **Important** finding: the honesty bar this
  repo holds itself to requires showing the sweep, not just claiming one
  was done.

### 5. Index hash / staleness interaction with eval validity

- Confirm `run_eval.py` evaluates against the same index whose hash is
  reported, and that there's no path where a stale, previously-saved index
  gets evaluated after the corpus has changed underneath it (cross-reference
  `production-robustness-checker`'s idempotency finding if it also touches
  this).

## Quick Reference

| Check | Pass condition | Common failure |
|---|---|---|
| Gold independence | Labels traceable to source text, not search output | Label chosen by eyeballing top search result |
| Metric formulas | Match hand-worked test cases exactly | Off-by-one in rank/log discount, wrong IDCG cap |
| Fair comparison | Same k, same queries across all modes | Hybrid evaluated on an easier subset |
| Sweep evidence | Parameter sweep shown, not just claimed | "We tried a few values" with no numbers |
| Index freshness | Eval always runs against the current corpus's index | Stale pickled index silently reused |

## Red Flags

- Any gold label whose only justification is "the system found this."
- A metric function with no corresponding hand-worked test.
- A headline comparative claim ("X beats Y") backed by a single run with no
  sweep or robustness check.

## Rationalization Table

| Excuse | Reality |
|---|---|
| "I checked a few gold labels by searching for them first" | Searching first and then writing the label down is exactly the leakage this checklist exists to catch, even if the label is factually correct. The process, not just the outcome, must be independent. |
| "The heading-bootstrapped tier is basically free, more data can't hurt" | More *easy* queries can inflate a pooled average and make the system look stronger than the hand-labeled tier alone would suggest. The tiers must be reported separately, not just pooled. |
| "BM25 winning once is good enough to report" | One run can't distinguish a real effect from a lucky hyperparameter default. The claim needs the sweep. |

## Output Format

Report findings as Critical / Important / Minor, each citing the exact file
and gold-set entry or metric function involved, plus a concrete suggested
fix. List explicit passes (e.g. "spot-checked 5/15 analyst_gold.json labels
against source text directly, all independently verifiable") alongside
failures.

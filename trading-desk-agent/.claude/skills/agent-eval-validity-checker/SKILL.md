---
name: agent-eval-validity-checker
description: Use when reviewing an agent eval's methodology for validity - whether its gold questions are genuinely answerable from the available tools, whether any LLM-as-judge is itself validated against human labels, and whether non-determinism is logged - triggers on "agent eval", "LLM-as-judge", "gold questions", "eval validity".
---

# Agent Eval Validity Checker

## Overview

An agent eval can run cleanly and produce plausible-looking metrics while
testing the wrong thing - gold questions that don't actually require the
tools they claim to, or (if ever added) an LLM-as-judge trusted without
itself being validated. This mirrors `retrieval-validity-checker` from
`trading-research-rag` and `label-reliability-checker` from
`llm-news-signal`, applied to an agent eval instead of a retrieval or
labeling eval.

## When to Use

Before trusting `config/eval_questions.json` as a meaningful test set, or
any future LLM-as-judge grading built on top of it.

## Core Checklist

### 1. Are the gold questions genuinely answerable from the tools?

- For each question in `config/eval_questions.json`, confirm its
  `expected_tools` are actually capable of answering it - e.g. a question
  expecting `search_corpus` should have real, findable content in
  `trading-research-rag`'s indexed corpus (spot-check a few by actually
  calling the tool or checking the source files directly).
- Confirm `gold_keywords` were derived from the actual source material
  (sibling projects' READMEs/AUDIT.md/CLAUDE.md), not invented - the same
  independence discipline `llm-news-signal`'s hand labels follow: written
  by reading the real source, not by running the system under test first.
- Check the "refusal" category question (asking for live Bitcoin price)
  genuinely has no tool that could answer it - confirm none of the four
  tools, even indirectly, could produce a live price, so a "cannot answer"
  response is actually the correct behavior being tested for, not an
  artifact of weak tooling.

### 2. Tool-usage-recall and keyword-recall validity

- Confirm `tool_usage_recall`'s vacuous-pass case (empty `expected_tools`
  returns 1.0) is used correctly - only the refusal question should have
  an empty `expected_tools` list; any other question with an empty list
  would make the eval trivially easy to pass on that item.
- Confirm `keyword_recall`'s keyword lists are specific enough to
  distinguish a real answer from a generic non-answer (e.g. a keyword list
  of just `["the"]` would pass almost anything) - spot-check a few for
  specificity.

### 3. LLM-as-judge validity (once one exists)

- Not yet applicable - no LLM-as-judge is implemented. When one is added,
  this checklist item should require: the judge's grading validated against
  a held-out set of the reviewer's own human judgments (same kappa-style
  discipline as `llm-news-signal`), gold labels for that validation written
  *before* seeing the judge's output, and the judge's model/prompt version
  logged per graded item (same determinism discipline as
  `llm-determinism-checker`).

### 4. Non-determinism and reproducibility

- Confirm `run_eval.py` logs enough about each run (model name, which
  questions, transcript file paths) that a future reader could tell which
  eval run a given `data/eval_results.json` came from - an eval result
  with no record of what model/version produced it isn't reproducible
  evidence.

## Quick Reference

| Check | Pass condition | Common failure |
|---|---|---|
| Question answerability | Each question's expected tools can actually answer it | A question expecting a tool that has no relevant content |
| Gold-label independence | Keywords/citations derived from source text directly | Keywords copied from a prior system run |
| Refusal case validity | No tool could answer it, confirmed | A tool could technically answer it, making refusal the wrong expectation |
| Keyword specificity | Keywords distinguish a real answer from a generic one | Keywords so generic almost any answer passes |
| Eval provenance | Model/version/question-set logged per run | Results with no record of what produced them |

## Red Flags

- A gold question whose `expected_tools` can't plausibly produce the
  `gold_keywords` it's checked against.
- An LLM-as-judge added without a validation step against human labels.
- `eval_results.json` with no record of which model or prompt version ran.

## Rationalization Table

| Excuse | Reality |
|---|---|
| "I wrote the questions myself from the real READMEs, that's good enough" | Writing them from real material is necessary but the *keywords/expected tools* also need to be checked for whether they actually discriminate a good answer from a bad one, not just whether they're truthful. |
| "An LLM-as-judge is obviously more reliable than keyword matching" | An unvalidated judge is not obviously more reliable than a mechanical check - it's differently fallible, and claiming otherwise without validation is exactly the gap this checklist exists to catch. |

## Output Format

Report findings as Critical / Important / Minor with file:line references
and a concrete suggested fix. List explicit passes.

# Project Audit

Audited 2026-10-03, via the `project-audit` skill (`.claude/skills/project-audit/`).
**This is a pre-execution audit**: no `ANTHROPIC_API_KEY` was available, so no real
agent run or live audit-dispatch run has happened, and the README's live-eval
section is correctly marked PENDING. The four checkers
(`tool-use-safety-checker`, `hallucination-citation-checker`,
`agent-eval-validity-checker`, `narrative-checker`) were dispatched in parallel
against the pipeline's *mechanism* — tool sandboxing, the citation-precision
metric's correctness, the gold eval set's validity, and the PENDING framing's
honesty — not against real agent-quality numbers, which don't exist yet. A
second, full audit (re-running all four against real transcripts and real
`data/eval_results.json`) is still required once `make eval-live` has actually
run — see CLAUDE.md's "Final review gate." All findings below were fixed before
this report was written; none were deferred without a stated reason.

## Critical

1. **The citation-precision regex absorbed trailing sentence punctuation,
   producing false hallucination flags for the overwhelmingly common case of a
   citation at the end of a sentence.** (`hallucination-citation-checker`)
   `_PATH_LIKE_RE`'s character class included `.`, so an answer like "...see
   `pm-bayes-pricer/README.md`." (a real, correctly-cited source) extracted the
   token `pm-bayes-pricer/README.md.` (with the trailing period), which then
   failed to match the evidence and was wrongly flagged unsupported — the exact
   opposite of the metric's purpose. Verified live: reproduced the false flag,
   confirmed the fix. **Fixed**: `_extract_clean_paths` now strips trailing
   `.,:;)'"` from every extracted token, on both the answer side and the
   evidence side. Regression-tested in
   `test_citation_precision_does_not_falsely_flag_a_sentence_ending_citation`.

2. **8 of 16 gold eval questions expected `search_corpus` to find content that
   was never indexed.** (`agent-eval-validity-checker`) `trading-research-rag`'s
   corpus is fixed to only `crypto-cointegration-signal` and `pm-bayes-pricer`
   (confirmed in that project's own `config.py`/README) — it does not index
   itself or `llm-news-signal`. Eight questions asked about `trading-research-rag`'s
   own audit/eval content or `llm-news-signal`'s content with `expected_tools:
   ["search_corpus"]`, which structurally cannot retrieve either. A correctly-
   behaving agent would score near-zero on these through no fault of its own
   reasoning, or be pushed toward guessing (exactly the hallucination risk
   `citation_precision` exists to catch) rather than a genuine tool-selection
   failure. **Fixed**: all 8 questions' `expected_tools` changed to `["get_file"]`
   (which *can* reach these projects' files — `allowed_file_roots` already
   included them), their `gold_citation_substring` changed to a real, verified
   file path, and their wording adjusted to ask "according to `<project>`'s
   README/CLAUDE.md" to make the intended tool unambiguous. Every corrected
   citation path was independently re-verified to actually resolve via
   `get_file` after the fix.

## Important

3. **No structural link between `rerun_backtest_variant`'s subprocess timeout
   and grandchild-process cleanup, and a prompt-injection-from-tool-output risk
   with no mitigation, were both real but previously undisclosed.**
   (`tool-use-safety-checker`) Verified live: path-traversal, symlink-escape,
   override-allowlist-bypass, and shell-injection-via-allowed-key attempts were
   all correctly blocked by existing code (not just docstrings) — no exploit
   found. But two real limitations had no README mention: (a) tool results flow
   into the next model message with no framing marking them as untrusted
   content, and (b) a subprocess timeout bounds wall-clock time but not
   necessarily a full process tree. **Fixed**: both disclosed explicitly in
   README "Scope and limits," not silently left unmentioned.

4. **Several `gold_keywords` were too generic to discriminate a correct answer
   from an incorrect or generic one.** (`agent-eval-validity-checker`) Specific
   examples verified: `"6"` alone substring-matches "2026"/"16"/"60"; a bare
   `"0.4"` matches 0.40-0.49; `"mean"`/`"sol"` alone are generic enough to match
   unrelated text (`"sol"` even matches inside "console"/"resolve"). **Fixed**:
   replaced with verified, specific phrases actually present in the real source
   text (e.g. `"2 assets x 3 horizons"`, `"landis & koch"`, `"gbm_har"`,
   `"newey-west"`), each independently re-checked against the real files with
   `grep` after the change, not just asserted.

5. **No eval-run provenance**: `data/eval_results.json` would have recorded no
   model name or transcript file path per question, making a past result set
   unverifiable against the transcript that produced it. (`agent-eval-validity-checker`)
   **Fixed**: `AgentResult` now carries `model` and `transcript_path`;
   `run_eval.py` writes both into every result row.

6. **`citation_precision`'s vacuous pass ("cited nothing") was indistinguishable
   from "cited things, all verified" in any aggregate reporting.**
   (`hallucination-citation-checker`) A future agent that learned to avoid
   citing anything at all would have silently inflated the mean precision
   score. **Fixed**: `citation_precision` now returns an explicit `cited_nothing`
   flag; `run_eval.py` reports a separate `zero_citation_rate` alongside the
   mean, so the two conditions can never collapse into one number.

7. **Citation matching used an unanchored raw substring check, so a truncated
   or mangled citation that happened to be a textual substring of a real one
   would score as supported.** (`hallucination-citation-checker`) Verified live:
   a citation missing its leading path segment (`bar/baz.md` vs. the real
   `foo/bar/baz.md`) scored fully supported before the fix. **Fixed**: matching
   is now against the *set* of whole path-like tokens extracted from the
   evidence (via the same extraction function used on the answer), not a raw
   substring check — a truncated citation no longer exact-matches a longer real
   one. Regression-tested in
   `test_citation_precision_does_not_accept_a_truncated_citation_as_supported`.

8. **README's own "verified" claim didn't match its cited test.** (`narrative-checker`)
   The README stated a hallucinated citation was "correctly flagged with
   precision 0.0," but the test it was describing
   (`test_citation_precision_flags_a_hallucinated_citation`) actually asserts
   0.5 (one real + one fabricated citation). No committed test produced a pure
   0.0 case at the time. **Fixed**: added
   `test_citation_precision_is_zero_when_every_citation_is_unsupported` and
   corrected the README to accurately describe both the 0.5 and 0.0 cases by
   name.

9. **The audit-dispatch synthesis's keyword-overlap limitation was disclosed
   only in "Design decisions," not in "Scope and limits"** where a skimming
   reader would actually look for caveats. (`narrative-checker`) **Fixed**:
   pulled a concise version of the disclosure up into "Scope and limits."

## Minor

10. **`citation_precision` can't catch a correctly-cited source paired with a
    misquoted fact** — it only checks that a cited *path* was actually
    retrieved, not that claims about its contents are accurate.
    (`hallucination-citation-checker`) **Disclosed, not fixed**: this is a
    structural limitation of a mechanical (non-semantic) metric, not a bug;
    noted explicitly in the skill checklist and left as a known gap pending a
    real LLM-as-judge.
11. Minor keyword/phrasing looseness in the refusal question's keyword list
    (contraction-sensitive, e.g. "I can't" vs. "cannot") —
    (`agent-eval-validity-checker`) **mitigated**: added `"can't"` as an
    additional accepted keyword variant; full phrasing-robustness would need
    the same LLM-as-judge this project already defers.
12. A subprocess timeout doesn't guarantee full process-tree/resource cleanup
    — (`tool-use-safety-checker`) **disclosed** in README, not currently
    exploitable (the wrapped CLI doesn't fork further).

## Verified sound

- No arbitrary code execution path exists in any tool: `run_stat_test` dispatches
  over a fixed 3-value enum; `rerun_backtest_variant`'s override allowlist is
  enforced in code before the config is merged/written, confirmed by reading
  the execution order, not the docstring; YAML `safe_load`/`safe_dump` are used
  throughout, never `yaml.load`/`eval`.
- `get_file` genuinely cannot escape its allowed roots: path traversal, bare
  absolute paths, URL-encoded traversal, prefix-confusion root names, and a
  real symlink-escape attempt (a symlink *inside* an allowed root pointing
  outside it) were all tested live and correctly blocked by the
  `.resolve()` + `is_relative_to` check — not merely a string-prefix check a
  crafted path could defeat.
- The agent loop's `max_iterations` cap is real and enforced, with a
  distinguishable `hit_max_iterations`/`stop_reason="max_iterations"` result
  that cannot be confused with a genuine final answer.
- No tool error is ever silently swallowed: every caught exception becomes a
  visible `is_error: true` tool result the loop continues past.
- The `ANTHROPIC_API_KEY` never appears in any written transcript or error
  message — confirmed by tracing every place `anthropic_api_key` is referenced
  in the codebase.
- The async multi-checker dispatch's concurrency is real, not just claimed:
  three 0.05s-delay scripted calls complete in ~0.05s total via
  `asyncio.gather`, independently re-timed and confirmed well under the 0.15s
  bound stated in the README.
- All 8 in-corpus-appropriate questions (the ones still correctly using
  `search_corpus`) were independently checked against the real source text in
  `crypto-cointegration-signal`/`pm-bayes-pricer` and confirmed genuinely
  answerable from what's actually indexed.
- The refusal question (live Bitcoin price) was confirmed to have no answering
  path through any of the four tools — a refusal is genuinely the correct
  behavior being tested for, not an artifact of weak tooling.

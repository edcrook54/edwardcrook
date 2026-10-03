# Project Audit

Audited 2026-10-02, via the `project-audit` skill (`.claude/skills/project-audit/`),
once the retrieval pipeline ran end to end, `make eval` produced real numbers, and
the README reflected them. Four independent, narrowly-scoped subagent checkers
(`retrieval-validity-checker`, `production-robustness-checker`,
`citation-provenance-checker`, `narrative-checker`) were dispatched in parallel, each
given only the files its lens needed and no visibility into the others' findings or
the builder's own session history. All findings below were fixed before this report
was written; none were deferred without a stated reason.

## Critical

1. **The index could silently go stale while the service was running, directly
   contradicting this project's own "never silently serve a stale index" claim.**
   (`production-robustness-checker`) The original `_load_index()` was a process-
   lifetime `@lru_cache(maxsize=1)`: once loaded, it was never re-checked, so running
   `make index` against a live `make serve` process had zero effect until restart —
   verified live by corrupting the on-disk hash and watching `/health` keep returning
   the stale cached result. **Fixed**: `api.py`'s `_load_index()` now re-reads the
   small sidecar hash file on every request and only re-unpickles the (larger) index
   when it's actually changed. Regression-tested in
   `tests/test_api.py::test_rebuilt_index_is_picked_up_without_a_restart`.

2. **The README and `index.py` docstring overclaimed what the content hash actually
   guarantees.** (`citation-provenance-checker`) Both claimed a stale index "can
   never silently serve queries after the corpus has moved on." In fact
   `content_hash()` is fixed at build time and the hash check only catches a
   pickle/sidecar mismatch (corruption or tampering) — it says nothing about whether
   the source files in `edwardcrook/` changed *since* the last `make index` run; the
   old pickle and old hash file agree perfectly with each other in that case.
   **Fixed**: reworded the docstring and README to state precisely what is and isn't
   guaranteed, and named the remaining gap explicitly in "Not yet done."

3. **CI's own `/metrics` smoke-test step didn't actually pass.** (`production-robustness-checker`)
   `/metrics` is a Starlette sub-mount that 307-redirects the bare path to `/metrics/`;
   `curl -sf` (no `-L`) returns an empty body with exit 0, so the `grep -q` after it
   failed the step under `bash -eo pipefail`. Verified live. **Fixed**: added `-L` to
   that `curl` call in `.github/workflows/trading-research-rag.yml`.

## Important

4. **`make eval` didn't exist.** Found independently by two checkers from different
   angles — `retrieval-validity-checker` (the CI-gate claim couldn't be exercised as
   documented) and `narrative-checker` (the README's own "2 minutes, nothing to
   install" reproduction step was broken) — which is a stronger signal than either
   alone. The Makefile had no `eval`/`eval-gate` target despite README, CLAUDE.md, and
   `run_eval.py`'s own docstring all instructing `make eval` / `make eval -- --gate`.
   **Fixed**: added `eval`, `eval-gate`, `eval-baseline`, and `sweep` targets; aligned
   all prose to the real command names.

5. **The headline "parameter sweep" claim had no committed evidence.** Also found
   independently by both `retrieval-validity-checker` and `narrative-checker`: the
   README asserted a sweep over RRF `k` and SVD components but no script, notebook, or
   test reproduced it — a reader would have to rewrite it themselves to verify a
   headline claim, which this project's own "shown, not just claimed" bar doesn't
   allow. Both checkers independently re-ran the sweep themselves and confirmed the
   *numbers* were accurate; the gap was reproducibility, not correctness. **Fixed**:
   committed `src/tradingrag/eval/sweep.py` (wired to `make sweep`), re-ran it, and
   corrected the README's quoted ranges to match its actual output.

6. **Whitespace-only queries were silently accepted.** (`production-robustness-checker`)
   `Query(..., min_length=1)` rejects `""` but not `"   "`; confirmed live that
   `q=%20%20%20` returned `200 {"hits":[]}` instead of a 4xx. **Fixed**: `/search` now
   explicitly rejects a query that is empty after stripping, before touching the index
   or incrementing metrics. Tested in `test_search_rejects_whitespace_only_query`.

7. **A real mis-chunking bug: the naive header regex misread a `#` comment inside a
   fenced code block as a markdown header.** (`production-robustness-checker`) Verified
   live against `pm-bayes-pricer/README.md`'s Quick Start block, which has exactly this
   pattern (`# with the Kraken tick files available locally:` inside a bash fence) —
   this silently split one real section into two and shifted every later section's
   index, corrupting provenance for the exact thing this project's citations depend
   on. Not disclosed, not tested. **Fixed**: `chunk.py` now tracks fence state
   (`_iter_headers`) and never matches a header inside a fenced block; rebuilding the
   index after the fix dropped the chunk count from 325 to 324 (confirming the bug
   was live, not theoretical) and `heading_gold.json` was regenerated accordingly (all
   15 `analyst_gold.json` labels were independently confirmed still valid — none
   referenced the affected region). Regression-tested in
   `test_chunk_markdown_ignores_hash_lines_inside_fenced_code_blocks`.

8. **503 errors from a missing index gave a raw, non-actionable message.**
   (`production-robustness-checker`) A caller hitting `/health` or `/search` before
   `make index` had ever run got FastAPI's default `FileNotFoundError` string with no
   pointer to the fix. **Fixed**: the error now reads
   `"no index found at {index_dir}; run `make index` first"`.

9. **No API-layer test coverage existed at all.** (`production-robustness-checker`)
   Every finding above involving `/health`/`/search` behavior was, until now, invisible
   to `pytest` — only nominally covered by CI's narrow manual smoke test. **Fixed**:
   added `tests/test_api.py` (9 tests) covering missing-index 503s, whitespace/empty
   query rejection, `top_k`/`mode` bounds, a real citation round-trip, the `/metrics`
   endpoint, and the no-restart-refresh behavior from finding 1.

10. **No regression test guarded the chunk-id collision bug the README claims was
    fixed.** (`citation-provenance-checker`) The bug (missing repo-name prefix on
    `chunk_id`, allowing two projects' same-named files to collide) was indeed fixed in
    the code, but nothing would catch a future regression dropping the prefix again —
    every existing test used a single corpus root. **Fixed**: added
    `test_chunk_id_does_not_collide_across_repos_with_the_same_filename`, constructing
    two same-named files under two different repo roots.

11. **Stale counts in the README.** (`narrative-checker`) The test count (quoted as 27)
    was already stale at audit time (actual: 30, before this audit's own fixes added
    11 more). **Fixed**: updated to the current count (41) in both places it's quoted,
    after all other fixes landed.

## Minor

12. **`_repo_name`'s fallback (`path.parent.name` for a path outside all
    `corpus_roots`) is silent and untested.** (`citation-provenance-checker`) Not
    reachable via the real pipeline — `load_corpus` only ever walks `corpus_roots`
    itself — so this is a latent footgun for a hypothetical future direct call to
    `chunk_markdown`/`chunk_notebook`, not a live bug. **Deferred**: left as-is; worth a
    guard only if this module's internal functions ever get a public, direct-call entry
    point.

13. **The "stable across tiers" headline claim slightly overstated consistency.**
    (`narrative-checker`) On the 15-query analyst tier specifically, hybrid and dense
    tie exactly on Recall@10 (both 0.800, BM25 at 0.867) rather than strictly
    ordering BM25 > hybrid > dense — true on every other metric and tier, but not that
    one cell. **Fixed**: reworded to state the tie explicitly rather than claim
    universal strict ordering.

## Verified sound (explicit passes from all four checkers)

- All eval metric formulas (`recall_at_k`, `precision_at_k`, `reciprocal_rank`,
  `ndcg_at_k`, `bootstrap_ci`) are correct and match their hand-worked test cases
  exactly — no off-by-one in the nDCG rank discount or IDCG cap.
- `find_chunk.py` is structurally incapable of leaking search results into gold
  labels — it imports only `config` and `ingest.parse`, never the retrieval/ranking
  modules.
- Spot-checked gold labels (both `analyst_gold.json` and several `heading_gold.json`
  entries) trace to real, current source text, not to search output.
- BM25/dense/hybrid are evaluated at the same K and the same gold queries; the pooled
  metric is a genuine per-query aggregation, not an average-of-averages.
- The two gold tiers are reported separately, never silently blended into one number.
- `content_hash()` idempotency holds under reordering, not just by construction, and
  was independently confirmed live (`make index` run twice, byte-identical hash).
- `Index.load` genuinely 503s (no traceback leak) on a tampered hash/pickle pair, for
  both `/health` and `/search`.
- `top_k` bounds and `mode` validation are real and enforced at the API layer, not
  decorative — confirmed with live boundary-value requests.
- Empty and empty-after-chunking inputs (blank notebook cells, header-only markdown
  sections) are dropped, never indexed as blank chunks.
- `/metrics` is genuinely live (real Prometheus counters/histograms after real
  traffic), not a stub — matching the README's disclosure exactly.
- CI's path filters are consistently scoped against the sibling `pm-bayes-pricer.yml`
  workflow's pattern.
- No loose use of "proves," "robust," "reliable," or unqualified "significant" found
  anywhere in the README; no causal claims drawn from correlational evidence.
- All chunk_ids in the current (post-fix) index are globally unique; zero collisions
  across both corpus projects.
- Notebook `cell_index` values were spot-checked against real `.ipynb` files and
  match true cell position exactly, including correct heading inheritance across a
  no-header code cell and a deliberate first-header choice in multi-header markdown
  cells.

# trading-research-rag

**Hybrid BM25 + LSA retrieval service over my own quant-research corpus — built and
CI-gated as a production retrieval service, not a chatbot demo.**

Every formula and every eval number here is derived from scratch (no `rank_bm25`,
no LangChain, no hosted vector DB) and checked against a hand-worked example or an
independently-labeled gold set, the same rule the rest of this repo holds itself to.

## See the results (2 minutes, nothing to install)

The corpus is `crypto-cointegration-signal` and `pm-bayes-pricer`'s own READMEs,
AUDIT.md/CLAUDE.md, configs and notebooks (324 chunks). A real query against the
running service:

```
$ curl "http://localhost:8010/search?q=kalman+filter+hedge+ratio&top_k=2"
{
  "query": "kalman filter hedge ratio", "mode": "hybrid", "index_hash": "d6549a1d06a5",
  "hits": [
    {"citation": "crypto-cointegration-signal/notebooks/04_backtest.ipynb (cell 4)",
     "section": "Kalman-filtered hedge ratio (train only)", "score": 0.0328, "rank": 1, ...},
    {"citation": "crypto-cointegration-signal/notebooks/04_backtest.ipynb (cell 5)",
     "score": 0.0318, "rank": 2, ...}
  ]
}
```

Full eval table: `make eval` (reproduces the table below from the committed gold sets
in `config/eval/`, no API keys or external services needed).

## Scope and limits

* **Tested:** retrieval quality against two gold tiers — 15 analyst questions I
  hand-labeled by reading the source files directly (never by looking at what the
  system itself retrieves, which would make the eval circular), and 153
  queries bootstrapped from section headings (an easier, weak-supervision tier,
  reported separately). Idempotent reindexing, API error paths, index/hash integrity.
* **Not tested:** behavior at a much larger corpus size (this is a few hundred
  chunks — brute-force cosine and in-memory BM25 are fine here and would not be at
  10k+ chunks), real concurrent production traffic, a neural embedding model as the
  dense leg (see "Design decisions").
* No live external calls anywhere in this project — everything runs offline against
  the committed corpus.

## Headline result — pooled Recall@10 (both gold tiers, 95% bootstrap CI)

| Mode | Recall@10 | MRR | nDCG@10 |
|---|---|---|---|
| **BM25 only** | **0.799 [0.757, 0.840]** | **0.907 [0.868, 0.943]** | **0.755 [0.721, 0.789]** |
| Hybrid (BM25 + LSA, RRF) | 0.773 [0.729, 0.816] | 0.861 [0.816, 0.902] | 0.714 [0.677, 0.750] |
| Dense (LSA) only | 0.751 [0.706, 0.794] | 0.775 [0.722, 0.825] | 0.659 [0.617, 0.697] |

**Plain BM25 beats the hybrid on this corpus.** This held across a deliberate
parameter sweep before I'd accept it as the answer rather than a bad default — run it
yourself with `make sweep` (committed, not just asserted): RRF `k` from 5 to 200
(hybrid Recall@10 stayed in 0.773–0.782, never reaching BM25's 0.799), and SVD
components from 20 to 150 (dense Recall@10 rose from 0.552 to 0.758 but still didn't
close the gap). My read: these queries are short and term-specific ("Kalman-filtered
hedge ratio"), a regime where exact lexical overlap already finds the right chunk, and
the LSA leg mostly adds topically-adjacent-but-wrong chunks that dilute the fused
ranking rather than rescuing a lexical miss. The build order (`trading-desk-agent`'s
tool-use layer) defaults to **BM25-only** for retrieval until a query mix actually
shows the hybrid earning its keep — see "Not yet done".

Per-tier breakdown (`make eval` prints both): BM25 leads hybrid and dense on every
metric in both tiers, except Recall@10 specifically on the 15-query analyst tier,
where hybrid and dense tie exactly with BM25 slightly ahead (0.867 vs. 0.800 vs.
0.800) — a small-N tie, not a reversal of the ranking.

## What running it against real data caught

* **A real chunk-id collision bug**: the original chunk-id scheme didn't include the
  repo name, so two different projects' `README.md` sections could silently collide
  on the same id if their heading/position happened to match — exactly the kind of
  bug the eval set and citation provenance depend on being impossible. Fixed by
  prefixing every id with its source repo.
* **A real mis-chunking bug, caught by the citation-provenance audit, not by inspection**:
  the naive line-based header regex misread a `# with the Kraken tick files available
  locally:` bash comment (column 0, inside a fenced code block in
  `pm-bayes-pricer/README.md`'s Quick Start) as a markdown header, silently splitting
  one section into two and shifting every later section's index. Confirmed by actually
  rebuilding the index after the fix: chunk count dropped from 325 to 324, exactly one
  spurious section. Fixed by tracking fence state and never matching headers inside a
  fenced block (`_iter_headers` in `chunk.py`); regression-tested in `test_chunk.py`.
* **The index could silently go stale while the service was running**, not just across
  restarts: the original `_load_index()` cached the loaded index for the lifetime of
  the process, so running `make index` against a live `make serve` would have zero
  effect until restart — directly contradicting the "a stale index can never silently
  serve queries" claim this project makes. Fixed: the API now re-checks the small
  on-disk sidecar hash on every request and only re-unpickles the index when it's
  actually changed.
* **Hybrid retrieval doesn't automatically beat lexical search** — see above. The
  instinct to default to "hybrid is strictly better" was wrong here, and only the
  parameter sweep (not a single run) made that a safe claim rather than a fluke.
* Gold labels built by eyeballing the system's own top results would have been
  circular (the eval would just confirm whatever the system already believed); every
  `analyst_gold.json` label was instead found independently via
  `python -m tradingrag.eval.find_chunk "<substring>"`, which never calls the
  retrieval/ranking code at all.

## Architecture

```
corpus (.md/.yaml/.ipynb) --chunk by header/cell--> provenance-tagged chunks
                                                            |
                                        +-------------------+-------------------+
                                        v                                       v
                               BM25 (from scratch)                  TF-IDF + truncated SVD (LSA)
                                        |                                       |
                                        +-------------------+-------------------+
                                                            v
                                          reciprocal rank fusion (rank, not score)
                                                            |
                                                            v
                                    content-hashed Index (pickle + sha256 sidecar)
                                                            |
                                                            v
                                     FastAPI /search, /health, /metrics (Prometheus)
```

## Quick start

```bash
make install   # editable install, dev + notebook extras
make index     # parse the corpus, build+save the hybrid index -> data/index/
make eval      # print the Recall@10/Precision@10/MRR/nDCG@10 table above
make serve     # FastAPI on :8010
make lint      # ruff check + format --check
make typecheck # mypy --strict
make test      # pytest (41 tests: chunking, bm25, dense, fusion, index, eval metrics, config, API)
make sweep     # reproduce the RRF-k / SVD-components ablation behind the headline finding
```

## Layout

| Path | Purpose |
|---|---|
| `src/tradingrag/ingest/` | Markdown/notebook chunking by header/cell, with full provenance |
| `src/tradingrag/retrieval/` | `bm25.py` (Okapi BM25, ATIRE IDF), `dense.py` (TF-IDF+SVD), `fusion.py` (RRF), `index.py` (build/save/load, content hash) |
| `src/tradingrag/eval/` | `metrics.py` (recall/precision/MRR/nDCG/bootstrap CI), `gold.py`, `find_chunk.py` (independent gold-label lookup), `run_eval.py`, `generate_heading_gold.py` |
| `config/eval/` | `analyst_gold.json` (15 hand-labeled), `heading_gold.json` (153 bootstrapped), `baseline_metrics.json` (CI regression gate) |
| `src/tradingrag/api.py` | FastAPI `/search`, `/health`, `/metrics` |
| `tests/` | 41 tests: hand-worked BM25/RRF/nDCG examples, chunking provenance (incl. a cross-repo chunk-id collision regression and a fenced-code-block header regression), idempotent hashing, eval-set validity, API routing/validation/staleness |

## Design decisions

* **LSA, not a neural embedding model, for the dense leg.** At a few hundred chunks,
  a GPU/API-dependent embedding model buys nothing a reviewer could verify by
  re-running `make eval` offline, and it would hide the "why did this rank here"
  reasoning LSA keeps transparent (a weighted sum of term co-occurrence
  directions). `DenseIndex` is a contained interface — swapping in
  `sentence-transformers` later is a local change, not a rearchitecture.
* **Reciprocal rank fusion, not a weighted score blend.** BM25 and cosine-similarity
  scores live on incomparable scales; fusing by rank position avoids letting
  whichever method happens to produce larger raw numbers dominate.
* **Content-hashed index, hash-checked on load.** `Index.load` refuses to serve a
  pickle whose sidecar hash doesn't match it — a corruption/tamper check on the saved
  artifact itself, not a corpus-freshness guarantee (see "Not yet done"). The API
  layer re-reads the small sidecar hash file on every request and only re-unpickles
  the (larger) index when it's actually changed, so running `make index` against a
  *live* `make serve` process is picked up on the next request with no restart
  needed — this was originally a `/health`-only, first-load-only check (a real gap
  the audit caught: a rebuilt index was silently ignored by an already-running
  process) and is now re-verified on every call.
* **Chunk = one markdown section or one notebook cell**, not a sliding token
  window — so every citation is something a human would recognise as "the thing
  that answers this" when it's quoted back.

## Not yet done

Docker/Postgres/Prometheus/Grafana observability stack (the API exposes Prometheus
metrics directly at `/metrics`, but the dashboarded stack `pm-bayes-pricer` runs
isn't wired up here yet); a neural-embedding dense leg to test whether it closes the
gap to BM25 that LSA didn't; behavior at corpus sizes beyond a few hundred chunks;
**no corpus-drift detection** — the content hash only catches a corrupted/tampered
index artifact, not a source file in `edwardcrook/` changing after the last
`make index` run (there's no file-mtime or source-hash check against the live
corpus, only against the saved pickle).

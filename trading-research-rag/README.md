# trading-research-rag

Hybrid BM25 + LSA search over my own quant-research corpus. Built like a real
service (tests, CI, eval gate) not a chatbot demo. Everything from scratch
(no rank_bm25, no LangChain, no vector DB), no API key needed anywhere.

## try it

```
$ curl "http://localhost:8010/search?q=kalman+filter+hedge+ratio&top_k=2"
{"hits": [{"citation": "crypto-cointegration-signal/notebooks/04_backtest.ipynb (cell 4)", ...}]}
```

`make eval` reproduces the table below offline, no services needed.

## headline result: BM25 beats the hybrid

| Mode | Recall@10 | MRR | nDCG@10 |
|---|---|---|---|
| **BM25 only** | **0.799** | **0.907** | **0.755** |
| Hybrid (BM25+LSA) | 0.773 | 0.861 | 0.714 |
| Dense (LSA) only | 0.751 | 0.775 | 0.659 |

Plain lexical search wins on this corpus. Checked with a real sweep
(`make sweep`), not a bad default — RRF k 5-200 and SVD dims 20-150 never got
hybrid above BM25. Guess: queries here are short and specific ("Kalman hedge
ratio"), exact word match already wins, LSA just adds noise.

## bugs the audit caught

- chunk ids collided across projects (no repo prefix) — fixed
- bash comment inside a code fence got read as a markdown header, corrupting
  real chunks (325 → 324 after fix) — fixed, fence-aware now
- index could go stale while the service kept running (only checked hash on
  first load) — fixed, re-checks every request
- gold labels built by eyeballing search output would be circular — built
  independently instead (`find_chunk.py`, never touches search code)

full writeup in `AUDIT.md` — four independent reviewers, not one self-check.

## how it works

```
corpus (.md/.ipynb) -> chunk by header/cell -> [BM25, LSA] -> RRF fuse
  -> content-hashed index -> FastAPI /search, /health, /metrics
```

## run it

```bash
make install && make index && make eval && make serve
make test      # 41 tests
make sweep     # reproduce the ablation above
```

## why LSA not a neural embedder

Transparent, no GPU, fully offline-reproducible at this corpus size (few
hundred chunks). Swappable later behind `DenseIndex` if it matters.

## not done

Docker/Grafana stack (metrics already on `/metrics`); neural embedding
option; corpus-drift detection (hash only catches a corrupted index file,
not the source docs changing underneath it).

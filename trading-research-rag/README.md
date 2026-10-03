# trading-research-rag

Hybrid BM25 + LSA search over my own quant-research corpus. Built like a real
service (tests, CI, eval gate), not a chatbot demo. Everything from scratch
(no rank_bm25, no LangChain, no vector DB). No API key needed anywhere.

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

Plain lexical search wins on this corpus. I checked it wasn't just a bad
default with a real sweep (`make sweep`): RRF k 5-200 and SVD dims 20-150,
hybrid never got above BM25. My guess: queries here are short and specific
("Kalman hedge ratio"), exact word match already wins, LSA mostly adds noise.

## bugs the audit caught

- chunk ids collided across projects (no repo prefix). Fixed.
- a bash comment inside a code fence got read as a markdown header, which
  corrupted real chunks (325 dropped to 324 after the fix). Fixed, the
  chunker is fence-aware now.
- the index could go stale while the service kept running, since it only
  checked the hash on first load. Fixed, it re-checks every request.
- gold labels built by eyeballing search output would be circular, so I
  built them independently instead (`find_chunk.py`, never touches search code).

Full writeup in `AUDIT.md`: four independent reviewers, no self-review.

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

## why LSA, not a neural embedder

Transparent, no GPU, fully offline-reproducible at this corpus size (a few
hundred chunks). Swappable later behind `DenseIndex` if it ever matters.

## not done

Docker/Grafana stack (metrics already on `/metrics`); a neural embedding
option; corpus-drift detection (the hash catches a corrupted index file, but
can't tell if the source docs changed underneath it).

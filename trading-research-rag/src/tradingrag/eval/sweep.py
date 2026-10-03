"""Reproduces the parameter sweep behind the README's "BM25 beats hybrid" claim.

Run via `make sweep`. Committed as a real script, not just asserted in prose,
so the claim that hybrid's loss to BM25-only holds across a range of RRF `k`
and SVD component counts (rather than being an artifact of one bad default)
is independently re-runnable by anyone, not just trusted on the author's word.
"""

from __future__ import annotations

from tradingrag.config import get_settings
from tradingrag.eval.gold import load_gold_json
from tradingrag.eval.run_eval import CONFIG_DIR, evaluate, summarize
from tradingrag.ingest.parse import load_corpus
from tradingrag.retrieval.index import Index

SVD_SWEEP = [20, 50, 100, 150]
RRF_K_SWEEP = [5, 10, 30, 60, 100, 200]


def main() -> None:
    settings = get_settings()
    chunks = load_corpus(settings.corpus_roots, settings.corpus_globs)
    all_queries = load_gold_json(CONFIG_DIR / "analyst_gold.json", tier="analyst") + load_gold_json(
        CONFIG_DIR / "heading_gold.json", tier="heading"
    )

    print("--- dense (LSA) pooled recall@10 vs. svd_components ---")
    for svd_n in SVD_SWEEP:
        index = Index(chunks, svd_components=svd_n, rrf_k=settings.rrf_k)
        recall = summarize(evaluate(index, all_queries, "dense"))["recall_at_10"]["mean"]
        print(f"  svd_components={svd_n:4d}  recall@10={recall:.4f}")

    print("\n--- hybrid pooled recall@10 vs. rrf_k (svd_components fixed at default) ---")
    index = Index(chunks, svd_components=settings.svd_components, rrf_k=settings.rrf_k)
    for rrf_k in RRF_K_SWEEP:
        index.rrf_k = rrf_k
        recall = summarize(evaluate(index, all_queries, "hybrid"))["recall_at_10"]["mean"]
        print(f"  rrf_k={rrf_k:4d}  recall@10={recall:.4f}")

    bm25_recall = summarize(evaluate(index, all_queries, "bm25"))["recall_at_10"]["mean"]
    print(f"\nbm25-only pooled recall@10 (no sweep needed) = {bm25_recall:.4f}")


if __name__ == "__main__":
    main()

"""Entry point for `make index`: parse the corpus and persist a fresh Index."""

from __future__ import annotations

from tradingrag.config import get_settings
from tradingrag.ingest.parse import load_corpus
from tradingrag.retrieval.index import Index


def main() -> None:
    settings = get_settings()
    chunks = load_corpus(settings.corpus_roots, settings.corpus_globs)
    if not chunks:
        raise SystemExit(
            f"no chunks found under {settings.corpus_roots} — check corpus_roots in config.py"
        )
    index = Index(chunks, svd_components=settings.svd_components, rrf_k=settings.rrf_k)
    index.save(settings.index_dir)
    n_roots = len(settings.corpus_roots)
    print(f"indexed {len(chunks)} chunks from {n_roots} roots -> {index.hash[:12]}")


if __name__ == "__main__":
    main()

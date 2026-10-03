"""Dev utility for building/extending the gold set: find which chunk, as the
canonical ingestion pipeline segments it, contains a given substring.

Deliberately independent of the retrieval system (BM25/dense/index) — gold
labels must come from reading the corpus directly, never from "whatever the
system already ranks first," or the eval would just be checking the system
against itself.

Usage: python -m tradingrag.eval.find_chunk "calendar-grid backward-fill"
"""

from __future__ import annotations

import sys

from tradingrag.config import get_settings
from tradingrag.ingest.parse import load_corpus


def main() -> None:
    substring = sys.argv[1]
    settings = get_settings()
    chunks = load_corpus(settings.corpus_roots, settings.corpus_globs)
    matches = [c for c in chunks if substring.lower() in c.text.lower()]
    if not matches:
        print(f"no chunk contains: {substring!r}")
        return
    for chunk in matches:
        print(f"{chunk.chunk_id}")
        print(f"  citation: {chunk.citation()}")
        print(f"  text: {chunk.text.strip()[:160]!r}")


if __name__ == "__main__":
    main()

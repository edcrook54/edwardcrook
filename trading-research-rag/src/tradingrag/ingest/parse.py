from __future__ import annotations

from pathlib import Path

from tradingrag.ingest.chunk import Chunk, chunk_markdown, chunk_notebook


def _iter_corpus_files(corpus_roots: list[Path], globs: list[str]) -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    for root in corpus_roots:
        for pattern in globs:
            for path in sorted(root.glob(pattern)):
                if path.is_file() and path not in seen:
                    seen.add(path)
                    files.append(path)
    return files


def load_corpus(corpus_roots: list[Path], globs: list[str]) -> list[Chunk]:
    """Parse every matching file under `corpus_roots` into provenance-tagged chunks."""
    chunks: list[Chunk] = []
    for path in _iter_corpus_files(corpus_roots, globs):
        if path.suffix == ".ipynb":
            chunks.extend(chunk_notebook(path, corpus_roots))
        elif path.suffix in {".md", ".yaml", ".yml"}:
            chunks.extend(chunk_markdown(path, corpus_roots))
    return chunks

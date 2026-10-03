"""Chunking rules: one chunk per markdown header section, one per notebook cell.

Keeping the unit this coarse (a whole section / a whole cell, not a sliding
token window) means every chunk is something a human would actually
recognise as "the thing that answers this question" when citing it back,
which matters more here than squeezing retrieval metrics.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from re import Match

import nbformat

_HEADER_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FENCE_RE = re.compile(r"^(```|~~~)")


def _iter_headers(lines: list[str]) -> Iterator[Match[str] | None]:
    """Yields a header match per line, or None — but never matches inside a
    fenced code block, so a line like `# comment at column 0` in a bash
    snippet isn't misread as a markdown header (a real bug this once was).
    """
    in_fence = False
    for line in lines:
        if _FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            yield None
            continue
        yield None if in_fence else _HEADER_RE.match(line)


@dataclass(frozen=True)
class Chunk:
    """A retrievable unit of text with full provenance back to its source."""

    chunk_id: str
    text: str
    source_repo: str
    source_path: str
    section: str
    cell_type: str = "markdown"
    cell_index: int | None = None

    def citation(self) -> str:
        loc = f"cell {self.cell_index}" if self.cell_index is not None else self.section
        return f"{self.source_repo}/{self.source_path} ({loc})"


def _repo_name(path: Path, corpus_roots: list[Path]) -> str:
    for root in corpus_roots:
        if path.is_relative_to(root):
            return root.name
    return path.parent.name


def chunk_markdown(path: Path, corpus_roots: list[Path]) -> list[Chunk]:
    text = path.read_text(encoding="utf-8")
    repo = _repo_name(path, corpus_roots)
    rel = _relative_path(path, corpus_roots)

    lines = text.splitlines()
    sections: list[tuple[str, list[str]]] = [("(preamble)", [])]
    for line, match in zip(lines, _iter_headers(lines), strict=True):
        if match:
            sections.append((match.group(2).strip(), []))
        else:
            sections[-1][1].append(line)

    chunks: list[Chunk] = []
    for idx, (heading, body_lines) in enumerate(sections):
        body = "\n".join(body_lines).strip()
        if not body:
            continue
        chunks.append(
            Chunk(
                chunk_id=f"{repo}/{rel}::{idx}::{heading}",
                text=f"{heading}\n{body}" if heading != "(preamble)" else body,
                source_repo=repo,
                source_path=rel,
                section=heading,
            )
        )
    return chunks


def chunk_notebook(path: Path, corpus_roots: list[Path]) -> list[Chunk]:
    nb = nbformat.read(path, as_version=4)  # type: ignore[no-untyped-call] # nbformat has no full stubs
    repo = _repo_name(path, corpus_roots)
    rel = _relative_path(path, corpus_roots)

    chunks: list[Chunk] = []
    current_heading = "(untitled)"
    for idx, cell in enumerate(nb.cells):
        source = cell.get("source", "").strip()
        if not source:
            continue
        if cell.cell_type == "markdown":
            matches = _iter_headers(source.splitlines())
            first_header = next((m.group(2).strip() for m in matches if m), None)
            if first_header:
                current_heading = first_header
        chunks.append(
            Chunk(
                chunk_id=f"{repo}/{rel}::{idx}",
                text=source,
                source_repo=repo,
                source_path=rel,
                section=current_heading,
                cell_type=cell.cell_type,
                cell_index=idx,
            )
        )
    return chunks


def _relative_path(path: Path, corpus_roots: list[Path]) -> str:
    for root in corpus_roots:
        if path.is_relative_to(root):
            return str(path.relative_to(root))
    return str(path)

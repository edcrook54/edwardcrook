"""Bootstraps a large, cheap-but-honest gold tier from section headings.

For every non-trivial heading, the heading text itself becomes a query and
every chunk that shares that exact heading is relevant. This is weak
supervision, not independent human judgement: a heading that paraphrases its
own content is an easier query than a real analyst question would be, so
this tier's numbers should read as an upper bound, not the whole story — see
`config/eval/analyst_gold.json` for the harder, independently hand-labeled
tier, and the README's "Scope and limits" section for why both exist.
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from tradingrag.config import get_settings
from tradingrag.ingest.parse import load_corpus

EXCLUDED_HEADINGS = {"(preamble)", "(untitled)"}
MIN_HEADING_WORDS = 2
OUTPUT_PATH = Path(__file__).resolve().parents[3] / "config" / "eval" / "heading_gold.json"


def generate() -> list[dict[str, object]]:
    settings = get_settings()
    chunks = load_corpus(settings.corpus_roots, settings.corpus_globs)

    by_heading: dict[str, list[str]] = defaultdict(list)
    for chunk in chunks:
        heading = chunk.section.strip()
        if heading in EXCLUDED_HEADINGS or len(heading.split()) < MIN_HEADING_WORDS:
            continue
        by_heading[heading].append(chunk.chunk_id)

    return [
        {"query": heading, "relevant_chunk_ids": sorted(chunk_ids)}
        for heading, chunk_ids in sorted(by_heading.items())
    ]


def main() -> None:
    gold = generate()
    OUTPUT_PATH.write_text(json.dumps(gold, indent=2) + "\n")
    print(f"wrote {len(gold)} heading-derived gold queries -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()

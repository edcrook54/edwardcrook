from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class GoldQuery:
    query: str
    relevant_chunk_ids: list[str]
    tier: str


def load_gold_json(path: Path, tier: str) -> list[GoldQuery]:
    data = json.loads(path.read_text())
    return [
        GoldQuery(query=item["query"], relevant_chunk_ids=item["relevant_chunk_ids"], tier=tier)
        for item in data
    ]


def load_gold_yaml(path: Path, tier: str) -> list[GoldQuery]:
    data = yaml.safe_load(path.read_text())
    return [
        GoldQuery(query=item["query"], relevant_chunk_ids=item["relevant_chunk_ids"], tier=tier)
        for item in data
    ]

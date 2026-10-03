"""Settings for the corpus to ingest and where the built index lives.

Corpus roots must resolve correctly in two different layouts, not just the
one on this machine: during development this project lives in the outer
portfolio folder and reaches into a nested `edwardcrook/` checkout, but once
published it moves to live *inside* `edwardcrook/` as a direct sibling of
`crypto-cointegration-signal` and `pm-bayes-pricer` — which is also the only
layout that exists at all in CI or on a clone of the public repo, since the
outer folder's `edwardcrook/` is a separate git repository (an empty gitlink
on checkout, not real content). `_resolve_edwardcrook_root` tries the
published (direct-sibling) layout first and only falls back to the nested
dev layout if that fails, so the same code works unmodified in both places.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_edwardcrook_root(project_root: Path = PROJECT_ROOT) -> Path:
    direct_sibling = project_root.parent  # published layout: inside edwardcrook/
    if (direct_sibling / "crypto-cointegration-signal").is_dir():
        return direct_sibling
    nested = project_root.parent / "edwardcrook"  # dev layout: outer portfolio folder
    if (nested / "crypto-cointegration-signal").is_dir():
        return nested
    raise FileNotFoundError(
        "could not find crypto-cointegration-signal as a sibling of this project "
        f"(tried {direct_sibling} and {nested}) - is this project checked out "
        "in the expected location relative to the other showcase projects?"
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TRADINGRAG_")

    corpus_roots: list[Path] = Field(
        default_factory=lambda: [
            _resolve_edwardcrook_root() / "crypto-cointegration-signal",
            _resolve_edwardcrook_root() / "pm-bayes-pricer",
        ]
    )
    corpus_globs: list[str] = Field(
        default_factory=lambda: ["*.md", "*.yaml", "*.yml", "notebooks/*.ipynb"]
    )
    index_dir: Path = PROJECT_ROOT / "data" / "index"
    svd_components: int = 100
    rrf_k: int = 60


def get_settings() -> Settings:
    return Settings()

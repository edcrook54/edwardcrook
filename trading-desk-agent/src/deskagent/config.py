"""Settings: locations of the sibling showcase projects this agent's tools
reach into, and agent-loop parameters.

Same dual-layout resolution as `trading-research-rag`/`llm-news-signal`'s
`config.py` - this project also needs to work both from the outer portfolio
dev folder and once published inside `edwardcrook/`.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _resolve_showcase_root(project_root: Path = PROJECT_ROOT) -> Path:
    direct_sibling = project_root.parent  # published layout: inside edwardcrook/
    if (direct_sibling / "pm-bayes-pricer").is_dir():
        return direct_sibling
    nested = project_root.parent / "edwardcrook"  # dev layout: outer portfolio folder
    if (nested / "pm-bayes-pricer").is_dir():
        return nested
    raise FileNotFoundError(
        f"could not find pm-bayes-pricer as a sibling of this project "
        f"(tried {direct_sibling} and {nested})"
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DESKAGENT_")

    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "DESKAGENT_ANTHROPIC_API_KEY"),
    )
    model: str = "claude-sonnet-5"
    max_iterations: int = 8
    tool_timeout_seconds: int = 60

    search_corpus_url: str = "http://127.0.0.1:8010/search"

    showcase_root: Path = Field(default_factory=_resolve_showcase_root)

    transcript_dir: Path = PROJECT_ROOT / "data" / "transcripts"

    # get_file is restricted to these roots (relative to showcase_root) -
    # nothing outside them, no path traversal.
    allowed_file_roots: tuple[str, ...] = (
        "crypto-cointegration-signal",
        "pm-bayes-pricer",
        "trading-research-rag",
        "llm-news-signal",
    )


def get_settings() -> Settings:
    return Settings()

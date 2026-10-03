"""Settings: where the FOMC statement data and cached price bars live.

Corpus/bar roots resolve correctly whether this project is in the outer
portfolio dev folder or published inside `edwardcrook/` as a direct sibling
of `pm-bayes-pricer` — same dual-layout trick as `trading-research-rag`'s
`config.py`, which this is deliberately consistent with.
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
        "could not find pm-bayes-pricer as a sibling of this project "
        f"(tried {direct_sibling} and {nested})"
    )


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LLMSIGNAL_")

    # Accepts the standard ANTHROPIC_API_KEY (what everyone already has set for
    # the SDK) as well as our own namespaced LLMSIGNAL_ANTHROPIC_API_KEY.
    anthropic_api_key: str | None = Field(
        default=None,
        validation_alias=AliasChoices("ANTHROPIC_API_KEY", "LLMSIGNAL_ANTHROPIC_API_KEY"),
    )
    model: str = "claude-haiku-4-5-20251001"

    fomc_statements_path: Path = PROJECT_ROOT / "data" / "fomc_statements.json"
    extractions_path: Path = PROJECT_ROOT / "data" / "extractions.json"
    reliability_labels_path: Path = PROJECT_ROOT / "data" / "reliability_labels.json"
    recorded_responses_path: Path = PROJECT_ROOT / "data" / "recorded_responses.json"

    bar_paths: dict[str, Path] = Field(
        default_factory=lambda: {
            asset: _resolve_showcase_root() / "pm-bayes-pricer" / "data" / "bars" / fname
            for asset, fname in [("BTC", "XBT_1m.parquet"), ("ETH", "ETH_1m.parquet")]
        }
    )

    horizons_hours: list[int] = Field(default_factory=lambda: [1, 24, 168])
    cost_bps: float = 10.0
    oos_fraction: float = 0.3
    score_threshold: float = 0.2


def get_settings() -> Settings:
    return Settings()

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from environment variables (or a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PMQ_", extra="ignore")

    database_url: str = "postgresql://pmq:pmq@localhost:5432/pmq"
    fred_api_key: str | None = None
    poll_interval_seconds: int = Field(default=60, ge=5)
    http_timeout_seconds: float = Field(default=10.0, gt=0)
    # Kraken tick exports (headerless CSVs) live outside the repo: they are ~45 GB.
    ticks_dir: Path = Path("../TimeAndSales_Combined")
    bars_dir: Path = Path("data/bars")
    # Live pricer
    asset: str = "XBT"
    model_path: Path = Path("models/har_XBT.json")
    metrics_port: int = 9108
    max_spot_age_seconds: int = 3 * 3600  # newest completed hourly candle must be this recent


@lru_cache
def get_settings() -> Settings:
    return Settings()

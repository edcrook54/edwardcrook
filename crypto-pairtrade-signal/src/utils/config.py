"""
Config loader - reads config/config.yaml and .env.
"""

from pathlib import Path
from dotenv import load_dotenv
import yaml


class ConfigLoader:
    """Loads project configuration from a YAML file, with .env overrides picked up as a side effect."""

    def __init__(self, path: str | Path = "config/config.yaml"):
        self.path = Path(path)

    def load(self) -> dict:
        load_dotenv()
        with open(self.path, "r") as f:
            return yaml.safe_load(f)


def load_config(path: str | Path = "config/config.yaml") -> dict:
    """Functional convenience wrapper kept for notebook/script ergonomics."""
    return ConfigLoader(path).load()

import pytest
from pydantic import ValidationError

from pmq.config import Settings


def test_defaults_point_at_local_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("PMQ_DATABASE_URL", raising=False)
    settings = Settings(_env_file=None)
    assert settings.database_url.startswith("postgresql://")
    assert settings.poll_interval_seconds == 60


def test_env_overrides_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PMQ_POLL_INTERVAL_SECONDS", "120")
    assert Settings(_env_file=None).poll_interval_seconds == 120


def test_poll_interval_floor_protects_venue_rate_limits() -> None:
    with pytest.raises(ValidationError):
        Settings(_env_file=None, poll_interval_seconds=1)

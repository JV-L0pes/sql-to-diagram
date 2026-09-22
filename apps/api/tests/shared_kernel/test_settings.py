import pytest
from pydantic import ValidationError

from src.shared_kernel.settings import Settings, normalize_database_url


@pytest.mark.parametrize(
    ("raw_url", "expected"),
    [
        (
            "postgresql+psycopg://user:pw@localhost/db",
            "postgresql+psycopg://user:pw@localhost/db",
        ),
        (
            "postgresql://user:pw@ep-example.neon.tech/db",
            "postgresql+psycopg://user:pw@ep-example.neon.tech/db",
        ),
        (
            "postgres://user:pw@ep-example.neon.tech/db",
            "postgresql+psycopg://user:pw@ep-example.neon.tech/db",
        ),
    ],
)
def test_normalize_database_url(raw_url: str, expected: str) -> None:
    assert normalize_database_url(raw_url) == expected


def test_settings_normalizes_bare_postgresql_url(monkeypatch: pytest.MonkeyPatch) -> None:
    """Simulates Vercel's Neon-injected DATABASE_URL, which has no driver suffix."""
    monkeypatch.setenv("DATABASE_URL", "postgresql://user:pw@ep-example.neon.tech/db")
    monkeypatch.setenv("JWT_SECRET", "test-secret-at-least-32-characters-long")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.database_url == "postgresql+psycopg://user:pw@ep-example.neon.tech/db"


def test_settings_rejects_a_short_jwt_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite://")
    monkeypatch.setenv("JWT_SECRET", "too-short")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]

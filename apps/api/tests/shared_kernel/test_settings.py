import pytest

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
    monkeypatch.setenv("JWT_SECRET", "test-secret")
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    assert settings.database_url == "postgresql+psycopg://user:pw@ep-example.neon.tech/db"

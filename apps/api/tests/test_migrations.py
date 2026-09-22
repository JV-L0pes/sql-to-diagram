from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from alembic import command
from src.shared_kernel.settings import get_settings

API_ROOT = Path(__file__).resolve().parents[1]


def _alembic_config() -> Config:
    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))
    return config


def test_alembic_upgrade_head_runs_on_sqlite(tmp_path, monkeypatch):
    """Local/dev databases and the smoke-test path use SQLite; migrations must not crash."""
    db_path = tmp_path / "migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()

    try:
        command.upgrade(_alembic_config(), "head")

        engine = create_engine(f"sqlite:///{db_path}")
        assert {"users", "projects", "refresh_tokens"} <= set(inspect(engine).get_table_names())
    finally:
        get_settings.cache_clear()


def test_email_normalization_upgrade_lowercases_existing_rows(tmp_path, monkeypatch):
    """Rows created before email normalization must not survive as duplicate-case accounts."""
    db_path = tmp_path / "email-migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{db_path}")

    try:
        command.upgrade(_alembic_config(), "f3a9c2d41b57")
        with engine.begin() as connection:
            connection.execute(
                text(
                    "INSERT INTO users (id, email, password_hash, created_at) "
                    "VALUES ('u1', 'Mixed@Example.COM', 'h', CURRENT_TIMESTAMP)"
                )
            )

        command.upgrade(_alembic_config(), "head")

        with engine.connect() as connection:
            email = connection.execute(text("SELECT email FROM users WHERE id = 'u1'")).scalar_one()
        assert email == "mixed@example.com"
    finally:
        engine.dispose()
        get_settings.cache_clear()

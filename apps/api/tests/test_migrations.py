from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, inspect

from alembic import command
from src.shared_kernel.settings import get_settings

API_ROOT = Path(__file__).resolve().parents[1]


def test_alembic_upgrade_head_runs_on_sqlite(tmp_path, monkeypatch):
    """Local/dev databases and the smoke-test path use SQLite; migrations must not crash."""
    db_path = tmp_path / "migration.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()

    config = Config(str(API_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(API_ROOT / "alembic"))

    try:
        command.upgrade(config, "head")

        engine = create_engine(f"sqlite:///{db_path}")
        assert {"users", "projects", "refresh_tokens"} <= set(inspect(engine).get_table_names())
    finally:
        get_settings.cache_clear()

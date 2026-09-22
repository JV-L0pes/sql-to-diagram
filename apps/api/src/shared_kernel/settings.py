from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(raw_url: str) -> str:
    """Ensure the URL always requests the psycopg (v3) driver.

    Local `.env` files and CI already use `postgresql+psycopg://`, but
    Vercel's Neon-integration-injected `DATABASE_URL` has no driver suffix
    (`postgresql://...` or `postgres://...`), which would otherwise make
    SQLAlchemy default to psycopg2 in production only. Normalizing here
    means the same driver (`psycopg[binary]`) is used everywhere.
    """
    if raw_url.startswith("postgresql+"):
        return raw_url
    if raw_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw_url[len("postgresql://") :]
    if raw_url.startswith("postgres://"):
        return "postgresql+psycopg://" + raw_url[len("postgres://") :]
    return raw_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str = Field(min_length=32)
    cors_allow_origins: list[str] = ["http://localhost:5173"]

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, value: str) -> str:
        return normalize_database_url(value)


def get_settings() -> Settings:
    return Settings()

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    cors_allow_origins: list[str] = ["http://localhost:5173"]


def get_settings() -> Settings:
    return Settings()

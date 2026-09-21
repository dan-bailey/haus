from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Haus"
    app_version: str = "0.1.0"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    database_url: str = "sqlite:///./data/haus.db"
    timezone: str = "America/Chicago"
    household_hostname: str = "haus.home.arpa"
    media_dir: str = "data/media"
    session_secret: str = "development-only-change-this-secret"
    google_client_id: str = ""
    google_client_secret: str = ""

    model_config = SettingsConfigDict(env_prefix="HAUS_", env_file=".env")


@lru_cache
def get_settings() -> Settings:
    return Settings()
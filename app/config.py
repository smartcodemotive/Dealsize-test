"""Application configuration from environment."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql+asyncpg://assessment:assessment@localhost:5432/events_db"
    redis_url: str = "redis://localhost:6380"
    provider_a_api_key: str = "test-key-a"
    provider_b_api_key: str = "test-key-b"
    log_level: str = "INFO"
    env: str = "development"


settings = Settings()

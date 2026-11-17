from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://fintech:fintech@localhost:5432/fintech"
    test_database_url: str = (
        "postgresql+asyncpg://fintech:fintech@localhost:5432/fintech_test"
    )
    app_env: str = "development"

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

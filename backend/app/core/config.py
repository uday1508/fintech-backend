from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://fintech:fintech@localhost:5432/fintech"
    test_database_url: str = (
        "postgresql+asyncpg://fintech:fintech@localhost:5432/fintech_test"
    )
    app_env: str = "development"
    jwt_secret_key: str = "local-development-secret-change-before-deploy"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7

    @model_validator(mode="after")
    def validate_auth_settings(self) -> "Settings":
        if self.access_token_expire_minutes != 15:
            raise ValueError("Access tokens must expire after 15 minutes")
        if self.refresh_token_expire_days < 1:
            raise ValueError("Refresh token lifetime must be at least one day")
        if self.app_env.lower() in {"production", "prod"} and (
            len(self.jwt_secret_key) < 32
            or self.jwt_secret_key
            in {
                "local-development-secret-change-before-deploy",
                "replace-with-a-random-secret-at-least-32-characters-long",
            }
        ):
            raise ValueError("Set a unique JWT_SECRET_KEY of at least 32 characters in production")
        return self

    model_config = SettingsConfigDict(
        env_file=Path(__file__).resolve().parents[2] / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

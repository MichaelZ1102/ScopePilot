"""Application configuration."""
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import model_validator
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(extra="ignore")

    app_name: str = "ScopePilot"
    debug: bool = False
    database_url: str = "postgresql+asyncpg://localhost:5432/scopepilot"
    secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440  # 24h
    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://localhost:8000",
    ]

    # Jira defaults (override per workspace)
    jira_url: Optional[str] = None
    jira_email: Optional[str] = None
    jira_api_token: Optional[str] = None

    @model_validator(mode="after")
    def _validate_secret_key(self):
        if self.secret_key == "change-me-in-production":
            raise ValueError(
                "secret_key must be changed from the default value. "
                "Set the SECRET_KEY environment variable to a secure random value."
            )
        return self


settings = Settings()

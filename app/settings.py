"""Application settings loaded from environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = ""  # Set via DATABASE_URL env var or .env file

    # CRZ Export
    crz_export_base_url: str = "https://www.crz.gov.sk/export"
    crz_rolling_window_days: int = 90
    crz_rate_limit_day_seconds: float = 2.0
    crz_rate_limit_night_seconds: float = 0.4

    # Storage
    raw_data_dir: Path = Path("data/raw")
    sample_data_dir: Path = Path("data/sample")

    # App
    app_env: str = "development"
    log_level: str = "INFO"
    sql_echo: bool = False

    @property
    def base_dir(self) -> Path:
        return Path(__file__).parent.parent


settings = Settings()

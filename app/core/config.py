"""Runtime configuration. Secrets come from the environment, never from source code."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "QadamMetrics"
    environment: str = "development"
    database_url: str = "sqlite:///./data/qadammetrics.db"
    auto_create_tables: bool = True
    api_key: str | None = Field(default=None, alias="QM_API_KEY")
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.0-flash"
    gemini_timeout_seconds: float = 45.0
    cors_origins: str = "*"
    max_upload_mb: int = 32
    data_dir: str = "./data"
    log_level: str = "INFO"
    log_row_payloads: bool = False

    @field_validator("api_key", "gemini_api_key", mode="before")
    @classmethod
    def blank_is_none(cls, value: object) -> object:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def data_path(self) -> Path:
        return Path(self.data_dir)

    @property
    def ai_configured(self) -> bool:
        return bool(self.gemini_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()

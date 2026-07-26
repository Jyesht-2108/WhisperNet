"""
WhisperNet Backend — Application Configuration

Central configuration using Pydantic Settings. All values are loaded
from environment variables (or .env file via docker-compose).
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── App Metadata ──
    APP_NAME: str = "WhisperNet Backend"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    LOG_LEVEL: str = "info"

    # ── OpenAI Configuration ──
    OPENAI_API_KEY: str = "sk-placeholder"

    # ── Databricks Configuration ──
    DATABRICKS_ENDPOINT_URL: str = "https://placeholder.cloud.databricks.com"
    DATABRICKS_API_TOKEN: str = "dapi-placeholder"
    DATABRICKS_HOST: str = ""
    DATABRICKS_SQL_HTTP_PATH: str = ""
    USE_MOCK_DATABRICKS: bool = True

    # ── CORS ──
    CORS_ORIGINS: str = "http://localhost:3000,http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse comma-separated CORS origins into a list."""
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = {
        "env_file": str(Path(__file__).parent.parent / ".env"),
        "env_file_encoding": "utf-8",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """Cached settings singleton to avoid re-reading env on every request."""
    return Settings()

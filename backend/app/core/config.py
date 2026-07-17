"""Application settings.

This is the only place in the backend that reads the environment. Everything
else receives settings as an argument, which is what makes it testable — a
module that reaches for os.environ on import cannot be tested without one.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"

    # Async driver, so the scheme is postgresql+psycopg:// and not postgresql://.
    # Compose builds this from the POSTGRES_* variables; see docker-compose.yml.
    database_url: str

    # Comma-separated rather than a JSON list: pydantic-settings parses list[str]
    # from the environment as JSON, which makes the obvious value silently wrong.
    cors_origins: str = "http://localhost:5173"

    document_storage_path: str = "/var/lib/contractul/documents"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_development(self) -> bool:
        return self.environment == "development"


@lru_cache
def get_settings() -> Settings:
    """Cached so the environment is read once per process."""
    return Settings()  # type: ignore[call-arg]

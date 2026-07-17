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

    session_cookie_name: str = "contractul_session"

    # Secure cookies are HTTPS-only, so this must be false for local http://
    # development and true everywhere else. It is a setting rather than derived
    # from `environment` so that a staging box on HTTPS can have it on without
    # pretending to be production.
    cookie_secure: bool = False

    # Whether to read the client IP from X-Forwarded-For instead of the socket
    # peer. OFF by default and it must stay off until a reverse proxy sits in
    # front: with no proxy, the header is entirely attacker-controlled and
    # turning this on lets anyone forge a fresh identity per request, defeating
    # every rate limit. When a proxy IS added, configure it to OVERWRITE the
    # header with the real peer (nginx: `proxy_set_header X-Forwarded-For
    # $remote_addr`) — appending is spoofable, overwriting is not.
    trust_forwarded_for: bool = False

    # Rate limits for the auth endpoints, per client IP. Login guards against
    # password brute force; register against enumeration (its 409 confirms an
    # email exists) and signup spam. Generous enough not to catch a real user
    # fat-fingering a password, tight enough that a script cannot grind.
    rate_limit_login_max: int = 10
    rate_limit_login_window_seconds: int = 300
    rate_limit_register_max: int = 5
    rate_limit_register_window_seconds: int = 3600

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

"""Settings parsing.

Also serves as the walking skeleton's proof that the test harness runs.
"""

from app.core.config import Settings


def _settings(**overrides: str) -> Settings:
    defaults = {"database_url": "postgresql+psycopg://u:p@database:5432/db"}
    return Settings(**{**defaults, **overrides})  # type: ignore[arg-type]


def test_cors_origins_splits_on_commas() -> None:
    settings = _settings(cors_origins="http://localhost:5173,https://contracte.md")

    assert settings.cors_origin_list == ["http://localhost:5173", "https://contracte.md"]


def test_cors_origins_tolerates_whitespace_and_empty_entries() -> None:
    settings = _settings(cors_origins=" http://a.md , , http://b.md ")

    assert settings.cors_origin_list == ["http://a.md", "http://b.md"]


def test_single_origin_needs_no_commas() -> None:
    assert _settings(cors_origins="http://localhost:5173").cors_origin_list == [
        "http://localhost:5173"
    ]


def test_is_development_tracks_environment() -> None:
    assert _settings(environment="development").is_development is True
    assert _settings(environment="production").is_development is False

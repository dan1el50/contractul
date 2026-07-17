"""Health check response shapes."""

from pydantic import BaseModel


class DatabaseHealth(BaseModel):
    connected: bool
    # The applied Alembic revision, read from the database. None means the
    # database is reachable but migrations have not been run.
    migration_revision: str | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    environment: str
    database: DatabaseHealth

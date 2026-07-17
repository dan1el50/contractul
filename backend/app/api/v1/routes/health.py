"""Health check.

The walking skeleton's one real endpoint. It exists to prove the whole chain —
browser, API, database — is connected, and it stays useful afterwards as the
thing an orchestrator polls.
"""

import logging

from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import SessionDep
from app.core.config import get_settings
from app.schemas.health import DatabaseHealth, HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])


async def _check_database(session: AsyncSession) -> DatabaseHealth:
    """Reach the database for real and report what came back.

    Reads alembic_version rather than running SELECT 1, because it answers a
    more useful question. SELECT 1 proves the connection works; the revision
    proves the connection works *and* migrations have been applied, which is
    the state the application actually needs.
    """
    try:
        result = await session.execute(text("SELECT version_num FROM alembic_version"))
        return DatabaseHealth(connected=True, migration_revision=result.scalar_one_or_none())
    except SQLAlchemyError as exc:
        # Reachable but unmigrated looks identical to unreachable from here —
        # both raise. The message distinguishes them for a human reading logs.
        logger.warning("Database health check failed: %s", exc)
        return DatabaseHealth(
            connected=False,
            error=(
                "Cannot read alembic_version. The database may be unreachable, or "
                "migrations may not have been applied — try: "
                "docker compose exec backend alembic upgrade head"
            ),
        )


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"model": HealthResponse}},
    summary="Liveness and database connectivity",
)
async def health(session: SessionDep) -> Response:
    settings = get_settings()
    database = await _check_database(session)

    payload = HealthResponse(
        status="ok" if database.connected else "degraded",
        service="contractul-backend",
        version="0.1.0",
        environment=settings.environment,
        database=database,
    )

    # A health endpoint that returns 200 while the database is down is a broken
    # health endpoint — the status code is the part orchestrators read.
    code = status.HTTP_200_OK if database.connected else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=code, content=payload.model_dump())

"""Database engine and session lifecycle."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    # Verifies a connection is alive before handing it out. Without this, a
    # connection the database dropped while idle surfaces as a failed request.
    pool_pre_ping=True,
    echo=False,
)

SessionFactory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    # Attributes stay readable after commit. Otherwise returning an ORM object
    # from a route triggers a lazy refresh on a closed session.
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency. One session per request, always closed."""
    async with SessionFactory() as session:
        yield session

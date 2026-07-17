"""Shared test fixtures.

Integration tests run against a real PostgreSQL — a throwaway database beside
the development one, never the development one itself. Tests that share a
database with your dev data fail for reasons that have nothing to do with the
code (a leftover row already holds the email you are registering), and a test
suite you learn to distrust is worse than no suite.

Unit tests need none of this and must not use it. If a test touches the
database, it is an integration test and belongs in tests/integration/.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base

TEST_DATABASE_NAME = "contractul_test"


def _test_database_url() -> str:
    """The dev URL with the database name swapped out."""
    base, _, _ = get_settings().database_url.rpartition("/")
    return f"{base}/{TEST_DATABASE_NAME}"


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def engine() -> AsyncGenerator[AsyncEngine, None]:
    """Create the test database once per run, drop it at the end."""
    # CREATE DATABASE cannot run inside a transaction, hence AUTOCOMMIT. This
    # connects to the dev database only to issue the command — nothing is read
    # from or written to it.
    admin = create_async_engine(get_settings().database_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DATABASE_NAME} WITH (FORCE)"))
        await conn.execute(text(f"CREATE DATABASE {TEST_DATABASE_NAME}"))
    await admin.dispose()

    test_engine = create_async_engine(_test_database_url())

    # Schema from the models, not from migrations — it is much faster, and
    # `alembic check` already guards the two against drifting apart. If that
    # check is ever dropped, this becomes a place where tests pass against a
    # schema production does not have.
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield test_engine

    await test_engine.dispose()

    admin = create_async_engine(get_settings().database_url, isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f"DROP DATABASE IF EXISTS {TEST_DATABASE_NAME} WITH (FORCE)"))
    await admin.dispose()


@pytest_asyncio.fixture(loop_scope="session")
async def session(engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    """A session whose writes are always rolled back.

    Each test runs inside a transaction that is discarded afterwards, so tests
    cannot see each other's data and cannot depend on running order. This holds
    even if the code under test calls commit(): the commit lands in the
    surrounding transaction, which is then rolled back.
    """
    async with engine.connect() as connection:
        transaction = await connection.begin()
        factory = async_sessionmaker(bind=connection, expire_on_commit=False)

        async with factory() as db_session:
            yield db_session

        # A test that provoked an IntegrityError has already had the
        # transaction torn down underneath it — PostgreSQL aborts the whole
        # transaction on a constraint violation. Rolling back again is
        # harmless but noisy, and a warning printed on every error-path test
        # is how people learn to ignore warnings.
        if transaction.is_active:
            await transaction.rollback()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"

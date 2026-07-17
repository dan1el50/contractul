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
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_session
from app.main import app

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
        # The order-number sequence is not a model, so create_all does not make
        # it. The migration does in a real database; here we create it by hand
        # so checkout can draw numbers. See app/models/order.py.
        await conn.execute(text("CREATE SEQUENCE IF NOT EXISTS order_number_seq"))

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


@pytest_asyncio.fixture(loop_scope="session")
async def client(session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """An HTTP client wired to the same rolled-back session as the test.

    The override is what makes this work: without it the app would open its own
    connection, the test's writes would be invisible to the request, and the
    request's writes would survive the test. Sharing the session means the whole
    request/response cycle lands inside the transaction that gets discarded.

    ASGITransport calls the app in-process — no port, no network, no server to
    start. Middleware, dependencies and routing all still run.
    """

    async def _use_test_session() -> AsyncGenerator[AsyncSession, None]:
        yield session

    app.dependency_overrides[get_session] = _use_test_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        yield http_client

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _reset_rate_limiter() -> None:
    """Empty the rate limiter before every test.

    The limiter is a process-wide singleton keyed by client IP, and every
    ASGITransport request arrives from the same address. Without this, attempts
    would pile up across unrelated tests until an innocent register or login
    tripped the limit — a suite that fails by execution order, which is exactly
    what the rolled-back session fixture works to prevent for the database.
    """
    from app.api.deps import get_rate_limiter
    from app.core.rate_limit import InMemoryRateLimiter

    limiter = get_rate_limiter()
    # reset() is an implementation detail, not part of the Protocol — narrow to
    # the concrete type rather than widen the interface for a test's benefit.
    assert isinstance(limiter, InMemoryRateLimiter)
    limiter.reset()


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"

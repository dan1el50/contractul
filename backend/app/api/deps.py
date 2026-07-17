"""Shared route dependencies.

Anything more than one route needs: the database session, the current user,
and the admin guard.
"""

from functools import lru_cache
from math import ceil
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.rate_limit import InMemoryRateLimiter, RateLimiter
from app.db.session import get_session
from app.integrations.payments.base import PaymentProvider
from app.integrations.payments.mock import MockPaymentProvider
from app.integrations.storage.base import Storage
from app.integrations.storage.local import LocalStorage
from app.models.user import User
from app.services import auth as auth_service

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@lru_cache
def _storage() -> Storage:
    """The one place a concrete Storage is named.

    Everything else depends on the Storage protocol and is handed an
    implementation, so swapping the local filesystem for S3 changes this
    function and nothing else. A service that imports LocalStorage directly
    would make the interface decorative.
    """
    return LocalStorage(get_settings().document_storage_path)


def get_storage() -> Storage:
    return _storage()


StorageDep = Annotated[Storage, Depends(get_storage)]


@lru_cache
def _payments() -> PaymentProvider:
    """The one place a concrete PaymentProvider is named.

    Everything else depends on the protocol, so swapping the mock for a real
    acquirer changes this function and no business logic. Cached because the
    mock keeps its charges in memory — a fresh instance per request would
    forget every charge it had just taken, and refunds would fail.
    """
    return MockPaymentProvider()


def get_payments() -> PaymentProvider:
    return _payments()


PaymentsDep = Annotated[PaymentProvider, Depends(get_payments)]


@lru_cache
def _rate_limiter() -> RateLimiter:
    """The one place a concrete RateLimiter is named.

    Cached: the counter IS the state. A fresh instance per request would forget
    every attempt it had just seen, and the limit would never bind.
    """
    return InMemoryRateLimiter()


def get_rate_limiter() -> RateLimiter:
    return _rate_limiter()


RateLimiterDep = Annotated[RateLimiter, Depends(get_rate_limiter)]


def _client_ip(request: Request) -> str:
    """The address a rate limit is charged against.

    The socket peer by default. X-Forwarded-For is honoured only when
    `trust_forwarded_for` is set, because with no proxy in front the header is
    attacker-supplied — trusting it unconditionally would hand every caller a
    free identity per request. See the setting's note for the proxy config that
    makes it safe.
    """
    settings = get_settings()
    if settings.trust_forwarded_for:
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            return forwarded.split(",", 1)[0].strip()
    if request.client is not None:
        return request.client.host
    # No peer (a raw ASGI call with no client in scope). One shared bucket is
    # the safe failure: it over-limits rather than letting anyone through.
    return "unknown"


class RateLimit:
    """A per-client rate limit, expressed as a route dependency.

    Keyed by client IP inside a named scope, so a limit on one endpoint does
    not spend another's budget. Raises 429 with Retry-After when exceeded. The
    limits come from settings, read per request, so they are tunable without a
    code change and overridable in a test.

        @router.post("/login", dependencies=[Depends(RateLimit("login"))])
    """

    def __init__(self, scope: str) -> None:
        self._scope = scope

    async def __call__(self, request: Request, limiter: RateLimiterDep) -> None:
        limit, window = self._limits()
        key = f"{self._scope}:{_client_ip(request)}"
        result = limiter.hit(key, limit=limit, window_seconds=window)
        if not result.allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Prea multe încercări. Încearcă din nou mai târziu.",
                # Seconds, rounded up and never zero — a client that obeys it
                # must actually clear the window.
                headers={"Retry-After": str(max(1, ceil(result.retry_after)))},
            )

    def _limits(self) -> tuple[int, int]:
        settings = get_settings()
        if self._scope == "login":
            return settings.rate_limit_login_max, settings.rate_limit_login_window_seconds
        if self._scope == "register":
            return settings.rate_limit_register_max, settings.rate_limit_register_window_seconds
        raise ValueError(f"No rate limit configured for scope {self._scope!r}")


async def get_session_token(
    contractul_session: Annotated[str | None, Cookie()] = None,
) -> str | None:
    """The raw session token from the cookie, if the request carries one.

    The parameter name must match the cookie name — FastAPI maps it by name.
    get_settings().session_cookie_name is the single source of truth for that
    string; this signature has to agree with it, and a test asserts they do.
    """
    return contractul_session


SessionToken = Annotated[str | None, Depends(get_session_token)]


async def get_current_user(session: SessionDep, token: SessionToken) -> User:
    """The signed-in user, or 401.

    Every rule is re-checked per request — expiry, revocation, is_active — so
    access ends the moment it should, not whenever a token happens to lapse.
    """
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autentificare necesară.",
        )

    user = await auth_service.resolve_session(session, token=token)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sesiune invalidă sau expirată.",
        )

    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_admin_user(user: CurrentUser) -> User:
    """An admin, or 403.

    403 and not 404: this endpoint exists and the caller is simply not allowed
    to use it. Hiding admin routes behind 404s protects nothing — the frontend
    bundle names them anyway — and it makes a genuine bug look like a missing
    route.
    """
    if not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acces interzis.",
        )

    return user


AdminUser = Annotated[User, Depends(get_admin_user)]


def _assert_cookie_name_matches_settings() -> None:
    """The Cookie() parameter above is bound by name, not by config.

    If session_cookie_name changes and that signature does not, authentication
    silently stops working: the cookie is set under one name and read under
    another, every request looks logged out, and nothing raises.
    """
    expected = get_settings().session_cookie_name
    actual = "contractul_session"
    if expected != actual:
        raise RuntimeError(
            f"Cookie name mismatch: settings say {expected!r}, "
            f"get_session_token() reads {actual!r}. Update the parameter name."
        )


_assert_cookie_name_matches_settings()

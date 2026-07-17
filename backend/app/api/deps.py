"""Shared route dependencies.

Anything more than one route needs: the database session, the current user,
and the admin guard.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_session
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

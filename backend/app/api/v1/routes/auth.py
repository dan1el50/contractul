"""Authentication endpoints.

Handlers are thin by design: check input, call one service, shape a response.
Everything that decides anything lives in app.services.auth.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import CurrentUser, RateLimit, SessionDep, SessionToken
from app.core.config import get_settings
from app.schemas.auth import LoginRequest, RegisterRequest, UserResponse
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookie(response: Response, token: str) -> None:
    settings = get_settings()

    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        # JavaScript cannot read it. An XSS bug then cannot steal the session,
        # which is the whole reason this is not localStorage.
        httponly=True,
        # Not sent on cross-site requests, which blocks CSRF without a token
        # dance. "lax" rather than "strict" so that arriving from an emailed
        # link lands you logged in.
        samesite="lax",
        secure=settings.cookie_secure,
        max_age=int(auth_service.SESSION_LIFETIME.total_seconds()),
        path="/",
    )


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(RateLimit("register"))],
)
async def register(payload: RegisterRequest, response: Response, session: SessionDep) -> UserResponse:
    try:
        user = await auth_service.register(
            session,
            email=payload.email,
            password=payload.password,
            full_name=payload.full_name,
            phone=payload.phone,
        )
    except auth_service.EmailAlreadyRegistered:
        # 409, and it does confirm the email exists. Unavoidable: registration
        # has to say why it failed or it is unusable. The mitigation is the
        # rate limit on this route, which caps how fast the oracle can be
        # queried — not this handler.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un cont cu acest email există deja.",
        ) from None

    token = await auth_service.create_session(session, user=user)
    await session.commit()

    _set_session_cookie(response, token)
    return UserResponse.model_validate(user)


@router.post(
    "/login",
    response_model=UserResponse,
    dependencies=[Depends(RateLimit("login"))],
)
async def login(payload: LoginRequest, response: Response, session: SessionDep) -> UserResponse:
    try:
        user = await auth_service.authenticate(
            session, email=payload.email, password=payload.password
        )
    except auth_service.InvalidCredentials:
        # One message for wrong-email, wrong-password and deactivated. Naming
        # which one would turn this into an account-enumeration endpoint.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email sau parolă incorectă.",
        ) from None

    token = await auth_service.create_session(session, user=user)
    await session.commit()

    _set_session_cookie(response, token)
    return UserResponse.model_validate(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response, session: SessionDep, token: SessionToken) -> None:
    if token:
        await auth_service.revoke_session(session, token=token)
        await session.commit()

    # Cleared even when there was no session: logout is idempotent, and it must
    # not be possible to be told "you were not logged in anyway".
    response.delete_cookie(
        key=get_settings().session_cookie_name,
        httponly=True,
        samesite="lax",
        secure=get_settings().cookie_secure,
        path="/",
    )


@router.get("/me", response_model=UserResponse)
async def me(user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(user)

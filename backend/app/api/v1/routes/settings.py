"""Account settings: profile, password, company. Signed in only."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SessionDep, SessionToken
from app.schemas.auth import UserResponse
from app.schemas.settings import CompanyResponse, CompanyUpsert, PasswordChange, ProfileUpdate
from app.services import settings as settings_service

router = APIRouter(prefix="/settings", tags=["settings"])


@router.patch("/profile", response_model=UserResponse)
async def update_profile(
    payload: ProfileUpdate, session: SessionDep, user: CurrentUser
) -> UserResponse:
    updated = await settings_service.update_profile(
        session, user=user, full_name=payload.full_name, phone=payload.phone
    )
    await session.commit()
    return UserResponse.model_validate(updated)


@router.post("/password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    payload: PasswordChange, session: SessionDep, user: CurrentUser, token: SessionToken
) -> None:
    try:
        await settings_service.change_password(
            session,
            user=user,
            current_password=payload.current_password,
            new_password=payload.new_password,
            # Keep the caller signed in; end every other session.
            keep_token=token,
        )
    except settings_service.IncorrectPassword:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Parola actuală este incorectă.",
        ) from None

    await session.commit()


@router.get("/company", response_model=CompanyResponse | None)
async def get_company(session: SessionDep, user: CurrentUser) -> CompanyResponse | None:
    company = await settings_service.get_company(session, user_id=user.id)
    return CompanyResponse.model_validate(company) if company else None


@router.put("/company", response_model=CompanyResponse)
async def upsert_company(
    payload: CompanyUpsert, session: SessionDep, user: CurrentUser
) -> CompanyResponse:
    company = await settings_service.upsert_company(
        session,
        user_id=user.id,
        name=payload.name,
        idno=payload.idno,
        legal_address=payload.legal_address,
        iban=payload.iban,
        bank_name=payload.bank_name,
    )
    await session.commit()
    return CompanyResponse.model_validate(company)

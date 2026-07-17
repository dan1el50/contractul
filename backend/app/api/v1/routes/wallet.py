"""Wallet and saved cards. Every endpoint requires a signed-in user."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, PaymentsDep, SessionDep
from app.integrations.payments.base import CardDeclined, PaymentError
from app.schemas.wallet import (
    AddCardRequest,
    BalanceResponse,
    CardResponse,
    TopUpRequest,
    TransactionResponse,
)
from app.services import cards as cards_service
from app.services import wallet as wallet_service

router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("/balance", response_model=BalanceResponse)
async def get_balance(user: CurrentUser, session: SessionDep) -> BalanceResponse:
    balance = await wallet_service.get_balance(session, user_id=user.id)
    return BalanceResponse(balance_bani=balance)


@router.get("/transactions", response_model=list[TransactionResponse])
async def list_transactions(user: CurrentUser, session: SessionDep) -> list[TransactionResponse]:
    # Scoped to the current user by construction — there is no parameter for
    # whose transactions to list, so there is nothing to tamper with.
    transactions = await wallet_service.list_transactions(session, user_id=user.id)
    return [TransactionResponse.model_validate(t) for t in transactions]


@router.post("/top-up", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def top_up(
    payload: TopUpRequest,
    user: CurrentUser,
    session: SessionDep,
    payments: PaymentsDep,
) -> TransactionResponse:
    try:
        transaction = await wallet_service.top_up(
            session,
            provider=payments,
            user_id=user.id,
            card_id=payload.card_id,
            amount_bani=payload.amount_bani,
        )
    except wallet_service.CardNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cardul nu a fost găsit."
        ) from None
    except CardDeclined:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Cardul a fost refuzat. Încearcă alt card.",
        ) from None
    except PaymentError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc

    await session.commit()
    return TransactionResponse.model_validate(transaction)


@router.get("/cards", response_model=list[CardResponse])
async def list_cards(user: CurrentUser, session: SessionDep) -> list[CardResponse]:
    cards = await cards_service.list_cards(session, user_id=user.id)
    return [CardResponse.model_validate(c) for c in cards]


@router.post("/cards", response_model=CardResponse, status_code=status.HTTP_201_CREATED)
async def add_card(
    payload: AddCardRequest,
    user: CurrentUser,
    session: SessionDep,
    payments: PaymentsDep,
) -> CardResponse:
    try:
        card = await cards_service.add_card(
            session,
            provider=payments,
            user_id=user.id,
            number=payload.number,
            exp_month=payload.exp_month,
            exp_year=payload.exp_year,
            cvv=payload.cvv,
            make_default=payload.make_default,
        )
    except CardDeclined:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Cardul a fost refuzat."
        ) from None
    except PaymentError as exc:
        # The message never echoes the request. A validation error that quoted
        # the number back would put a PAN in the response body, and from there
        # into somebody's logs.
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    await session.commit()
    return CardResponse.model_validate(card)


@router.post("/cards/{card_id}/default", response_model=CardResponse)
async def set_default_card(
    card_id: uuid.UUID, user: CurrentUser, session: SessionDep
) -> CardResponse:
    try:
        card = await cards_service.set_default(session, user_id=user.id, card_id=card_id)
    except cards_service.CardNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cardul nu a fost găsit."
        ) from None

    await session.commit()
    return CardResponse.model_validate(card)


@router.delete("/cards/{card_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_card(card_id: uuid.UUID, user: CurrentUser, session: SessionDep) -> None:
    try:
        await cards_service.delete_card(session, user_id=user.id, card_id=card_id)
    except cards_service.CardNotFound:
        # 404 for "not yours" as much as for "does not exist". Distinguishing
        # them would let anyone probe which card ids are real.
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Cardul nu a fost găsit."
        ) from None

    await session.commit()

"""Order endpoints: checkout and order history. Signed in only."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.order import CheckoutRequest, OrderResponse
from app.services import cart as cart_service
from app.services import checkout as checkout_service
from app.services import wallet as wallet_service

router = APIRouter(prefix="/orders", tags=["orders"])


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
async def create_order(
    payload: CheckoutRequest, session: SessionDep, user: CurrentUser
) -> OrderResponse:
    """Check out the cart. All or nothing.

    On any failure the session is never committed, so no order, no debit, and no
    emptied cart survive — the guarantee the checkout service is built around.
    """
    try:
        order = await checkout_service.checkout(
            session, user_id=user.id, payment_method=payload.payment_method
        )
    except checkout_service.EmptyCart:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Coșul este gol."
        ) from None
    except cart_service.AlreadyOwned:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Coșul conține un contract pe care îl deții deja.",
        ) from None
    except wallet_service.InsufficientFunds as exc:
        # 402 Payment Required, and it says the shortfall. Nothing is committed:
        # the request never reaches the commit below, and get_session rolls the
        # session back when it closes, so no order and no debit survive and the
        # cart stays as it was. See tests/integration/test_checkout.py for the
        # atomicity proof against a real connection.
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Sold insuficient. Alimentează portofelul și încearcă din nou.",
            headers={
                "X-Balance-Bani": str(exc.balance_bani),
                "X-Required-Bani": str(exc.required_bani),
            },
        ) from None

    await session.commit()
    return OrderResponse.from_order(order)


@router.get("", response_model=list[OrderResponse])
async def list_orders(session: SessionDep, user: CurrentUser) -> list[OrderResponse]:
    orders = await checkout_service.list_orders(session, user_id=user.id)
    return [OrderResponse.from_order(o) for o in orders]


@router.get("/{order_id}", response_model=OrderResponse)
async def get_order(order_id: uuid.UUID, session: SessionDep, user: CurrentUser) -> OrderResponse:
    try:
        order = await checkout_service.get_order(session, user_id=user.id, order_id=order_id)
    except checkout_service.OrderNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Comanda nu a fost găsită."
        ) from None
    return OrderResponse.from_order(order)

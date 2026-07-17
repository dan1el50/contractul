"""Cart endpoints. Signed in only — a cart belongs to a user."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUser, SessionDep
from app.schemas.cart import AddToCartRequest, CartResponse
from app.services import cart as cart_service
from app.services.catalog import TemplateNotFound

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=CartResponse)
async def get_cart(session: SessionDep, user: CurrentUser) -> CartResponse:
    items = await cart_service.get_cart_items(session, user_id=user.id)
    return CartResponse.from_items(items)


@router.post("/items", response_model=CartResponse, status_code=status.HTTP_201_CREATED)
async def add_to_cart(
    payload: AddToCartRequest, session: SessionDep, user: CurrentUser
) -> CartResponse:
    try:
        await cart_service.add_item(session, user_id=user.id, slug=payload.slug)
    except TemplateNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contractul nu a fost găsit."
        ) from None
    except cart_service.AlreadyOwned:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ai cumpărat deja acest contract.",
        ) from None

    await session.commit()

    items = await cart_service.get_cart_items(session, user_id=user.id)
    return CartResponse.from_items(items)


@router.delete("/items/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_from_cart(
    template_id: uuid.UUID, session: SessionDep, user: CurrentUser
) -> None:
    await cart_service.remove_item(session, user_id=user.id, template_id=template_id)
    await session.commit()

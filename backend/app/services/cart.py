"""Cart logic: add, remove, and read a user's server-side cart.

The cart holds template ids, never prices — the price is read live from the
catalog and only snapshotted when the order is placed. See docs/data-model.md.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cart import Cart, CartItem
from app.models.catalog import ContractTemplate
from app.models.order import Order, OrderItem
from app.services.catalog import TemplateNotFound


class AlreadyOwned(Exception):
    """The user has already bought this template.

    Buying the same document twice is meaningless — the file is identical — so
    it is refused at the cart, not silently charged again.
    """

    def __init__(self, template_id: uuid.UUID) -> None:
        self.template_id = template_id
        super().__init__(str(template_id))


async def get_or_create_cart(session: AsyncSession, *, user_id: uuid.UUID) -> Cart:
    cart = await session.scalar(select(Cart).where(Cart.user_id == user_id))
    if cart is None:
        cart = Cart(user_id=user_id)
        session.add(cart)
        await session.flush()
    return cart


async def owned_template_ids(session: AsyncSession, *, user_id: uuid.UUID) -> set[uuid.UUID]:
    """Templates the user has already paid for.

    A paid order's items, by template. Used to keep a document out of the cart
    once it is owned, and to re-check at checkout.
    """
    rows = await session.scalars(
        select(OrderItem.template_id)
        .join(Order, OrderItem.order_id == Order.id)
        .where(Order.user_id == user_id, Order.status == "paid")
    )
    return set(rows.all())


async def get_cart_items(session: AsyncSession, *, user_id: uuid.UUID) -> list[CartItem]:
    """The cart's items, each with its template and category loaded, oldest first."""
    cart = await session.scalar(select(Cart).where(Cart.user_id == user_id))
    if cart is None:
        return []

    result = await session.scalars(
        select(CartItem)
        .where(CartItem.cart_id == cart.id)
        .options(selectinload(CartItem.template).selectinload(ContractTemplate.category))
        .order_by(CartItem.added_at, CartItem.id)
    )
    return list(result.all())


async def add_item(session: AsyncSession, *, user_id: uuid.UUID, slug: str) -> CartItem:
    """Add a published template to the cart, by slug.

    Idempotent on a template already in the cart — adding it again returns the
    existing line rather than erroring, so a double click is harmless. Refuses a
    template the user already owns.
    """
    template = await session.scalar(
        select(ContractTemplate).where(
            ContractTemplate.slug == slug, ContractTemplate.is_published
        )
    )
    if template is None:
        raise TemplateNotFound(slug)

    owned = await owned_template_ids(session, user_id=user_id)
    if template.id in owned:
        raise AlreadyOwned(template.id)

    cart = await get_or_create_cart(session, user_id=user_id)

    existing = await session.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id, CartItem.template_id == template.id
        )
    )
    if existing is not None:
        return existing

    item = CartItem(cart_id=cart.id, template_id=template.id)
    session.add(item)
    try:
        await session.flush()
    except IntegrityError:
        # Two concurrent adds of the same template race the UNIQUE constraint.
        # The loser reads the row the winner inserted — the outcome the user
        # wanted either way.
        await session.rollback()
        raced = await session.scalar(
            select(CartItem).where(
                CartItem.cart_id == cart.id, CartItem.template_id == template.id
            )
        )
        assert raced is not None
        return raced
    return item


async def remove_item(session: AsyncSession, *, user_id: uuid.UUID, template_id: uuid.UUID) -> None:
    """Remove a template from the cart. A no-op if it was not there."""
    cart = await session.scalar(select(Cart).where(Cart.user_id == user_id))
    if cart is None:
        return

    item = await session.scalar(
        select(CartItem).where(
            CartItem.cart_id == cart.id, CartItem.template_id == template_id
        )
    )
    if item is not None:
        await session.delete(item)
        await session.flush()


async def clear_cart(session: AsyncSession, *, cart_id: uuid.UUID) -> None:
    """Empty a cart, keeping the cart itself. Called after checkout."""
    items = await session.scalars(select(CartItem).where(CartItem.cart_id == cart_id))
    for item in items.all():
        await session.delete(item)
    await session.flush()

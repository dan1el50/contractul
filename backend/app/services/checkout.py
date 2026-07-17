"""Checkout: turn a cart into a paid order, atomically.

The whole of checkout — order, its snapshotted items, the wallet debit, and
emptying the cart — is one transaction. The caller (the route) commits once at
the end; if any step raises, nothing is committed and the request's session is
rolled back on close. So a purchase either fully happens or fully does not, which
is the property phase 6 exists to guarantee.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem
from app.services import cart as cart_service
from app.services import catalog as catalog_service
from app.services import wallet as wallet_service

logger = logging.getLogger(__name__)


class EmptyCart(Exception):
    """There is nothing to check out."""


class OrderNotFound(Exception):
    """No such order, or it belongs to somebody else.

    One exception for both: a caller must not be able to tell "does not exist"
    from "not yours", or order ids become enumerable.
    """


async def _next_order_number(session: AsyncSession) -> str:
    """CT-{year}-{sequence}, the year from Moldova's clock.

    The sequence is drawn even by a checkout that later rolls back, so numbers
    have gaps. That is deliberate and safe — see docs/data-model.md.
    """
    number = await session.scalar(
        text(
            "SELECT 'CT-' || to_char(now() AT TIME ZONE 'Europe/Chisinau', 'YYYY') "
            "|| '-' || lpad(nextval('order_number_seq')::text, 4, '0')"
        )
    )
    assert number is not None
    return str(number)


async def checkout(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    payment_method: str = "wallet",
) -> Order:
    """Buy everything in the user's cart, paying from the wallet.

    Raises EmptyCart, cart_service.AlreadyOwned, or
    wallet_service.InsufficientFunds. On any of them the caller must not commit;
    the partial order is then discarded on rollback.
    """
    if payment_method != "wallet":
        # Card-at-checkout waits for the real acquirer (phase 10). Until then
        # the only funded path is the wallet, which the mock top-up feeds.
        raise ValueError(f"Unsupported payment method: {payment_method!r}")

    items = await cart_service.get_cart_items(session, user_id=user_id)
    if not items:
        raise EmptyCart()

    owned = await cart_service.owned_template_ids(session, user_id=user_id)

    # Resolve each cart line to the exact file a buyer gets today. current_version
    # raises TemplateNotFound if a published template somehow has no current
    # version — a data bug, but one that must stop a sale rather than sell an
    # unrenderable document.
    lines: list[tuple[str, int, uuid.UUID, uuid.UUID]] = []
    for item in items:
        template = item.template
        if template.id in owned:
            raise cart_service.AlreadyOwned(template.id)
        version = await catalog_service.current_version(session, template=template)
        lines.append((template.name, template.price_bani, template.id, version.id))

    total_bani = sum(price for _, price, _, _ in lines)

    # The order is created and flushed before the wallet is touched. If the
    # debit then fails (insufficient funds), these rows were never committed and
    # vanish on rollback — the natural mid-transaction failure the atomicity
    # test relies on.
    number = await _next_order_number(session)
    order = Order(
        user_id=user_id,
        number=number,
        status="paid",
        total_bani=total_bani,
        payment_method=payment_method,
        # A plain datetime, not func.now(): the value is read straight back when
        # the response is built, and an unresolved SQL function element would
        # not serialise. Payment here is synchronous, so "paid now" is exact.
        paid_at=datetime.now(UTC),
    )
    # Appended through the relationship, not inserted by order_id: this both
    # persists the lines and populates order.items in memory, so building the
    # response does not trigger a lazy load outside the async context.
    for name, price, template_id, version_id in lines:
        order.items.append(
            OrderItem(
                template_id=template_id,
                template_version_id=version_id,
                name_snapshot=name,
                unit_price_bani=price,
            )
        )
    session.add(order)
    await session.flush()

    # Locks the user, re-checks the balance under the lock, and raises
    # InsufficientFunds rather than overdrawing. This is the step that can fail,
    # and failing here rolls back the order above with it.
    await wallet_service.debit(
        session,
        user_id=user_id,
        amount_bani=total_bani,
        kind="purchase",
        description=f"Comandă {number}",
        order_id=order.id,
    )

    cart = await cart_service.get_or_create_cart(session, user_id=user_id)
    await cart_service.clear_cart(session, cart_id=cart.id)

    logger.info("Order %s placed for user %s (%s bani)", number, user_id, total_bani)
    return order


async def get_order(session: AsyncSession, *, user_id: uuid.UUID, order_id: uuid.UUID) -> Order:
    order = await session.scalar(
        select(Order)
        .where(Order.id == order_id, Order.user_id == user_id)
        .options(selectinload(Order.items))
    )
    if order is None:
        raise OrderNotFound(str(order_id))
    return order


async def list_orders(session: AsyncSession, *, user_id: uuid.UUID) -> list[Order]:
    result = await session.scalars(
        select(Order)
        .where(Order.user_id == user_id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc(), Order.id.desc())
    )
    return list(result.all())

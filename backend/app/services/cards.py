"""Saved payment cards."""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.payments.base import PaymentProvider
from app.models.wallet import PaymentCard

logger = logging.getLogger(__name__)


class CardNotFound(Exception):
    """No such card, or not this user's."""


async def list_cards(session: AsyncSession, *, user_id: uuid.UUID) -> list[PaymentCard]:
    result = await session.scalars(
        select(PaymentCard)
        .where(PaymentCard.user_id == user_id)
        .order_by(PaymentCard.is_default.desc(), PaymentCard.created_at.desc())
    )
    return list(result.all())


async def add_card(
    session: AsyncSession,
    *,
    provider: PaymentProvider,
    user_id: uuid.UUID,
    number: str,
    exp_month: int,
    exp_year: int,
    cvv: str,
    make_default: bool = False,
) -> PaymentCard:
    """Tokenise a card and save the token.

    The raw number and CVV go to the provider and are never written anywhere —
    not to the database, not to a log. Only the token, brand and last four
    digits survive this function.
    """
    token = provider.tokenise_card(
        number=number, exp_month=exp_month, exp_year=exp_year, cvv=cvv
    )

    existing = await list_cards(session, user_id=user_id)
    # The first card is the default whether asked for or not: a user with cards
    # but no default has no sensible pre-selection at checkout.
    is_default = make_default or not existing

    if is_default:
        await _clear_default(session, user_id=user_id)

    card = PaymentCard(
        user_id=user_id,
        provider_token=token.token,
        brand=token.brand,
        last4=token.last4,
        exp_month=token.exp_month,
        exp_year=token.exp_year,
        is_default=is_default,
    )
    session.add(card)
    await session.flush()

    logger.info("Saved %s card ending %s for user %s", token.brand, token.last4, user_id)
    return card


async def set_default(
    session: AsyncSession, *, user_id: uuid.UUID, card_id: uuid.UUID
) -> PaymentCard:
    card = await session.get(PaymentCard, card_id)

    if card is None or card.user_id != user_id:
        raise CardNotFound(str(card_id))

    await _clear_default(session, user_id=user_id)
    card.is_default = True
    await session.flush()
    return card


async def delete_card(session: AsyncSession, *, user_id: uuid.UUID, card_id: uuid.UUID) -> None:
    card = await session.get(PaymentCard, card_id)

    if card is None or card.user_id != user_id:
        raise CardNotFound(str(card_id))

    was_default = card.is_default
    await session.delete(card)
    await session.flush()

    # Promote another card, so a user is never left with cards and no default.
    if was_default:
        remaining = await list_cards(session, user_id=user_id)
        if remaining:
            remaining[0].is_default = True
            await session.flush()


async def _clear_default(session: AsyncSession, *, user_id: uuid.UUID) -> None:
    """Unset the current default.

    Must run before setting a new one: a partial unique index enforces at most
    one default per user, so setting a second without clearing the first is an
    IntegrityError rather than a silent overwrite.
    """
    await session.execute(
        update(PaymentCard)
        .where(PaymentCard.user_id == user_id, PaymentCard.is_default)
        .values(is_default=False)
    )

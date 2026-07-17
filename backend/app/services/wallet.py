"""Wallet logic: balance, top-ups, and the debit primitive checkout will use.

The balance is derived from the ledger, never stored. See docs/data-model.md
for why. This module is where the cost of that choice is paid — and where the
concurrency problem it creates is solved.
"""

from __future__ import annotations

import logging
import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.payments.base import PaymentProvider
from app.models.user import User
from app.models.wallet import PaymentCard, WalletTransaction

logger = logging.getLogger(__name__)


class InsufficientFunds(Exception):
    def __init__(self, *, balance_bani: int, required_bani: int) -> None:
        self.balance_bani = balance_bani
        self.required_bani = required_bani
        super().__init__(f"Balance {balance_bani} < required {required_bani}")


class CardNotFound(Exception):
    """No such card, or it belongs to somebody else.

    One exception for both, deliberately: a caller must not be able to tell
    "does not exist" from "not yours", or card ids become enumerable.
    """


async def get_balance(session: AsyncSession, *, user_id: uuid.UUID) -> int:
    """Current balance in bani. Zero for a user with no transactions."""
    total = await session.scalar(
        select(func.coalesce(func.sum(WalletTransaction.amount_bani), 0)).where(
            WalletTransaction.user_id == user_id
        )
    )
    return int(total or 0)


async def _lock_user(session: AsyncSession, *, user_id: uuid.UUID) -> None:
    """Serialise wallet writes for one user.

    **This is what makes a derived balance safe.**

    Without it, two concurrent purchases each run "read balance, check it is
    enough, insert a debit". Both reads happen before either insert, so both see
    the old balance, both decide there is enough, and the wallet goes negative.
    No constraint catches it: each row is individually valid, and it is only
    their sum that is wrong — which is exactly the failure a SUM-derived balance
    cannot express as a CHECK.

    Taking a row lock on the user first means the second transaction blocks
    until the first commits, then reads the balance the first left behind. It
    serialises per user, not globally, so two different customers never wait on
    each other. At our volume the cost is unmeasurable.
    """
    await session.execute(select(User.id).where(User.id == user_id).with_for_update())


async def credit(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    amount_bani: int,
    kind: str,
    description: str,
    provider_charge_id: str | None = None,
    order_id: uuid.UUID | None = None,
) -> WalletTransaction:
    """Add money. Amount must be positive."""
    if amount_bani <= 0:
        raise ValueError(f"credit() needs a positive amount, got {amount_bani}")

    transaction = WalletTransaction(
        user_id=user_id,
        amount_bani=amount_bani,
        kind=kind,
        description=description,
        provider_charge_id=provider_charge_id,
        order_id=order_id,
    )
    session.add(transaction)
    await session.flush()
    return transaction


async def debit(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    amount_bani: int,
    kind: str,
    description: str,
    order_id: uuid.UUID | None = None,
) -> WalletTransaction:
    """Take money, refusing to overdraw.

    Locks the user first, so a concurrent debit cannot read a stale balance.
    Callers must be inside a transaction — the lock is only held until commit,
    and checkout depends on the debit and the order committing together.

    `amount_bani` is positive; it is stored negated. Making callers pass a
    negative number would put a sign error one keystroke away from a debit that
    silently credits.
    """
    if amount_bani <= 0:
        raise ValueError(f"debit() needs a positive amount, got {amount_bani}")

    await _lock_user(session, user_id=user_id)

    balance = await get_balance(session, user_id=user_id)
    if balance < amount_bani:
        raise InsufficientFunds(balance_bani=balance, required_bani=amount_bani)

    transaction = WalletTransaction(
        user_id=user_id,
        amount_bani=-amount_bani,
        kind=kind,
        description=description,
        order_id=order_id,
    )
    session.add(transaction)
    await session.flush()
    return transaction


async def top_up(
    session: AsyncSession,
    *,
    provider: PaymentProvider,
    user_id: uuid.UUID,
    card_id: uuid.UUID,
    amount_bani: int,
) -> WalletTransaction:
    """Charge a card and credit the wallet.

    The charge happens first. If it fails, nothing is credited; if the credit
    fails afterwards, the caller's transaction rolls back and we are left having
    taken money without crediting it — recoverable from the provider's charge id,
    which is why it is stored on the row.

    The alternative — credit first, charge after — would hand out money for
    free whenever a card declines. Given a choice between the two failures, the
    recoverable one wins.
    """
    card = await session.get(PaymentCard, card_id)

    if card is None or card.user_id != user_id:
        raise CardNotFound(str(card_id))

    charge = provider.charge(
        amount_bani=amount_bani,
        card_token=card.provider_token,
        description="Alimentare portofel Contractul.md",
    )

    logger.info("Top-up %s bani for user %s (charge %s)", amount_bani, user_id, charge.charge_id)

    return await credit(
        session,
        user_id=user_id,
        amount_bani=amount_bani,
        kind="topup",
        description="Alimentare cont",
        provider_charge_id=charge.charge_id,
    )


async def list_transactions(
    session: AsyncSession, *, user_id: uuid.UUID, limit: int = 50
) -> list[WalletTransaction]:
    result = await session.scalars(
        select(WalletTransaction)
        .where(WalletTransaction.user_id == user_id)
        .order_by(WalletTransaction.created_at.desc(), WalletTransaction.id.desc())
        .limit(limit)
    )
    return list(result.all())

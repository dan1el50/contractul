"""Wallet logic against a real database.

The concurrency test is the one that matters. A derived balance is only safe
because of the row lock in debit(); without it, two simultaneous purchases both
read the old balance, both decide there is enough, and the wallet goes negative.
No constraint catches that — each row is individually valid and only their sum
is wrong.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import asynccontextmanager

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.integrations.payments.mock import MockPaymentProvider
from app.models.user import User
from app.models.wallet import PaymentCard
from app.services import wallet as wallet_service


async def _user(session: AsyncSession, email: str = "ion@nordconstruct.md") -> User:
    user = User(email=email, password_hash="x", full_name="Ion Popescu")
    session.add(user)
    await session.flush()
    return user


async def _card(session: AsyncSession, user: User) -> PaymentCard:
    card = PaymentCard(
        user_id=user.id,
        provider_token="mock_tok_abc123",
        brand="visa",
        last4="3382",
        exp_month=9,
        exp_year=2028,
        is_default=True,
    )
    session.add(card)
    await session.flush()
    return card


# ─── Balance ─────────────────────────────────────────────────────────────────


async def test_a_new_wallet_is_empty(session: AsyncSession) -> None:
    user = await _user(session)

    assert await wallet_service.get_balance(session, user_id=user.id) == 0


async def test_balance_is_the_sum_of_the_ledger(session: AsyncSession) -> None:
    user = await _user(session)

    await wallet_service.credit(
        session, user_id=user.id, amount_bani=330000, kind="topup", description="Alimentare"
    )
    await wallet_service.debit(
        session, user_id=user.id, amount_bani=90000, kind="purchase", description="Contract"
    )

    assert await wallet_service.get_balance(session, user_id=user.id) == 240000


async def test_wallets_are_isolated_between_users(session: AsyncSession) -> None:
    ion = await _user(session, "ion@nordconstruct.md")
    maria = await _user(session, "maria@altfel.md")

    await wallet_service.credit(
        session, user_id=ion.id, amount_bani=100000, kind="topup", description="x"
    )

    assert await wallet_service.get_balance(session, user_id=maria.id) == 0


async def test_credit_rejects_a_non_positive_amount(session: AsyncSession) -> None:
    user = await _user(session)

    for amount in (0, -1):
        with pytest.raises(ValueError):
            await wallet_service.credit(
                session, user_id=user.id, amount_bani=amount, kind="topup", description="x"
            )


# ─── Debit ───────────────────────────────────────────────────────────────────


async def test_debit_stores_a_negative_amount(session: AsyncSession) -> None:
    """Callers pass a positive number; the sign is applied here.

    Making callers negate would put a sign error one keystroke away from a
    debit that silently credits.
    """
    user = await _user(session)
    await wallet_service.credit(
        session, user_id=user.id, amount_bani=100000, kind="topup", description="x"
    )

    transaction = await wallet_service.debit(
        session, user_id=user.id, amount_bani=90000, kind="purchase", description="Contract"
    )

    assert transaction.amount_bani == -90000


async def test_debit_refuses_to_overdraw(session: AsyncSession) -> None:
    user = await _user(session)
    await wallet_service.credit(
        session, user_id=user.id, amount_bani=50000, kind="topup", description="x"
    )

    with pytest.raises(wallet_service.InsufficientFunds) as exc:
        await wallet_service.debit(
            session, user_id=user.id, amount_bani=90000, kind="purchase", description="Contract"
        )

    assert exc.value.balance_bani == 50000
    assert exc.value.required_bani == 90000


async def test_a_refused_debit_leaves_no_trace(session: AsyncSession) -> None:
    user = await _user(session)

    with pytest.raises(wallet_service.InsufficientFunds):
        await wallet_service.debit(
            session, user_id=user.id, amount_bani=1, kind="purchase", description="x"
        )

    assert await wallet_service.get_balance(session, user_id=user.id) == 0
    assert await wallet_service.list_transactions(session, user_id=user.id) == []


async def test_spending_the_exact_balance_is_allowed(session: AsyncSession) -> None:
    """Off-by-one guard: the check is `balance < amount`, not `<=`."""
    user = await _user(session)
    await wallet_service.credit(
        session, user_id=user.id, amount_bani=90000, kind="topup", description="x"
    )

    await wallet_service.debit(
        session, user_id=user.id, amount_bani=90000, kind="purchase", description="Contract"
    )

    assert await wallet_service.get_balance(session, user_id=user.id) == 0


# ─── Concurrency ─────────────────────────────────────────────────────────────


@asynccontextmanager
async def _funded_user(engine: AsyncEngine, *, email: str, balance_bani: int):
    """A committed user with a real balance, cleaned up afterwards.

    These tests need genuine concurrent connections, so they cannot use the
    shared `session` fixture — everything inside one transaction never contends
    with itself, and the fixture's rollback would hide the commits.
    """
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async with factory() as setup:
        user = User(email=email, password_hash="x", full_name="Race Test")
        setup.add(user)
        await setup.flush()
        user_id = user.id
        await wallet_service.credit(
            setup, user_id=user_id, amount_bani=balance_bani, kind="topup", description="x"
        )
        await setup.commit()

    try:
        yield user_id, factory
    finally:
        async with factory() as cleanup:
            await cleanup.execute(
                text("DELETE FROM wallet_transactions WHERE user_id = :u"), {"u": user_id}
            )
            await cleanup.execute(text("DELETE FROM users WHERE id = :u"), {"u": user_id})
            await cleanup.commit()


async def test_a_second_debit_waits_and_then_sees_the_new_balance(
    engine: AsyncEngine,
) -> None:
    """**The guard on the row lock in debit(), and the reason it exists.**

    Two purchases of 900 against a balance of 1000. The second starts while the
    first is still uncommitted, so without the lock it reads the old balance and
    succeeds too — leaving the wallet at −800.

    The lock makes it block; the wait_for proves it blocked; once the first
    commits, the second wakes, re-reads, and is correctly refused.

    Verified to fail when the lock is removed. Two earlier attempts did not:

    - Racing two tasks with asyncio.gather passed with the lock gone, because
      the interleaving that triggers the bug never actually happened.
    - Asserting that SELECT ... FOR UPDATE NOWAIT is refused also passed with
      the lock gone — inserting a wallet_transactions row takes a FOR KEY SHARE
      lock on the parent users row all by itself, via the foreign key, and that
      already conflicts with FOR UPDATE. The test measured PostgreSQL's FK
      behaviour, not ours. (FOR KEY SHARE does not conflict with itself, which
      is why it does not prevent the race.)

    Both were removed. A test that passes whether or not the code is there is
    worse than no test, because it is trusted.
    """
    async with _funded_user(engine, email="wait@nordconstruct.md", balance_bani=100000) as (
        user_id,
        factory,
    ):
        async def second_purchase() -> str:
            async with factory() as own:
                try:
                    await wallet_service.debit(
                        own, user_id=user_id, amount_bani=90000, kind="purchase", description="a doua"
                    )
                    await own.commit()
                    return "ok"
                except wallet_service.InsufficientFunds:
                    await own.rollback()
                    return "refused"

        task: asyncio.Task[str] | None = None
        first = factory()
        await first.__aenter__()

        # try/finally, not a bare block: when this test fails it fails while
        # `first` still holds an uncommitted row lock, and the fixture's cleanup
        # DELETE would then wait on that lock forever. A failing test must fail,
        # not hang.
        try:
            await wallet_service.debit(
                first, user_id=user_id, amount_bani=90000, kind="purchase", description="prima"
            )

            task = asyncio.create_task(second_purchase())

            # It must still be blocked on the lock. If this does not time out,
            # the second debit sailed past an uncommitted first — the exact bug.
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(asyncio.shield(task), timeout=1.0)

            await first.commit()
        finally:
            await first.__aexit__(None, None, None)

        assert task is not None
        assert await asyncio.wait_for(task, timeout=10) == "refused"

        async with factory() as check:
            balance = await wallet_service.get_balance(check, user_id=user_id)

        assert balance == 10000, f"Balance is {balance}; it must never go negative"


# ─── Top-up ──────────────────────────────────────────────────────────────────


async def test_top_up_charges_the_card_and_credits_the_wallet(session: AsyncSession) -> None:
    user = await _user(session)
    card = await _card(session, user)
    provider = MockPaymentProvider()

    transaction = await wallet_service.top_up(
        session, provider=provider, user_id=user.id, card_id=card.id, amount_bani=330000
    )

    assert transaction.amount_bani == 330000
    assert transaction.kind == "topup"
    assert await wallet_service.get_balance(session, user_id=user.id) == 330000


async def test_top_up_records_the_provider_charge_id(session: AsyncSession) -> None:
    """The thread back to the acquirer.

    If the credit fails after the charge succeeded, this id is the only way to
    find the money again.
    """
    user = await _user(session)
    card = await _card(session, user)

    transaction = await wallet_service.top_up(
        session,
        provider=MockPaymentProvider(),
        user_id=user.id,
        card_id=card.id,
        amount_bani=100000,
    )

    assert transaction.provider_charge_id is not None
    assert transaction.provider_charge_id.startswith("mock_ch_")


async def test_top_up_with_another_users_card_is_refused(session: AsyncSession) -> None:
    """Otherwise anyone could charge anyone else's card."""
    ion = await _user(session, "ion@nordconstruct.md")
    maria = await _user(session, "maria@altfel.md")
    ion_card = await _card(session, ion)

    with pytest.raises(wallet_service.CardNotFound):
        await wallet_service.top_up(
            session,
            provider=MockPaymentProvider(),
            user_id=maria.id,
            card_id=ion_card.id,
            amount_bani=100000,
        )


async def test_top_up_with_an_unknown_card_is_refused(session: AsyncSession) -> None:
    user = await _user(session)

    with pytest.raises(wallet_service.CardNotFound):
        await wallet_service.top_up(
            session,
            provider=MockPaymentProvider(),
            user_id=user.id,
            card_id=uuid.uuid4(),
            amount_bani=100000,
        )


async def test_transactions_are_newest_first(session: AsyncSession) -> None:
    user = await _user(session)

    await wallet_service.credit(
        session, user_id=user.id, amount_bani=100000, kind="topup", description="prima"
    )
    await wallet_service.credit(
        session, user_id=user.id, amount_bani=200000, kind="topup", description="a doua"
    )

    transactions = await wallet_service.list_transactions(session, user_id=user.id)

    assert [t.description for t in transactions] == ["a doua", "prima"]

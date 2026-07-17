"""Checkout: the money path.

Two kinds of test, because they need two kinds of database access.

- **Behaviour over HTTP** uses the shared rolled-back session: status codes,
  totals, the cart emptying, isolation between users.
- **Atomicity** cannot use that session — proving a rollback restores a
  *committed* balance needs real, separate transactions. Those tests commit
  their setup on a real connection and verify from another, exactly as the
  wallet concurrency test does, and clean up after themselves.

The atomicity property is the point of the phase: a purchase either fully
happens or fully does not.
"""

from __future__ import annotations

import uuid
from contextlib import asynccontextmanager

import pytest
from httpx import AsyncClient
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models.cart import CartItem
from app.models.user import User
from app.services import cart as cart_service
from app.services import checkout as checkout_service
from app.services import wallet as wallet_service

from .factories import create_template

PASSWORD = "parola-mea-sigura-2026"


async def _register(client: AsyncClient, email: str = "ion@nordconstruct.md") -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Ion Popescu"},
    )
    assert response.status_code == 201, response.text


async def _user_id(session: AsyncSession, email: str = "ion@nordconstruct.md") -> uuid.UUID:
    user = await session.scalar(select(User).where(User.email == email))
    assert user is not None
    return user.id


async def _fund(session: AsyncSession, *, user_id: uuid.UUID, amount_bani: int) -> None:
    await wallet_service.credit(
        session, user_id=user_id, amount_bani=amount_bani, kind="topup", description="Alimentare"
    )
    await session.commit()


# ─── Auth boundary ───────────────────────────────────────────────────────────


async def test_checkout_requires_authentication(client: AsyncClient) -> None:
    assert (await client.post("/api/v1/orders", json={})).status_code == 401
    assert (await client.get("/api/v1/orders")).status_code == 401


# ─── The happy path ──────────────────────────────────────────────────────────


async def test_a_funded_purchase_creates_a_paid_order(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_template(session, slug="prestari-servicii", price_bani=90000, name="Prestări")
    await _register(client)
    await _fund(session, user_id=await _user_id(session), amount_bani=200000)
    await client.post("/api/v1/cart/items", json={"slug": "prestari-servicii"})

    response = await client.post("/api/v1/orders", json={})

    assert response.status_code == 201, response.text
    order = response.json()
    assert order["status"] == "paid"
    assert order["total_bani"] == 90000
    assert order["payment_method"] == "wallet"
    assert order["number"].startswith("CT-")
    assert order["paid_at"] is not None
    assert len(order["items"]) == 1
    assert order["items"][0]["name_snapshot"] == "Prestări"
    assert order["items"][0]["unit_price_bani"] == 90000
    assert order["net_bani"] + order["vat_bani"] == 90000


async def test_paying_debits_the_wallet_exactly_once(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_template(session, slug="a", price_bani=90000)
    await _register(client)
    await _fund(session, user_id=await _user_id(session), amount_bani=200000)
    await client.post("/api/v1/cart/items", json={"slug": "a"})

    await client.post("/api/v1/orders", json={})

    balance = (await client.get("/api/v1/wallet/balance")).json()
    assert balance["balance_bani"] == 110000


async def test_checkout_empties_the_cart(client: AsyncClient, session: AsyncSession) -> None:
    await create_template(session, slug="a", price_bani=90000)
    await _register(client)
    await _fund(session, user_id=await _user_id(session), amount_bani=200000)
    await client.post("/api/v1/cart/items", json={"slug": "a"})

    await client.post("/api/v1/orders", json={})

    assert (await client.get("/api/v1/cart")).json()["item_count"] == 0


async def test_the_purchase_appears_in_history_and_is_fetchable(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_template(session, slug="a", price_bani=90000)
    await _register(client)
    await _fund(session, user_id=await _user_id(session), amount_bani=200000)
    await client.post("/api/v1/cart/items", json={"slug": "a"})
    order_id = (await client.post("/api/v1/orders", json={})).json()["id"]

    history = (await client.get("/api/v1/orders")).json()
    assert [o["id"] for o in history] == [order_id]

    fetched = await client.get(f"/api/v1/orders/{order_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == order_id


async def test_a_multi_item_order_totals_every_line(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_template(session, slug="a", price_bani=90000)
    await create_template(session, slug="b", price_bani=120000)
    await _register(client)
    await _fund(session, user_id=await _user_id(session), amount_bani=300000)
    await client.post("/api/v1/cart/items", json={"slug": "a"})
    await client.post("/api/v1/cart/items", json={"slug": "b"})

    order = (await client.post("/api/v1/orders", json={})).json()

    assert order["total_bani"] == 210000
    assert len(order["items"]) == 2


# ─── Refusals over HTTP ──────────────────────────────────────────────────────


async def test_insufficient_funds_is_402_and_the_cart_survives(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The user-facing contract. Atomicity itself is proven below on a real
    connection; here we check the 402, the shortfall headers, and that the cart
    is left intact so the next step is simply to top up."""
    await create_template(session, slug="a", price_bani=90000)
    await _register(client)
    await _fund(session, user_id=await _user_id(session), amount_bani=50000)
    await client.post("/api/v1/cart/items", json={"slug": "a"})

    response = await client.post("/api/v1/orders", json={})

    assert response.status_code == 402
    assert response.headers["X-Required-Bani"] == "90000"
    assert response.headers["X-Balance-Bani"] == "50000"
    assert (await client.get("/api/v1/wallet/balance")).json()["balance_bani"] == 50000
    assert (await client.get("/api/v1/cart")).json()["item_count"] == 1


async def test_checking_out_an_empty_cart_is_refused(client: AsyncClient) -> None:
    await _register(client)

    response = await client.post("/api/v1/orders", json={})

    assert response.status_code == 400


async def test_a_bought_template_cannot_be_added_again(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Owning a document is forever — the file is identical on a second buy."""
    await create_template(session, slug="a", price_bani=90000)
    await _register(client)
    await _fund(session, user_id=await _user_id(session), amount_bani=200000)
    await client.post("/api/v1/cart/items", json={"slug": "a"})
    await client.post("/api/v1/orders", json={})

    response = await client.post("/api/v1/cart/items", json={"slug": "a"})

    assert response.status_code == 409


async def test_orders_are_not_visible_across_users(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_template(session, slug="a", price_bani=90000)
    await _register(client, "ion@nordconstruct.md")
    ion_id = await _user_id(session, "ion@nordconstruct.md")
    await _fund(session, user_id=ion_id, amount_bani=200000)
    await client.post("/api/v1/cart/items", json={"slug": "a"})
    ion_order = (await client.post("/api/v1/orders", json={})).json()["id"]
    await client.post("/api/v1/auth/logout")

    await _register(client, "maria@altfel.md")

    assert (await client.get("/api/v1/orders")).json() == []
    assert (await client.get(f"/api/v1/orders/{ion_order}")).status_code == 404


# ─── Atomicity, against real connections ─────────────────────────────────────


@asynccontextmanager
async def _committed_world(engine: AsyncEngine, *, balance_bani: int, price_bani: int = 90000):
    """A committed user with a funded wallet and one item in the cart.

    Real commits, so a rollback under test cannot quietly erase the setup along
    with the thing it is meant to undo. Everything is truncated afterwards so
    the committed rows do not leak into the rolled-back tests.
    """
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as setup:
        user = User(email="buyer@test.md", password_hash="x", full_name="Buyer")
        setup.add(user)
        await setup.flush()
        user_id = user.id
        template = await create_template(setup, slug="atomic", price_bani=price_bani)
        cart = await cart_service.get_or_create_cart(setup, user_id=user_id)
        setup.add(CartItem(cart_id=cart.id, template_id=template.id))
        await wallet_service.credit(
            setup, user_id=user_id, amount_bani=balance_bani, kind="topup", description="x"
        )
        await setup.commit()

    try:
        yield user_id, factory
    finally:
        async with factory() as cleanup:
            await cleanup.execute(
                text("TRUNCATE users, categories RESTART IDENTITY CASCADE")
            )
            await cleanup.commit()


async def test_insufficient_funds_persists_nothing(engine: AsyncEngine) -> None:
    """Fails mid-transaction: the order is flushed, then the debit refuses.

    Nothing may survive it — no order, no movement of money — and the cart must
    be exactly as it was.
    """
    async with _committed_world(engine, balance_bani=50000) as (user_id, factory):
        async with factory() as attempt:
            with pytest.raises(wallet_service.InsufficientFunds):
                await checkout_service.checkout(attempt, user_id=user_id)
            await attempt.rollback()

        async with factory() as check:
            assert await wallet_service.get_balance(check, user_id=user_id) == 50000
            assert await checkout_service.list_orders(check, user_id=user_id) == []
            assert len(await cart_service.get_cart_items(check, user_id=user_id)) == 1


async def test_a_failure_after_the_debit_rolls_the_debit_back(
    engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The hardest case: the money moves, then something downstream breaks.

    If emptying the cart throws after a successful debit, a rollback must
    restore the balance in full and leave no order. Money taken and then lost is
    the one outcome worse than a failed sale. The failure is injected between
    the debit and the cart-clear, which no HTTP request could provoke.
    """
    async with _committed_world(engine, balance_bani=200000) as (user_id, factory):

        def boom(*_args: object, **_kwargs: object) -> object:
            raise RuntimeError("storage went away while emptying the cart")

        monkeypatch.setattr(cart_service, "clear_cart", boom)

        async with factory() as attempt:
            with pytest.raises(RuntimeError):
                await checkout_service.checkout(attempt, user_id=user_id)
            # In production this exception propagates and get_session rolls the
            # session back on close; here we roll back explicitly — same guarantee.
            await attempt.rollback()

        async with factory() as check:
            assert await wallet_service.get_balance(check, user_id=user_id) == 200000
            assert await checkout_service.list_orders(check, user_id=user_id) == []

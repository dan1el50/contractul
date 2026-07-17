"""Wallet endpoints over HTTP.

Two themes: money is never exposed to tampering, and card data never leaks.
"""

from __future__ import annotations

import uuid

import pytest
from httpx import AsyncClient

from app.api.deps import get_payments
from app.integrations.payments.mock import DECLINE_CARD, MockPaymentProvider
from app.main import app

GOOD_CARD = "4242424242424242"
PASSWORD = "parola-mea-sigura-2026"


@pytest.fixture(autouse=True)
def payments() -> MockPaymentProvider:
    """One provider per test, so charges do not leak between them."""
    provider = MockPaymentProvider()
    app.dependency_overrides[get_payments] = lambda: provider
    yield provider
    app.dependency_overrides.pop(get_payments, None)


async def _register(client: AsyncClient, email: str = "ion@nordconstruct.md") -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Ion Popescu"},
    )
    assert response.status_code == 201


async def _add_card(client: AsyncClient, number: str = GOOD_CARD) -> str:
    response = await client.post(
        "/api/v1/wallet/cards",
        json={"number": number, "exp_month": 9, "exp_year": 2028, "cvv": "123"},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


# ─── Auth boundary ───────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/wallet/balance"),
        ("GET", "/api/v1/wallet/transactions"),
        ("GET", "/api/v1/wallet/cards"),
        ("POST", "/api/v1/wallet/top-up"),
        ("POST", "/api/v1/wallet/cards"),
    ],
)
async def test_wallet_requires_authentication(
    client: AsyncClient, method: str, path: str
) -> None:
    response = await client.request(method, path, json={})

    assert response.status_code == 401


# ─── Balance and top-up ──────────────────────────────────────────────────────


async def test_a_new_wallet_reads_zero(client: AsyncClient) -> None:
    await _register(client)

    body = (await client.get("/api/v1/wallet/balance")).json()

    assert body["balance_bani"] == 0
    assert body["balance_mdl"] == "0"


async def test_top_up_raises_the_balance(client: AsyncClient) -> None:
    await _register(client)
    card_id = await _add_card(client)

    response = await client.post(
        "/api/v1/wallet/top-up", json={"card_id": card_id, "amount_bani": 330000}
    )

    assert response.status_code == 201
    balance = (await client.get("/api/v1/wallet/balance")).json()
    assert balance["balance_bani"] == 330000
    assert balance["balance_mdl"] == "3 300"


async def test_top_up_appears_in_the_history(client: AsyncClient) -> None:
    await _register(client)
    card_id = await _add_card(client)
    await client.post("/api/v1/wallet/top-up", json={"card_id": card_id, "amount_bani": 330000})

    transactions = (await client.get("/api/v1/wallet/transactions")).json()

    assert len(transactions) == 1
    assert transactions[0]["kind"] == "topup"
    assert transactions[0]["amount_mdl"] == "+ 3 300"


async def test_a_declined_card_does_not_credit_the_wallet(client: AsyncClient) -> None:
    """A decline at top-up must leave the balance untouched."""
    await _register(client)
    # Adding the decline card fails at tokenisation, so charge one that works
    # and make the provider refuse instead.
    card_id = await _add_card(client)
    app.dependency_overrides[get_payments] = lambda: _AlwaysDeclines()

    response = await client.post(
        "/api/v1/wallet/top-up", json={"card_id": card_id, "amount_bani": 330000}
    )

    assert response.status_code == 402
    assert (await client.get("/api/v1/wallet/balance")).json()["balance_bani"] == 0


async def test_topping_up_someone_elses_card_is_404(client: AsyncClient) -> None:
    """Charging a stranger's card must be impossible, not merely discouraged."""
    await _register(client, "ion@nordconstruct.md")
    ion_card = await _add_card(client)
    await client.post("/api/v1/auth/logout")
    await _register(client, "maria@altfel.md")

    response = await client.post(
        "/api/v1/wallet/top-up", json={"card_id": ion_card, "amount_bani": 100000}
    )

    assert response.status_code == 404


async def test_top_up_below_the_minimum_is_rejected(client: AsyncClient) -> None:
    await _register(client)
    card_id = await _add_card(client)

    response = await client.post(
        "/api/v1/wallet/top-up", json={"card_id": card_id, "amount_bani": 100}
    )

    assert response.status_code == 422


async def test_a_negative_top_up_cannot_drain_the_wallet(client: AsyncClient) -> None:
    """The obvious attack: top up by a negative amount.

    Rejected by the schema's bounds rather than by anything in the service, so
    it never reaches the money code at all.
    """
    await _register(client)
    card_id = await _add_card(client)

    response = await client.post(
        "/api/v1/wallet/top-up", json={"card_id": card_id, "amount_bani": -500000}
    )

    assert response.status_code == 422
    assert (await client.get("/api/v1/wallet/balance")).json()["balance_bani"] == 0


async def test_wallets_are_not_visible_across_users(client: AsyncClient) -> None:
    await _register(client, "ion@nordconstruct.md")
    card_id = await _add_card(client)
    await client.post("/api/v1/wallet/top-up", json={"card_id": card_id, "amount_bani": 330000})
    await client.post("/api/v1/auth/logout")

    await _register(client, "maria@altfel.md")

    assert (await client.get("/api/v1/wallet/balance")).json()["balance_bani"] == 0
    assert (await client.get("/api/v1/wallet/transactions")).json() == []


# ─── Cards ───────────────────────────────────────────────────────────────────


async def test_adding_a_card_returns_only_safe_fields(client: AsyncClient) -> None:
    """**No PAN, no CVV, no provider token, ever.**

    The token is a bearer credential for charging the card; the PAN would put
    us in PCI-DSS scope. CardResponse lists its fields explicitly, which is what
    stops any of them leaking.
    """
    await _register(client)

    response = await client.post(
        "/api/v1/wallet/cards",
        json={"number": GOOD_CARD, "exp_month": 9, "exp_year": 2028, "cvv": "123"},
    )

    body = response.json()
    assert body["brand"] == "visa"
    assert body["last4"] == "4242"
    assert "provider_token" not in body
    assert "number" not in body
    assert "cvv" not in body
    assert GOOD_CARD not in response.text
    assert "123" not in str(body)


async def test_a_declined_card_is_not_saved(client: AsyncClient) -> None:
    await _register(client)

    response = await client.post(
        "/api/v1/wallet/cards",
        json={"number": DECLINE_CARD, "exp_month": 9, "exp_year": 2028, "cvv": "123"},
    )

    assert response.status_code == 402
    assert (await client.get("/api/v1/wallet/cards")).json() == []


async def test_the_first_card_becomes_the_default(client: AsyncClient) -> None:
    """A user with cards but no default has nothing to pre-select at checkout."""
    await _register(client)

    body = (await client.post(
        "/api/v1/wallet/cards",
        json={"number": GOOD_CARD, "exp_month": 9, "exp_year": 2028, "cvv": "123"},
    )).json()

    assert body["is_default"] is True


async def test_only_one_card_is_ever_default(client: AsyncClient) -> None:
    await _register(client)
    await _add_card(client, "4242424242424242")
    await client.post(
        "/api/v1/wallet/cards",
        json={
            "number": "5555555555554444",
            "exp_month": 3,
            "exp_year": 2027,
            "cvv": "123",
            "make_default": True,
        },
    )

    cards = (await client.get("/api/v1/wallet/cards")).json()

    assert sum(1 for c in cards if c["is_default"]) == 1


async def test_deleting_the_default_promotes_another(client: AsyncClient) -> None:
    await _register(client)
    first = await _add_card(client, "4242424242424242")
    await _add_card(client, "5555555555554444")

    await client.delete(f"/api/v1/wallet/cards/{first}")

    cards = (await client.get("/api/v1/wallet/cards")).json()
    assert len(cards) == 1
    assert cards[0]["is_default"] is True


async def test_deleting_someone_elses_card_is_404(client: AsyncClient) -> None:
    await _register(client, "ion@nordconstruct.md")
    ion_card = await _add_card(client)
    await client.post("/api/v1/auth/logout")
    await _register(client, "maria@altfel.md")

    response = await client.delete(f"/api/v1/wallet/cards/{ion_card}")

    assert response.status_code == 404


async def test_cards_are_not_visible_across_users(client: AsyncClient) -> None:
    await _register(client, "ion@nordconstruct.md")
    await _add_card(client)
    await client.post("/api/v1/auth/logout")
    await _register(client, "maria@altfel.md")

    assert (await client.get("/api/v1/wallet/cards")).json() == []


async def test_an_unknown_card_id_is_404_not_500(client: AsyncClient) -> None:
    await _register(client)

    response = await client.delete(f"/api/v1/wallet/cards/{uuid.uuid4()}")

    assert response.status_code == 404


class _AlwaysDeclines:
    """A provider that refuses every charge."""

    def tokenise_card(self, **_kwargs: object) -> object:
        raise NotImplementedError

    def charge(self, **_kwargs: object) -> object:
        from app.integrations.payments.base import CardDeclined

        raise CardDeclined("refuzat")

    def refund(self, **_kwargs: object) -> object:
        raise NotImplementedError

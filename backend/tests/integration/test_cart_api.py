"""Cart endpoints over HTTP.

The cart holds template ids and reads prices live from the catalog — a price
the client can edit is not a price — so these tests watch the server, not the
payload, decide what a line costs.
"""

from __future__ import annotations

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from .factories import create_template

PASSWORD = "parola-mea-sigura-2026"


async def _register(client: AsyncClient, email: str = "ion@nordconstruct.md") -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Ion Popescu"},
    )
    assert response.status_code == 201, response.text


# ─── Auth boundary ───────────────────────────────────────────────────────────


async def test_cart_requires_authentication(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/cart")).status_code == 401
    assert (await client.post("/api/v1/cart/items", json={"slug": "x"})).status_code == 401


# ─── Contents ────────────────────────────────────────────────────────────────


async def test_a_new_cart_is_empty(client: AsyncClient) -> None:
    await _register(client)

    body = (await client.get("/api/v1/cart")).json()

    assert body["items"] == []
    assert body["item_count"] == 0
    assert body["total_bani"] == 0


async def test_adding_a_template_puts_it_in_the_cart_at_the_catalog_price(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_template(session, slug="prestari-servicii", price_bani=90000)
    await _register(client)

    response = await client.post("/api/v1/cart/items", json={"slug": "prestari-servicii"})

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["item_count"] == 1
    assert body["items"][0]["slug"] == "prestari-servicii"
    # The price is the catalog's, not anything the client sent.
    assert body["items"][0]["price_bani"] == 90000
    assert body["total_bani"] == 90000


async def test_the_total_sums_the_lines(client: AsyncClient, session: AsyncSession) -> None:
    await create_template(session, slug="a", price_bani=90000)
    await create_template(session, slug="b", price_bani=120000)
    await _register(client)

    await client.post("/api/v1/cart/items", json={"slug": "a"})
    body = (await client.post("/api/v1/cart/items", json={"slug": "b"})).json()

    assert body["item_count"] == 2
    assert body["total_bani"] == 210000
    assert body["total_mdl"] == "2 100"


async def test_the_response_carries_the_vat_split(
    client: AsyncClient, session: AsyncSession
) -> None:
    """VAT is derived for display and must add back to the total, in bani."""
    await create_template(session, slug="a", price_bani=90000)
    await _register(client)

    body = (await client.post("/api/v1/cart/items", json={"slug": "a"})).json()

    assert body["net_bani"] + body["vat_bani"] == body["total_bani"]
    assert body["vat_bani"] == 15000


async def test_adding_the_same_template_twice_is_idempotent(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Buying the same document twice is meaningless — the file is identical."""
    await create_template(session, slug="a", price_bani=90000)
    await _register(client)

    await client.post("/api/v1/cart/items", json={"slug": "a"})
    body = (await client.post("/api/v1/cart/items", json={"slug": "a"})).json()

    assert body["item_count"] == 1


async def test_adding_an_unknown_template_is_404(client: AsyncClient) -> None:
    await _register(client)

    response = await client.post("/api/v1/cart/items", json={"slug": "does-not-exist"})

    assert response.status_code == 404


async def test_removing_a_template_takes_it_out(client: AsyncClient, session: AsyncSession) -> None:
    template = await create_template(session, slug="a", price_bani=90000)
    await _register(client)
    await client.post("/api/v1/cart/items", json={"slug": "a"})

    response = await client.delete(f"/api/v1/cart/items/{template.id}")

    assert response.status_code == 204
    assert (await client.get("/api/v1/cart")).json()["item_count"] == 0


async def test_removing_something_not_in_the_cart_is_still_204(client: AsyncClient) -> None:
    await _register(client)

    response = await client.delete(f"/api/v1/cart/items/{uuid.uuid4()}")

    assert response.status_code == 204


async def test_carts_are_not_visible_across_users(
    client: AsyncClient, session: AsyncSession
) -> None:
    await create_template(session, slug="a", price_bani=90000)
    await _register(client, "ion@nordconstruct.md")
    await client.post("/api/v1/cart/items", json={"slug": "a"})
    await client.post("/api/v1/auth/logout")

    await _register(client, "maria@altfel.md")

    assert (await client.get("/api/v1/cart")).json()["item_count"] == 0

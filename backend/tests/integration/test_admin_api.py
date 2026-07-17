"""Admin endpoints over HTTP.

Two themes: the guard actually keeps non-admins out, and the aggregates count
what they claim to.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Category
from app.models.order import Order, OrderItem
from app.models.user import User

from .factories import create_template

PASSWORD = "parola-mea-sigura-2026"

# A real, convertible .docx — the same placeholder the seed uses.
FIXTURE_DOCX = Path("tests/fixtures/activare-2fa.docx")
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def _a_category(session: AsyncSession) -> Category:
    category = Category(slug="servicii", name="Servicii & Colaborare")
    session.add(category)
    await session.flush()
    return category


async def _register(client: AsyncClient, email: str) -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Cineva"},
    )
    assert response.status_code == 201, response.text


async def _promote(session: AsyncSession, email: str) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    assert user is not None
    user.is_admin = True
    await session.flush()
    return user


async def _become_admin(client: AsyncClient, session: AsyncSession) -> User:
    await _register(client, "admin@crowe.md")
    return await _promote(session, "admin@crowe.md")


async def _paid_order(
    session: AsyncSession, *, user: User, template_id: uuid.UUID, version_id: uuid.UUID,
    number: str, total_bani: int, name: str,
) -> None:
    order = Order(
        user_id=user.id,
        number=number,
        status="paid",
        total_bani=total_bani,
        payment_method="wallet",
    )
    order.items.append(
        OrderItem(
            template_id=template_id,
            template_version_id=version_id,
            name_snapshot=name,
            unit_price_bani=total_bani,
        )
    )
    session.add(order)
    await session.flush()


# ─── The guard ───────────────────────────────────────────────────────────────


async def test_admin_endpoints_reject_anonymous(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/admin/stats")).status_code == 401


async def test_admin_endpoints_reject_a_normal_user(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A signed-in customer must be refused — 403, not 401."""
    await _register(client, "ion@nordconstruct.md")

    for path in ["/api/v1/admin/stats", "/api/v1/admin/orders", "/api/v1/admin/templates"]:
        response = await client.get(path)
        assert response.status_code == 403, path


async def test_an_admin_is_allowed_in(client: AsyncClient, session: AsyncSession) -> None:
    await _become_admin(client, session)

    assert (await client.get("/api/v1/admin/stats")).status_code == 200


# ─── Aggregates ──────────────────────────────────────────────────────────────


async def test_stats_count_paid_revenue_and_catalog(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _become_admin(client, session)
    template = await create_template(session, slug="a", price_bani=90000)
    version = template.versions[0]
    await _paid_order(
        session, user=admin, template_id=template.id, version_id=version.id,
        number="CT-2026-9001", total_bani=90000, name="Contract A",
    )

    body = (await client.get("/api/v1/admin/stats")).json()

    assert body["revenue_bani"] == 90000
    assert body["revenue_mdl"] == "900"
    assert body["paid_orders"] == 1
    assert body["users"] >= 1
    assert body["published_templates"] == 1


async def test_revenue_series_has_a_bucket_per_month_and_sums_paid(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _become_admin(client, session)
    template = await create_template(session, slug="a", price_bani=90000)
    version = template.versions[0]
    await _paid_order(
        session, user=admin, template_id=template.id, version_id=version.id,
        number="CT-2026-9002", total_bani=90000, name="Contract A",
    )

    series = (await client.get("/api/v1/admin/revenue")).json()

    assert len(series) == 6  # six months, gaps filled
    # This month's bucket (the last one) carries the paid order.
    assert series[-1]["revenue_bani"] == 90000
    assert sum(m["revenue_bani"] for m in series) == 90000


async def test_recent_orders_show_client_and_total(
    client: AsyncClient, session: AsyncSession
) -> None:
    admin = await _become_admin(client, session)
    template = await create_template(session, slug="a", price_bani=120000)
    version = template.versions[0]
    await _paid_order(
        session, user=admin, template_id=template.id, version_id=version.id,
        number="CT-2026-9003", total_bani=120000, name="Contract de transport",
    )

    orders = (await client.get("/api/v1/admin/orders")).json()

    assert orders[0]["number"] == "CT-2026-9003"
    assert orders[0]["client_email"] == "admin@crowe.md"
    assert orders[0]["total_mdl"] == "1 200"
    assert orders[0]["first_item"] == "Contract de transport"


# ─── Template management ─────────────────────────────────────────────────────


async def test_templates_list_includes_unpublished(
    client: AsyncClient, session: AsyncSession
) -> None:
    """The catalog hides drafts; the admin must see them."""
    await _become_admin(client, session)
    published = await create_template(session, slug="pub", price_bani=90000)
    draft = await create_template(session, slug="draft", price_bani=90000)
    draft.is_published = False
    await session.flush()

    slugs = {t["slug"] for t in (await client.get("/api/v1/admin/templates")).json()}

    assert {"pub", "draft"} <= slugs
    assert published.slug in slugs


async def test_unpublishing_a_template_hides_it_from_the_catalog(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _become_admin(client, session)
    template = await create_template(session, slug="a", price_bani=90000)

    # Visible in the public catalog to start.
    assert any(t["slug"] == "a" for t in (await client.get("/api/v1/templates")).json())

    patched = await client.patch(
        f"/api/v1/admin/templates/{template.id}", json={"is_published": False}
    )
    assert patched.status_code == 200
    assert patched.json()["is_published"] is False

    # Now gone from the public catalog, still present for the admin.
    assert not any(t["slug"] == "a" for t in (await client.get("/api/v1/templates")).json())
    assert any(t["slug"] == "a" for t in (await client.get("/api/v1/admin/templates")).json())


async def test_publishing_an_unknown_template_is_404(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _become_admin(client, session)

    response = await client.patch(
        f"/api/v1/admin/templates/{uuid.uuid4()}", json={"is_published": True}
    )

    assert response.status_code == 404


# ─── Adding a template (docx upload) ─────────────────────────────────────────


async def test_admin_adds_a_template_by_uploading_a_docx(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _become_admin(client, session)
    category = await _a_category(session)

    response = await client.post(
        "/api/v1/admin/templates",
        data={
            "name": "Contract nou de test",
            "category_id": str(category.id),
            "description": "Un contract adăugat de admin.",
            "price_bani": "90000",
            "languages": "ro,ru",
            "is_published": "true",
        },
        files={"file": ("nou.docx", FIXTURE_DOCX.read_bytes(), DOCX_MIME)},
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Contract nou de test"
    assert body["price_mdl"] == "900"
    assert body["is_published"] is True
    # It shows up for the admin and, being published, in the public catalog.
    admin_slugs = {t["slug"] for t in (await client.get("/api/v1/admin/templates")).json()}
    public_slugs = {t["slug"] for t in (await client.get("/api/v1/templates")).json()}
    assert body["slug"] in admin_slugs
    assert body["slug"] in public_slugs


async def test_uploading_a_file_that_is_not_a_docx_is_rejected(
    client: AsyncClient, session: AsyncSession
) -> None:
    """Validation by rendering: a non-.docx cannot become a catalog entry."""
    await _become_admin(client, session)
    category = await _a_category(session)

    response = await client.post(
        "/api/v1/admin/templates",
        data={
            "name": "Fișier stricat",
            "category_id": str(category.id),
            "description": "x",
            "price_bani": "90000",
            "languages": "ro",
        },
        files={"file": ("bad.docx", b"this is plainly not a docx", "application/octet-stream")},
    )

    assert response.status_code == 400


async def test_adding_a_template_requires_admin(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _register(client, "ion@nordconstruct.md")
    category = await _a_category(session)

    response = await client.post(
        "/api/v1/admin/templates",
        data={
            "name": "Nepermis",
            "category_id": str(category.id),
            "description": "x",
            "price_bani": "90000",
            "languages": "ro",
        },
        files={"file": ("t.docx", FIXTURE_DOCX.read_bytes(), DOCX_MIME)},
    )

    assert response.status_code == 403


# ─── Removing a template ─────────────────────────────────────────────────────


async def test_admin_deletes_a_template_with_no_sales(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _become_admin(client, session)
    template = await create_template(session, slug="de-sters", price_bani=90000)

    response = await client.delete(f"/api/v1/admin/templates/{template.id}")

    assert response.status_code == 204
    slugs = {t["slug"] for t in (await client.get("/api/v1/admin/templates")).json()}
    assert "de-sters" not in slugs


async def test_deleting_a_sold_template_is_refused(
    client: AsyncClient, session: AsyncSession
) -> None:
    """An order references it, so deleting it would orphan a receipt."""
    admin = await _become_admin(client, session)
    template = await create_template(session, slug="vandut", price_bani=90000)
    version = template.versions[0]
    await _paid_order(
        session, user=admin, template_id=template.id, version_id=version.id,
        number="CT-2026-9100", total_bani=90000, name="Vândut",
    )

    response = await client.delete(f"/api/v1/admin/templates/{template.id}")

    assert response.status_code == 409
    # Still there — refused, not silently removed.
    assert any(t["slug"] == "vandut" for t in (await client.get("/api/v1/admin/templates")).json())


async def test_deleting_a_template_requires_admin(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _register(client, "ion@nordconstruct.md")
    template = await create_template(session, slug="x", price_bani=90000)

    response = await client.delete(f"/api/v1/admin/templates/{template.id}")

    assert response.status_code == 403

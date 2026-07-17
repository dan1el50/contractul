"""Settings endpoints over HTTP: profile, password, company.

The password path is the one with teeth — a change must require the current
password, and it must end other sessions.
"""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.user import User
from app.services import auth as auth_service
from app.services import settings as settings_service

PASSWORD = "parola-mea-sigura-2026"


async def _register(client: AsyncClient, email: str = "ion@nordconstruct.md") -> None:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD, "full_name": "Ion Popescu"},
    )
    assert response.status_code == 201, response.text


# ─── Auth boundary ───────────────────────────────────────────────────────────


async def test_settings_require_authentication(client: AsyncClient) -> None:
    assert (await client.patch("/api/v1/settings/profile", json={})).status_code == 401
    assert (await client.get("/api/v1/settings/company")).status_code == 401
    assert (await client.post("/api/v1/settings/password", json={})).status_code == 401


# ─── Profile ─────────────────────────────────────────────────────────────────


async def test_updating_the_profile_changes_name_and_phone(client: AsyncClient) -> None:
    await _register(client)

    response = await client.patch(
        "/api/v1/settings/profile",
        json={"full_name": "Ion V. Popescu", "phone": "+373 79 111 222"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["full_name"] == "Ion V. Popescu"
    assert body["phone"] == "+373 79 111 222"
    # And it sticks for the next request.
    assert (await client.get("/api/v1/auth/me")).json()["full_name"] == "Ion V. Popescu"


async def test_updating_the_profile_never_touches_admin_or_email(client: AsyncClient) -> None:
    """Hopeful extra fields must not escalate privilege or change identity."""
    await _register(client)

    response = await client.patch(
        "/api/v1/settings/profile",
        json={"full_name": "Ion", "is_admin": True, "email": "attacker@evil.md"},
    )

    body = response.json()
    assert body["is_admin"] is False
    assert body["email"] == "ion@nordconstruct.md"


async def test_a_too_short_name_is_rejected(client: AsyncClient) -> None:
    await _register(client)

    response = await client.patch("/api/v1/settings/profile", json={"full_name": "I"})

    assert response.status_code == 422


# ─── Password ────────────────────────────────────────────────────────────────


async def test_changing_the_password_requires_the_current_one(client: AsyncClient) -> None:
    await _register(client)

    response = await client.post(
        "/api/v1/settings/password",
        json={"current_password": "gresit-total", "new_password": "parola-noua-2026"},
    )

    assert response.status_code == 400


async def test_a_correct_change_updates_the_password(client: AsyncClient) -> None:
    await _register(client)

    change = await client.post(
        "/api/v1/settings/password",
        json={"current_password": PASSWORD, "new_password": "parola-noua-2026x"},
    )
    assert change.status_code == 204

    # The old password no longer logs in; the new one does.
    await client.post("/api/v1/auth/logout")
    old = await client.post(
        "/api/v1/auth/login", json={"email": "ion@nordconstruct.md", "password": PASSWORD}
    )
    assert old.status_code == 401
    new = await client.post(
        "/api/v1/auth/login",
        json={"email": "ion@nordconstruct.md", "password": "parola-noua-2026x"},
    )
    assert new.status_code == 200


async def test_the_new_password_must_meet_the_length_bar(client: AsyncClient) -> None:
    await _register(client)

    response = await client.post(
        "/api/v1/settings/password",
        json={"current_password": PASSWORD, "new_password": "scurt"},
    )

    assert response.status_code == 422


async def test_changing_the_password_keeps_the_current_session_alive(client: AsyncClient) -> None:
    """Whoever changed it stays signed in — they keep their cookie."""
    await _register(client)

    await client.post(
        "/api/v1/settings/password",
        json={"current_password": PASSWORD, "new_password": "parola-noua-2026x"},
    )

    assert (await client.get("/api/v1/auth/me")).status_code == 200


async def test_changing_the_password_ends_every_other_session(session: AsyncSession) -> None:
    """A second, open session — a stolen cookie, say — dies the moment the owner
    changes the password. The current session survives; the other does not."""
    user = User(email="x@x.md", password_hash=hash_password(PASSWORD), full_name="X")
    session.add(user)
    await session.flush()

    keep = await auth_service.create_session(session, user=user)
    other = await auth_service.create_session(session, user=user)

    await settings_service.change_password(
        session,
        user=user,
        current_password=PASSWORD,
        new_password="parola-noua-2026x",
        keep_token=keep,
    )

    assert await auth_service.resolve_session(session, token=keep) is not None
    assert await auth_service.resolve_session(session, token=other) is None


# ─── Company ─────────────────────────────────────────────────────────────────


async def test_a_new_user_has_no_company(client: AsyncClient) -> None:
    await _register(client)

    response = await client.get("/api/v1/settings/company")

    assert response.status_code == 200
    assert response.json() is None


async def test_saving_a_company_then_reading_it_back(client: AsyncClient) -> None:
    await _register(client)

    saved = await client.put(
        "/api/v1/settings/company",
        json={
            "name": 'SRL "NordConstruct"',
            "idno": "1234567890123",
            "legal_address": "str. Alexei Șciusev 29, Chișinău",
            "iban": "MD24AG000225100013104168",
            "bank_name": "Victoriabank",
        },
    )

    assert saved.status_code == 200
    assert saved.json()["idno"] == "1234567890123"
    read = await client.get("/api/v1/settings/company")
    assert read.json()["name"] == 'SRL "NordConstruct"'


async def test_saving_the_company_again_updates_rather_than_duplicates(client: AsyncClient) -> None:
    """One company per user — a second save edits the first."""
    await _register(client)
    base = {"name": "A", "idno": "1234567890123"}

    await client.put("/api/v1/settings/company", json=base)
    await client.put("/api/v1/settings/company", json={**base, "name": "B"})

    assert (await client.get("/api/v1/settings/company")).json()["name"] == "B"


async def test_a_malformed_idno_is_rejected(client: AsyncClient) -> None:
    await _register(client)

    for bad in ["123", "12345678901234", "abcdefghijklm"]:
        response = await client.put(
            "/api/v1/settings/company", json={"name": "A", "idno": bad}
        )
        assert response.status_code == 422, bad


async def test_companies_are_not_visible_across_users(client: AsyncClient) -> None:
    await _register(client, "ion@nordconstruct.md")
    await client.put("/api/v1/settings/company", json={"name": "Ion SRL", "idno": "1234567890123"})
    await client.post("/api/v1/auth/logout")

    await _register(client, "maria@altfel.md")

    assert (await client.get("/api/v1/settings/company")).json() is None

"""Rate limiting at the HTTP boundary.

The unit tests prove the limiter's arithmetic. These prove the wiring: that the
auth routes are actually behind it, that a tripped limit is a 429 with a usable
Retry-After, and that each endpoint has its own budget. The per-test reset
fixture in conftest is what keeps these from leaking into every other test.
"""

from httpx import AsyncClient

from app.core.config import get_settings

PASSWORD = "parola-mea-sigura-2026"

REGISTRATION = {
    "email": "ion@nordconstruct.md",
    "password": PASSWORD,
    "full_name": "Ion Popescu",
    "phone": "+373 79 000 000",
}


def _register_payload(index: int) -> dict[str, str]:
    """A registration with a unique email, so only the limit stops it."""
    return {**REGISTRATION, "email": f"user{index}@nordconstruct.md"}


async def test_login_is_blocked_after_the_limit(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=REGISTRATION)
    limit = get_settings().rate_limit_login_max

    # Wrong password every time: these are refused (401) but still count — the
    # limiter runs before the handler, which is the whole point against a
    # brute-force loop that never guesses right.
    for _ in range(limit):
        attempt = await client.post(
            "/api/v1/auth/login",
            json={"email": REGISTRATION["email"], "password": "gresit"},
        )
        assert attempt.status_code == 401

    blocked = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTRATION["email"], "password": "gresit"},
    )
    assert blocked.status_code == 429


async def test_a_blocked_response_carries_a_retry_after(client: AsyncClient) -> None:
    limit = get_settings().rate_limit_login_max

    for _ in range(limit + 1):
        blocked = await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@nowhere.md", "password": "gresit"},
        )

    assert blocked.status_code == 429
    retry_after = blocked.headers.get("retry-after")
    assert retry_after is not None
    # A positive whole number of seconds — a client that waits it out must
    # actually clear the window.
    assert int(retry_after) >= 1


async def test_registration_is_blocked_after_the_limit(client: AsyncClient) -> None:
    limit = get_settings().rate_limit_register_max

    for index in range(limit):
        created = await client.post("/api/v1/auth/register", json=_register_payload(index))
        assert created.status_code == 201

    blocked = await client.post("/api/v1/auth/register", json=_register_payload(limit))
    assert blocked.status_code == 429


async def test_login_and_register_have_separate_budgets(client: AsyncClient) -> None:
    """Exhausting one endpoint must not lock a caller out of the other.

    A user who mistyped a password five times should still be able to register
    — the scopes are keyed apart, so login's limit is not register's.
    """
    for _ in range(get_settings().rate_limit_login_max + 1):
        await client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@nowhere.md", "password": "gresit"},
        )

    # Login is now blocked; register is untouched.
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "nobody@nowhere.md", "password": "gresit"},
    )
    register = await client.post("/api/v1/auth/register", json=REGISTRATION)

    assert login.status_code == 429
    assert register.status_code == 201

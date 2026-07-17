"""The auth endpoints over HTTP.

What the service tests cannot see: status codes, cookie flags, response
shapes, and the dependency wiring. The cookie flags in particular are only
observable here, and getting them wrong is a real vulnerability that no
service-level test would notice.
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

COOKIE = get_settings().session_cookie_name


# ─── Registration ────────────────────────────────────────────────────────────


async def test_register_returns_201_and_the_user(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json=REGISTRATION)

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ion@nordconstruct.md"
    assert body["full_name"] == "Ion Popescu"
    assert body["is_admin"] is False


async def test_register_never_returns_the_password_hash(client: AsyncClient) -> None:
    """UserResponse lists its fields explicitly, which is what prevents this."""
    response = await client.post("/api/v1/auth/register", json=REGISTRATION)

    body = response.json()
    assert "password" not in body
    assert "password_hash" not in body
    assert PASSWORD not in response.text


async def test_register_signs_you_in(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/register", json=REGISTRATION)

    assert COOKIE in response.cookies


async def test_duplicate_registration_returns_409(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=REGISTRATION)

    response = await client.post("/api/v1/auth/register", json=REGISTRATION)

    assert response.status_code == 409


async def test_short_password_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register", json={**REGISTRATION, "password": "scurt"}
    )

    assert response.status_code == 422


async def test_malformed_email_is_rejected(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/register", json={**REGISTRATION, "email": "not-an-email"}
    )

    assert response.status_code == 422


async def test_registration_cannot_grant_admin(client: AsyncClient) -> None:
    """Privilege escalation via a hopeful extra field.

    Pydantic ignores unknown keys, so is_admin is simply not settable from
    outside — but that is worth pinning down rather than trusting.
    """
    response = await client.post(
        "/api/v1/auth/register", json={**REGISTRATION, "is_admin": True}
    )

    assert response.status_code == 201
    assert response.json()["is_admin"] is False


# ─── Cookie flags ────────────────────────────────────────────────────────────


async def test_session_cookie_is_httponly_and_samesite(client: AsyncClient) -> None:
    """Only observable over HTTP, and wrong flags are a real vulnerability.

    HttpOnly keeps JavaScript — and therefore any XSS — away from the session.
    SameSite=Lax stops the cookie riding along on cross-site requests, which is
    what makes CSRF tokens unnecessary here.
    """
    response = await client.post("/api/v1/auth/register", json=REGISTRATION)

    header = response.headers["set-cookie"].lower()
    assert "httponly" in header
    assert "samesite=lax" in header
    assert "path=/" in header


async def test_session_cookie_is_not_secure_in_development(client: AsyncClient) -> None:
    """Secure cookies are HTTPS-only, so a Secure flag here would break local dev.

    Production must set COOKIE_SECURE=true. The flag is configuration, not a
    constant, which is exactly why it is worth asserting both ways.
    """
    response = await client.post("/api/v1/auth/register", json=REGISTRATION)

    assert get_settings().cookie_secure is False
    assert "secure" not in response.headers["set-cookie"].lower()


# ─── Login ───────────────────────────────────────────────────────────────────


async def test_login_with_correct_credentials(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=REGISTRATION)

    response = await client.post(
        "/api/v1/auth/login", json={"email": REGISTRATION["email"], "password": PASSWORD}
    )

    assert response.status_code == 200
    assert COOKIE in response.cookies


async def test_login_with_a_wrong_password_returns_401(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=REGISTRATION)

    response = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTRATION["email"], "password": "parola-gresita-999"},
    )

    assert response.status_code == 401
    assert COOKIE not in response.cookies


async def test_login_errors_do_not_reveal_whether_the_account_exists(
    client: AsyncClient,
) -> None:
    """Account enumeration, at the boundary where it would actually leak."""
    await client.post("/api/v1/auth/register", json=REGISTRATION)

    unknown = await client.post(
        "/api/v1/auth/login", json={"email": "nobody@nowhere.md", "password": PASSWORD}
    )
    wrong_password = await client.post(
        "/api/v1/auth/login",
        json={"email": REGISTRATION["email"], "password": "parola-gresita-999"},
    )

    assert unknown.status_code == wrong_password.status_code == 401
    assert unknown.json() == wrong_password.json()


# ─── /me and the auth boundary ───────────────────────────────────────────────


async def test_me_returns_the_signed_in_user(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=REGISTRATION)

    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 200
    assert response.json()["email"] == "ion@nordconstruct.md"


async def test_me_without_a_cookie_returns_401(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


async def test_me_with_a_forged_cookie_returns_401(client: AsyncClient) -> None:
    """A guessed or made-up token must not work."""
    client.cookies.set(COOKIE, "definitely-not-a-real-token")

    response = await client.get("/api/v1/auth/me")

    assert response.status_code == 401


# ─── Logout ──────────────────────────────────────────────────────────────────


async def test_logout_ends_the_session(client: AsyncClient) -> None:
    await client.post("/api/v1/auth/register", json=REGISTRATION)
    assert (await client.get("/api/v1/auth/me")).status_code == 200

    logout = await client.post("/api/v1/auth/logout")

    assert logout.status_code == 204
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_logged_out_token_stays_dead_even_if_replayed(client: AsyncClient) -> None:
    """The cookie is cleared, but the token must be revoked server-side too.

    Clearing the cookie alone would be theatre: anyone who captured the token
    could keep using it. This is the difference a sessions table buys.
    """
    await client.post("/api/v1/auth/register", json=REGISTRATION)
    stolen = client.cookies[COOKIE]

    await client.post("/api/v1/auth/logout")

    client.cookies.set(COOKIE, stolen)
    assert (await client.get("/api/v1/auth/me")).status_code == 401


async def test_logout_without_a_session_is_still_204(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 204

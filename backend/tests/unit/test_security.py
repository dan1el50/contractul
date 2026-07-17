"""Password hashing and session tokens.

Pure crypto primitives, no database.
"""

from app.core.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    verify_password,
)


def test_password_verifies_against_its_own_hash() -> None:
    password = "parola-mea-sigura-2026"

    assert verify_password(password, hash_password(password)) is True


def test_wrong_password_is_rejected() -> None:
    assert verify_password("gresit", hash_password("corect")) is False


def test_hash_does_not_contain_the_password() -> None:
    """The obvious catastrophe, asserted anyway."""
    password = "parola-mea-sigura-2026"

    assert password not in hash_password(password)


def test_same_password_hashes_differently_each_time() -> None:
    """Argon2 salts per hash.

    Without a salt, identical passwords produce identical hashes — and one
    glance at the users table tells you which accounts share a password.
    """
    first = hash_password("aceeasi-parola")
    second = hash_password("aceeasi-parola")

    assert first != second
    assert verify_password("aceeasi-parola", first)
    assert verify_password("aceeasi-parola", second)


def test_hash_is_argon2id() -> None:
    assert hash_password("x").startswith("$argon2id$")


def test_verify_returns_false_on_a_corrupt_hash() -> None:
    """Never raises. A caller must not have to distinguish the failures."""
    assert verify_password("x", "not-a-hash") is False
    assert verify_password("x", "") is False


def test_session_tokens_are_unique() -> None:
    tokens = {generate_session_token() for _ in range(1000)}

    assert len(tokens) == 1000


def test_session_token_has_enough_entropy() -> None:
    """32 random bytes, url-safe base64 — comfortably over 40 characters."""
    assert len(generate_session_token()) >= 40


def test_token_hashing_is_deterministic_but_not_reversible() -> None:
    token = generate_session_token()
    digest = hash_session_token(token)

    assert hash_session_token(token) == digest  # lookups depend on this
    assert token not in digest
    assert len(digest) == 64  # hex sha256


def test_different_tokens_hash_differently() -> None:
    assert hash_session_token(generate_session_token()) != hash_session_token(
        generate_session_token()
    )

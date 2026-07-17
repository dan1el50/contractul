"""What crosses the auth API boundary."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, EmailStr, Field

# Long enough to matter, short enough not to push people towards a sticky note.
# No composition rules (one upper, one digit, one symbol): they measurably push
# users towards Passw0rd! and are no longer recommended by NIST or OWASP.
MIN_PASSWORD_LENGTH = 10

# Argon2 hashes the whole input, so a very long password is a cheap way to make
# the server do unbounded work.
MAX_PASSWORD_LENGTH = 128


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)
    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=32)


class LoginRequest(BaseModel):
    email: EmailStr
    # No length bounds. A rejected short password at login would tell an
    # attacker the rule without telling a legitimate user anything they need.
    password: str = Field(max_length=MAX_PASSWORD_LENGTH)


class UserResponse(BaseModel):
    """The user, as the client is allowed to see them.

    Separate from the User model on purpose. password_hash exists on the model
    and must never leave the server; a response built from an explicit field
    list cannot leak it by accident, whereas one built by serialising the ORM
    object leaks whatever gets added to the table next year.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    phone: str | None
    is_admin: bool

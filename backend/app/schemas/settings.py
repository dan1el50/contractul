"""What crosses the settings API boundary: profile, company, and password."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.auth import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH


class ProfileUpdate(BaseModel):
    full_name: str = Field(min_length=2, max_length=200)
    phone: str | None = Field(default=None, max_length=32)


class PasswordChange(BaseModel):
    current_password: str = Field(max_length=MAX_PASSWORD_LENGTH)
    # The new password is held to the same bar as registration.
    new_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=MAX_PASSWORD_LENGTH)


class CompanyUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    # Exactly 13 digits — the Moldovan IDNO. pattern rejects letters and wrong
    # lengths before the value reaches the database.
    idno: str = Field(pattern=r"^\d{13}$")
    legal_address: str | None = Field(default=None, max_length=500)
    iban: str | None = Field(default=None, max_length=34)
    bank_name: str | None = Field(default=None, max_length=120)


class CompanyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    idno: str
    legal_address: str | None
    iban: str | None
    bank_name: str | None

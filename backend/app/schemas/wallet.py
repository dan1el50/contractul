"""What crosses the wallet API boundary."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.core.money import format_mdl

# 50 MDL. Below this the card fees would exceed the top-up.
MIN_TOPUP_BANI = 5000
# 100 000 MDL. Not a business rule so much as a guard: a top-up this large is
# a typo or a test, and either way it deserves a human.
MAX_TOPUP_BANI = 10_000_000


class BalanceResponse(BaseModel):
    balance_bani: int

    @computed_field
    @property
    def balance_mdl(self) -> str:
        return format_mdl(self.balance_bani)


class TransactionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    amount_bani: int
    kind: str
    description: str
    created_at: datetime

    @computed_field
    @property
    def amount_mdl(self) -> str:
        """Signed and formatted: "+ 3 300" / "− 900"."""
        prefix = "+ " if self.amount_bani > 0 else "− "
        return prefix + format_mdl(abs(self.amount_bani))


class CardResponse(BaseModel):
    """A saved card, as the client may see it.

    provider_token is deliberately absent. It is a bearer credential for
    charging that card — listing fields explicitly is what keeps it from
    leaking the day someone serialises the model instead.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    brand: str
    last4: str
    exp_month: int
    exp_year: int
    is_default: bool


class AddCardRequest(BaseModel):
    """**Card details reaching our server is a development-only shortcut.**

    A real acquirer tokenises in the browser and our backend never sees a PAN.
    See MockPaymentProvider.tokenise_card.
    """

    number: str = Field(min_length=13, max_length=25)
    exp_month: int = Field(ge=1, le=12)
    exp_year: int = Field(ge=2024, le=2100)
    cvv: str = Field(min_length=3, max_length=4)
    make_default: bool = False


class TopUpRequest(BaseModel):
    card_id: uuid.UUID
    amount_bani: int = Field(ge=MIN_TOPUP_BANI, le=MAX_TOPUP_BANI)

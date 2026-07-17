"""What crosses the order API boundary."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, computed_field

from app.core.money import format_mdl, vat_split
from app.models.order import Order


class OrderItemResponse(BaseModel):
    """A purchased line, as snapshotted at the time of sale."""

    model_config = ConfigDict(from_attributes=True)

    template_id: uuid.UUID
    name_snapshot: str
    unit_price_bani: int

    @computed_field
    @property
    def unit_price_mdl(self) -> str:
        return format_mdl(self.unit_price_bani)


class OrderResponse(BaseModel):
    id: uuid.UUID
    number: str
    status: str
    payment_method: str
    total_bani: int
    created_at: datetime
    paid_at: datetime | None
    items: list[OrderItemResponse]

    @computed_field
    @property
    def total_mdl(self) -> str:
        return format_mdl(self.total_bani)

    @computed_field
    @property
    def net_bani(self) -> int:
        return vat_split(self.total_bani)[0]

    @computed_field
    @property
    def vat_bani(self) -> int:
        return vat_split(self.total_bani)[1]

    @computed_field
    @property
    def net_mdl(self) -> str:
        return format_mdl(self.net_bani)

    @computed_field
    @property
    def vat_mdl(self) -> str:
        return format_mdl(self.vat_bani)

    @classmethod
    def from_order(cls, order: Order) -> OrderResponse:
        return cls(
            id=order.id,
            number=order.number,
            status=order.status,
            payment_method=order.payment_method,
            total_bani=order.total_bani,
            created_at=order.created_at,
            paid_at=order.paid_at,
            items=[OrderItemResponse.model_validate(item) for item in order.items],
        )


class CheckoutRequest(BaseModel):
    # Only the wallet is funded until the real acquirer lands; the field exists
    # so the client states intent and the enum is ready to grow.
    payment_method: str = "wallet"

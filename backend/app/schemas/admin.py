"""What crosses the admin API boundary."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, computed_field

from app.core.money import format_mdl


class StatsResponse(BaseModel):
    revenue_bani: int
    paid_orders: int
    users: int
    published_templates: int

    @computed_field
    @property
    def revenue_mdl(self) -> str:
        return format_mdl(self.revenue_bani)


class MonthRevenueResponse(BaseModel):
    label: str
    revenue_bani: int

    @computed_field
    @property
    def revenue_mdl(self) -> str:
        return format_mdl(self.revenue_bani)


class AdminOrderResponse(BaseModel):
    number: str
    client_name: str
    client_email: str
    first_item: str
    item_count: int
    total_bani: int
    status: str
    created_at: datetime

    @computed_field
    @property
    def total_mdl(self) -> str:
        return format_mdl(self.total_bani)


class AdminTemplateResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    category_name: str
    price_bani: int
    is_published: bool

    @computed_field
    @property
    def price_mdl(self) -> str:
        return format_mdl(self.price_bani)


class PublishUpdate(BaseModel):
    is_published: bool

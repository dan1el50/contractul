"""What crosses the cart API boundary."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, computed_field

from app.core.money import format_mdl, vat_split
from app.models.cart import CartItem


class CartItemResponse(BaseModel):
    """One line of the cart, at the live catalog price."""

    template_id: uuid.UUID
    slug: str
    name: str
    category_name: str
    languages: list[str]
    price_bani: int

    @computed_field
    @property
    def price_mdl(self) -> str:
        return format_mdl(self.price_bani)

    @classmethod
    def from_item(cls, item: CartItem) -> CartItemResponse:
        template = item.template
        return cls(
            template_id=template.id,
            slug=template.slug,
            name=template.name,
            category_name=template.category.name,
            languages=list(template.languages),
            price_bani=template.price_bani,
        )


class CartResponse(BaseModel):
    items: list[CartItemResponse]
    total_bani: int

    @computed_field
    @property
    def item_count(self) -> int:
        return len(self.items)

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
    def from_items(cls, items: list[CartItem]) -> CartResponse:
        lines = [CartItemResponse.from_item(item) for item in items]
        return cls(items=lines, total_bani=sum(line.price_bani for line in lines))


class AddToCartRequest(BaseModel):
    slug: str

"""What crosses the catalog API boundary."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, computed_field


class CategoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: str | None


class TemplateSummary(BaseModel):
    """A catalog card."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    slug: str
    name: str
    description: str
    price_bani: int
    languages: list[str]
    category: CategoryResponse

    @computed_field
    @property
    def price_mdl(self) -> str:
        """Formatted for display: 90000 -> "900".

        Money crosses the wire as bani and is formatted once, here. Letting the
        frontend divide by 100 would spread that rule across two languages and
        invite a float back into the arithmetic.
        """
        return f"{self.price_bani // 100:,}".replace(",", " ")


class TemplateDetail(TemplateSummary):
    page_count: int
    free_pages: int

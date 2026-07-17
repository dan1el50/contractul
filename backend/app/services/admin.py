"""Admin read models and template management.

Aggregate queries for the dashboard, plus the one write an admin makes here:
publishing or unpublishing a template. Knows nothing about HTTP.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import ContractTemplate
from app.models.order import Order
from app.models.user import User


class TemplateNotFound(Exception):
    """No template with that id."""


@dataclass(frozen=True)
class Stats:
    revenue_bani: int
    paid_orders: int
    users: int
    published_templates: int


@dataclass(frozen=True)
class MonthRevenue:
    label: str  # "2026-07"
    revenue_bani: int


async def stats(session: AsyncSession) -> Stats:
    revenue = await session.scalar(
        select(func.coalesce(func.sum(Order.total_bani), 0)).where(Order.status == "paid")
    )
    paid = await session.scalar(
        select(func.count()).select_from(Order).where(Order.status == "paid")
    )
    users = await session.scalar(select(func.count()).select_from(User))
    published = await session.scalar(
        select(func.count()).select_from(ContractTemplate).where(ContractTemplate.is_published)
    )
    return Stats(
        revenue_bani=int(revenue or 0),
        paid_orders=int(paid or 0),
        users=int(users or 0),
        published_templates=int(published or 0),
    )


async def revenue_by_month(session: AsyncSession, *, months: int = 6) -> list[MonthRevenue]:
    """Paid revenue per calendar month, with empty months filled to zero.

    The gaps are filled here rather than left out, so the chart always has a
    continuous axis instead of skipping a quiet month.
    """
    rows = await session.execute(
        select(
            func.date_trunc("month", Order.created_at).label("m"),
            func.sum(Order.total_bani),
        )
        .where(Order.status == "paid")
        .group_by("m")
    )
    by_bucket = {(row.m.year, row.m.month): int(row[1] or 0) for row in rows}

    now = datetime.now(UTC)
    buckets: list[tuple[int, int]] = []
    year, month = now.year, now.month
    for _ in range(months):
        buckets.append((year, month))
        month -= 1
        if month == 0:
            month = 12
            year -= 1
    buckets.reverse()

    return [
        MonthRevenue(label=f"{y}-{m:02d}", revenue_bani=by_bucket.get((y, m), 0))
        for y, m in buckets
    ]


@dataclass(frozen=True)
class OrderRow:
    number: str
    client_name: str
    client_email: str
    first_item: str
    item_count: int
    total_bani: int
    status: str
    created_at: datetime


async def recent_orders(session: AsyncSession, *, limit: int = 15) -> list[OrderRow]:
    result = await session.execute(
        select(Order, User.full_name, User.email)
        .join(User, Order.user_id == User.id)
        .options(selectinload(Order.items))
        .order_by(Order.created_at.desc(), Order.id.desc())
        .limit(limit)
    )

    rows: list[OrderRow] = []
    for order, full_name, email in result:
        first = order.items[0].name_snapshot if order.items else "—"
        rows.append(
            OrderRow(
                number=order.number,
                client_name=full_name,
                client_email=email,
                first_item=first,
                item_count=len(order.items),
                total_bani=order.total_bani,
                status=order.status,
                created_at=order.created_at,
            )
        )
    return rows


async def list_all_templates(session: AsyncSession) -> list[ContractTemplate]:
    """Every template, drafts included — the catalog read hides unpublished
    ones, but the admin manages them."""
    result = await session.scalars(
        select(ContractTemplate)
        .options(selectinload(ContractTemplate.category))
        .order_by(ContractTemplate.name)
    )
    return list(result.all())


async def set_published(
    session: AsyncSession, *, template_id: uuid.UUID, is_published: bool
) -> ContractTemplate:
    template = await session.scalar(
        select(ContractTemplate)
        .where(ContractTemplate.id == template_id)
        .options(selectinload(ContractTemplate.category))
    )
    if template is None:
        raise TemplateNotFound(str(template_id))

    template.is_published = is_published
    await session.flush()
    return template

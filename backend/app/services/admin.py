"""Admin read models and template management.

Aggregate queries for the dashboard, plus the writes an admin makes: publishing
a template, adding a new one from an uploaded .docx, and removing one. Knows
nothing about HTTP.
"""

from __future__ import annotations

import re
import tempfile
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pypdf import PdfReader
from sqlalchemy import delete as sql_delete
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.documents.renderer import docx_to_pdf, fill_template
from app.integrations.storage.base import Storage
from app.models.cart import CartItem
from app.models.catalog import Category, ContractTemplate, TemplateVersion
from app.models.order import Order, OrderItem
from app.models.user import User


class TemplateNotFound(Exception):
    """No template with that id."""


class CategoryNotFound(Exception):
    """No category with that id."""


class TemplateHasSales(Exception):
    """The template has been sold, so it cannot be deleted — only hidden.

    Order lines reference the template, and an order that points at a deleted
    template is a broken receipt. History outlives the catalog entry.
    """


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


def count_pages(docx_bytes: bytes) -> int:
    """Render an uploaded .docx and count its pages.

    Blocking — it shells out to LibreOffice — so a caller must run it off the
    event loop. Doubles as validation: a file that is not a real, convertible
    .docx raises RenderError here rather than becoming a broken catalog entry.
    Filled with an empty context, exactly as a placeholder-free document would
    be at sale time.
    """
    with tempfile.TemporaryDirectory() as tmp:
        workdir = Path(tmp)
        source = workdir / "uploaded.docx"
        source.write_bytes(docx_bytes)
        filled = fill_template(source, {}, workdir / "filled.docx")
        pdf = docx_to_pdf(filled, workdir)
        return len(PdfReader(str(pdf)).pages)


def _slugify(name: str) -> str:
    """A URL-safe slug from a name. Romanian diacritics fold to ASCII."""
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", folded).strip("-").lower()
    return slug or "sablon"


async def _unique_slug(session: AsyncSession, base: str) -> str:
    """`base`, or `base-2`, `base-3`… — the first that no template holds."""
    slug = base
    suffix = 2
    while await session.scalar(select(ContractTemplate.id).where(ContractTemplate.slug == slug)):
        slug = f"{base}-{suffix}"
        suffix += 1
    return slug


async def create_template(
    session: AsyncSession,
    storage: Storage,
    *,
    name: str,
    category_id: uuid.UUID,
    description: str,
    price_bani: int,
    languages: list[str],
    is_published: bool,
    docx_bytes: bytes,
    page_count: int,
    uploaded_by: uuid.UUID,
) -> ContractTemplate:
    """Add a template to the catalog from an uploaded .docx.

    The file is stored and version 1 is created as the current version. The
    page count is computed by the caller (off the event loop) and passed in.
    """
    category = await session.get(Category, category_id)
    if category is None:
        raise CategoryNotFound(str(category_id))

    slug = await _unique_slug(session, _slugify(name))
    object_key = f"templates/{slug}/v1.docx"
    storage.put(object_key, docx_bytes)

    template = ContractTemplate(
        slug=slug,
        name=name.strip(),
        description=description.strip(),
        category_id=category_id,
        price_bani=price_bani,
        languages=languages,
        is_published=is_published,
        versions=[
            TemplateVersion(
                version=1,
                docx_object_key=object_key,
                page_count=page_count,
                is_current=True,
                uploaded_by=uploaded_by,
            )
        ],
    )
    session.add(template)
    await session.flush()

    # Re-read with the category eager-loaded, so building the response does not
    # lazy-load outside the async context.
    loaded = await session.scalar(
        select(ContractTemplate)
        .where(ContractTemplate.id == template.id)
        .options(selectinload(ContractTemplate.category))
    )
    assert loaded is not None
    return loaded


async def delete_template(session: AsyncSession, *, template_id: uuid.UUID) -> None:
    """Remove a template that has never been sold.

    Refuses if any order references it — deleting it would orphan a receipt.
    Such a template is hidden (unpublished) instead. A template with no sales is
    removed outright, along with its versions and any stray cart lines. Stored
    files are left as-is: a version's object key may be shared (the seed points
    every template at one placeholder), and deleting a shared file would break
    the others.
    """
    template = await session.get(ContractTemplate, template_id)
    if template is None:
        raise TemplateNotFound(str(template_id))

    sold = await session.scalar(
        select(func.count()).select_from(OrderItem).where(OrderItem.template_id == template_id)
    )
    if sold:
        raise TemplateHasSales(str(template_id))

    await session.execute(sql_delete(CartItem).where(CartItem.template_id == template_id))
    await session.execute(
        sql_delete(TemplateVersion).where(TemplateVersion.template_id == template_id)
    )
    await session.delete(template)
    await session.flush()

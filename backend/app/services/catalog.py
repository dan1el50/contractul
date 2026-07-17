"""Catalog reads: categories and published templates."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.catalog import Category, ContractTemplate, TemplateVersion


class TemplateNotFound(Exception):
    """No published template with that slug."""


async def list_categories(session: AsyncSession) -> list[Category]:
    result = await session.scalars(select(Category).order_by(Category.sort_order, Category.name))
    return list(result.all())


async def list_templates(
    session: AsyncSession, *, category_slug: str | None = None
) -> list[ContractTemplate]:
    """Published templates, newest first, optionally filtered by category.

    Unpublished rows are filtered here rather than by the caller. A draft is
    invisible because the query cannot return it, not because every endpoint
    remembers to ask.
    """
    query = (
        select(ContractTemplate)
        .where(ContractTemplate.is_published)
        # selectinload, not lazy loading: the list screen shows each template's
        # category, and lazy loading would fire one query per row. It is also
        # an error under async SQLAlchemy rather than merely slow.
        .options(selectinload(ContractTemplate.category))
        .order_by(ContractTemplate.name)
    )

    if category_slug:
        query = query.join(Category).where(Category.slug == category_slug)

    return list((await session.scalars(query)).all())


async def get_template(session: AsyncSession, *, slug: str) -> ContractTemplate:
    """One published template. Raises TemplateNotFound otherwise.

    An unpublished template is indistinguishable from a nonexistent one, which
    is the point: a draft's URL must not confirm it exists.
    """
    template = await session.scalar(
        select(ContractTemplate)
        .where(ContractTemplate.slug == slug, ContractTemplate.is_published)
        .options(
            selectinload(ContractTemplate.category),
            selectinload(ContractTemplate.versions),
        )
    )

    if template is None:
        raise TemplateNotFound(slug)

    return template


async def current_version(session: AsyncSession, *, template: ContractTemplate) -> TemplateVersion:
    """The version a buyer would get today.

    Raises TemplateNotFound when a published template has no current version —
    which is a data bug, not a user error, but from the outside it is simply
    not purchasable.
    """
    version = await session.scalar(
        select(TemplateVersion).where(
            TemplateVersion.template_id == template.id,
            TemplateVersion.is_current,
        )
    )

    if version is None:
        raise TemplateNotFound(template.slug)

    return version

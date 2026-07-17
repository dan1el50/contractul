"""Small builders for integration tests.

Seeding a template means three rows — a category, the template, and a current
version — and several tests need one. Kept here so each test asks for a template
by the two things it cares about (slug and price) and not the scaffolding.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.catalog import Category, ContractTemplate, TemplateVersion
from app.models.user import User


async def create_user(session: AsyncSession, *, email: str = "ion@nordconstruct.md") -> User:
    user = User(email=email, password_hash="x", full_name="Ion Popescu")
    session.add(user)
    await session.flush()
    return user


async def create_template(
    session: AsyncSession,
    *,
    slug: str,
    price_bani: int,
    name: str | None = None,
    category_slug: str = "servicii",
    category_name: str = "Servicii & Colaborare",
    page_count: int = 3,
) -> ContractTemplate:
    """A published template with a current version, ready to be bought."""
    category = await session.scalar(select(Category).where(Category.slug == category_slug))
    if category is None:
        category = Category(slug=category_slug, name=category_name)
        session.add(category)
        await session.flush()

    # The version is built through the relationship, not added separately, so
    # template.versions is populated in memory — a test reading template.versions
    # then does not trigger a lazy load outside the async context.
    template = ContractTemplate(
        slug=slug,
        name=name or f"Contract {slug}",
        description="Un contract de test.",
        category_id=category.id,
        price_bani=price_bani,
        languages=["ro", "ru"],
        is_published=True,
        versions=[
            TemplateVersion(
                version=1,
                docx_object_key=f"templates/{slug}/v1.docx",
                page_count=page_count,
                is_current=True,
            )
        ],
    )
    session.add(template)
    await session.flush()

    return template

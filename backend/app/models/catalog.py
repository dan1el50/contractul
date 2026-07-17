"""Catalog models: categories, templates, and template versions.

See docs/data-model.md for the schema and the reasoning behind it.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    templates: Mapped[list[ContractTemplate]] = relationship(back_populates="category")

    def __repr__(self) -> str:
        return f"<Category {self.slug}>"


class ContractTemplate(Base):
    __tablename__ = "contract_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    slug: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Bani, not lei. 900 MDL = 90000. Flat: one document, one price, whatever
    # languages it happens to contain.
    #
    # BigInteger is overkill for a template price — INTEGER would reach 21
    # million MDL — but "every money column is BIGINT" is a rule precisely so
    # that nobody has to judge it per column. An exception here is how you end
    # up with a money column that quietly overflows somewhere it matters.
    price_bani: Mapped[int] = mapped_column(BigInteger, nullable=False)

    # Which languages this document is written in — {ro,ru}. Descriptive only.
    # It drives the "Limbi incluse" label and must never multiply the price.
    languages: Mapped[list[str]] = mapped_column(ARRAY(String(2)), nullable=False)

    is_published: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    category: Mapped[Category] = relationship(back_populates="templates")
    versions: Mapped[list[TemplateVersion]] = relationship(
        back_populates="template", order_by="TemplateVersion.version"
    )

    __table_args__ = (
        CheckConstraint("price_bani > 0", name="price_positive"),
        CheckConstraint("cardinality(languages) > 0", name="languages_not_empty"),
        # The catalog only ever reads published rows, so the index only covers
        # them. Drafts are a rounding error and are never listed this way.
        Index(
            "ix_contract_templates_category_id_published",
            "category_id",
            postgresql_where=text("is_published"),
        ),
    )

    def __repr__(self) -> str:
        return f"<ContractTemplate {self.slug}>"


class TemplateVersion(Base):
    """A specific .docx. Never updated, never deleted.

    This is what makes a sold document reproducible: an order records the
    version it was generated from, so revising a template cannot rewrite
    history. A lawyer changing wording creates version N+1; version N stays
    exactly as it was, for as long as anyone might ask for their document back.
    """

    __tablename__ = "template_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contract_templates.id"), nullable=False
    )
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # A storage key, not a filesystem path. Storage sits behind an interface;
    # today this resolves to a file in a volume, tomorrow to an S3 object.
    docx_object_key: Mapped[str] = mapped_column(String(500), nullable=False)

    page_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    template: Mapped[ContractTemplate] = relationship(back_populates="versions")

    __table_args__ = (
        UniqueConstraint("template_id", "version", name="uq_template_versions_template_id_version"),
        CheckConstraint("version > 0", name="version_positive"),
        # At most one current version per template. A partial unique index is
        # the only way to say that in PostgreSQL — a plain unique on
        # (template_id, is_current) would also forbid two *false* rows, which
        # is the normal case for every superseded version.
        Index(
            "uq_template_versions_one_current",
            "template_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    def __repr__(self) -> str:
        return f"<TemplateVersion {self.template_id} v{self.version}>"

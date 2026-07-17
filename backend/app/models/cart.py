"""Cart models: the server-side cart and its items.

See docs/data-model.md. The cart lives on the server because a price the client
can edit is not a price.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.catalog import ContractTemplate


class Cart(Base):
    """One open cart per user.

    Created lazily the first time something is added, and emptied — not
    deleted — when its contents are checked out.
    """

    __tablename__ = "carts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    items: Mapped[list[CartItem]] = relationship(
        back_populates="cart", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Cart user={self.user_id}>"


class CartItem(Base):
    """One template queued for purchase.

    No quantity and UNIQUE (cart_id, template_id): buying the same document
    twice is meaningless — you would download the identical file — so the
    constraint makes it impossible rather than merely discouraged.

    No price snapshot: the cart shows the live price, and the *order* snapshots
    it. A cart that quietly holds last week's price is a bug, not a feature.
    """

    __tablename__ = "cart_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    cart_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("carts.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contract_templates.id"), nullable=False
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    cart: Mapped[Cart] = relationship(back_populates="items")
    template: Mapped[ContractTemplate] = relationship("ContractTemplate")

    __table_args__ = (
        UniqueConstraint("cart_id", "template_id", name="uq_cart_items_cart_id_template_id"),
        Index("ix_cart_items_cart_id", "cart_id"),
    )

    def __repr__(self) -> str:
        return f"<CartItem cart={self.cart_id} template={self.template_id}>"

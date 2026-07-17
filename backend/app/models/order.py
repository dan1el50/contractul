"""Order models: a completed purchase and its snapshotted lines.

See docs/data-model.md. Orders are the permanent record of a sale; their lines
copy the name and price at purchase time so a receipt reads the same years
later, whatever has since happened to the template.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

ORDER_STATUSES = ("pending", "paid", "failed", "cancelled")
PAYMENT_METHODS = ("wallet", "card")

# The order number is drawn from this sequence. Plain and monotonic; gaps are
# expected and fine — a rolled-back checkout has already consumed its number,
# and gap-free numbering would mean serialising every checkout behind one
# counter. Safe precisely because the number is a customer reference, not a
# fiscal document. See docs/data-model.md.
#
# Created by the migration, and by the test harness after create_all (the
# metadata builds tables, not sequences). Kept out of Base.metadata on purpose
# so autogenerate stays a clean table-only diff.
ORDER_NUMBER_SEQUENCE = "order_number_seq"


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Human-facing: CT-2026-0184. Separate from the UUID id, which is for
    # machines — making the primary key human-facing would leak order volume.
    number: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    status: Mapped[str] = mapped_column(String(20), nullable=False)

    # Snapshotted sum of the item prices. Stored, not re-summed, because the
    # items themselves are snapshots and the total must not drift from them.
    total_bani: Mapped[int] = mapped_column(BigInteger, nullable=False)

    payment_method: Mapped[str] = mapped_column(String(20), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list[OrderItem]] = relationship(
        back_populates="order", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN " + str(ORDER_STATUSES), name="status_valid"
        ),
        CheckConstraint(
            "payment_method IN " + str(PAYMENT_METHODS), name="payment_method_valid"
        ),
        CheckConstraint("total_bani >= 0", name="total_non_negative"),
        Index("ix_orders_user_id_created_at", "user_id", text("created_at DESC")),
    )

    def __repr__(self) -> str:
        return f"<Order {self.number} {self.status}>"


class OrderItem(Base):
    """One purchased line, snapshotted.

    name_snapshot and unit_price_bani are deliberate duplication: a receipt
    must read the same in 2030 as it did on the day, after the template has
    been renamed and repriced any number of times.

    template_version_id records the exact file bought, which is what lets
    phase 7 regenerate the identical document later.
    """

    __tablename__ = "order_items"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("orders.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("contract_templates.id"), nullable=False
    )
    template_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("template_versions.id"), nullable=False
    )
    name_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    unit_price_bani: Mapped[int] = mapped_column(BigInteger, nullable=False)

    order: Mapped[Order] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("unit_price_bani >= 0", name="unit_price_non_negative"),
        Index("ix_order_items_order_id", "order_id"),
    )

    def __repr__(self) -> str:
        return f"<OrderItem {self.name_snapshot} {self.unit_price_bani}>"

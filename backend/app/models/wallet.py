"""Wallet models: the transaction ledger and saved cards.

See docs/data-model.md.
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
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

TRANSACTION_KINDS = ("topup", "purchase", "refund", "adjustment")


class WalletTransaction(Base):
    """One movement of money. Append-only.

    **There is no balance column anywhere in this schema.** The balance is
    SUM(amount_bani) for a user. A balance column plus a transaction list is two
    records of one fact, and two records of one fact drift — and when they
    disagree, you cannot tell which is right. Deriving means the history *is*
    the balance: always explainable, always reconcilable.

    Rows are never updated and never deleted. A mistake is corrected by writing
    a compensating transaction, so both the error and the correction stay
    visible.
    """

    __tablename__ = "wallet_transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )

    # Signed: positive credits, negative debits. Summing is the whole point,
    # so a "type" column plus an unsigned amount would just make every query
    # carry a CASE.
    amount_bani: Mapped[int] = mapped_column(BigInteger, nullable=False)

    kind: Mapped[str] = mapped_column(String(20), nullable=False)

    order_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    provider_charge_id: Mapped[str | None] = mapped_column(String(120), nullable=True)

    description: Mapped[str] = mapped_column(Text, nullable=False)

    # clock_timestamp(), NOT now().
    #
    # PostgreSQL's now() returns the *transaction start* time, so every row
    # written in one transaction shares an identical timestamp. For a ledger
    # that is actively wrong: the history is ordered by time, and identical
    # timestamps leave the order to a tiebreak on a random UUID — so the same
    # data renders in a different order on different requests.
    #
    # clock_timestamp() reads the real clock at insert, so created_at means
    # "when this entry happened" rather than "when its transaction opened",
    # and entries written together still order deterministically.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.clock_timestamp()
    )

    __table_args__ = (
        # A zero-value transaction records nothing and would only ever be a bug.
        CheckConstraint("amount_bani <> 0", name="amount_not_zero"),
        CheckConstraint(
            "kind IN " + str(TRANSACTION_KINDS).replace("'", "'"),
            name="kind_valid",
        ),
        # Every balance sums this, and the history screen pages it. The hottest
        # read in the system once anyone has a wallet.
        Index("ix_wallet_transactions_user_id_created_at", "user_id", text("created_at DESC")),
    )

    def __repr__(self) -> str:
        return f"<WalletTransaction {self.kind} {self.amount_bani}>"


class PaymentCard(Base):
    """A saved card — as a token, never as a number.

    We store the acquirer's opaque token, the brand, and the last four digits.
    Nothing else. No PAN, no CVV, ever. Storing a card number would drag this
    system into PCI-DSS scope, which is not a thing to acquire by accident.
    """

    __tablename__ = "payment_cards"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )

    provider_token: Mapped[str] = mapped_column(String(255), nullable=False)
    brand: Mapped[str] = mapped_column(String(20), nullable=False)
    last4: Mapped[str] = mapped_column(String(4), nullable=False)
    exp_month: Mapped[int] = mapped_column(Integer, nullable=False)
    exp_year: Mapped[int] = mapped_column(Integer, nullable=False)

    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint("exp_month BETWEEN 1 AND 12", name="exp_month_valid"),
        CheckConstraint("length(last4) = 4", name="last4_length"),
        # At most one default card per user. Partial unique index, because a
        # plain unique on (user_id, is_default) would also forbid a user having
        # two *non*-default cards — the normal case.
        Index(
            "uq_payment_cards_one_default",
            "user_id",
            unique=True,
            postgresql_where=text("is_default"),
        ),
        Index("ix_payment_cards_user_id", "user_id"),
    )

    def __repr__(self) -> str:
        return f"<PaymentCard {self.brand} ****{self.last4}>"

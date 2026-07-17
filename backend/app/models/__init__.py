"""Model registry.

Importing this package registers every model against Base.metadata. Alembic
reads that metadata to work out what the schema should be, so **a model missing
from this list is invisible to autogenerate** — which will then cheerfully
generate a migration dropping its table.

Add every new model here.

This lives here rather than in app.db.base because models import Base from that
module. Importing them back would be a cycle, and a cycle that resolves in one
import order and raises in the other passes tests while breaking the server.
"""

from app.models.catalog import Category, ContractTemplate, TemplateVersion
from app.models.session import Session
from app.models.wallet import PaymentCard, WalletTransaction
from app.models.user import User

__all__ = [
    "Category",
    "ContractTemplate",
    "PaymentCard",
    "Session",
    "TemplateVersion",
    "User",
    "WalletTransaction",
]

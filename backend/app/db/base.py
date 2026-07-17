"""Declarative base and model registry.

Every model inherits from Base. Alembic's autogenerate reads Base.metadata to
work out what the schema should look like, which means a model that is never
imported is invisible to it — importing them here is what makes them visible.
"""

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

# Deterministic constraint names.
#
# Without this, PostgreSQL invents names, and they differ between a database
# built by migrations and one built by create_all. A later migration that needs
# to drop or alter a constraint then has nothing reliable to name — you end up
# hand-copying whatever the server happened to choose. Setting the convention
# now, while there is one table, costs nothing; setting it later means renaming
# every existing constraint.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# Models are imported here so they register with Base.metadata before Alembic
# inspects it. A model missing from this list is invisible to autogenerate,
# which will cheerfully write a migration dropping its table.
from app.models.user import User  # noqa: E402, F401

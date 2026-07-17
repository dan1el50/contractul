"""Declarative base.

Base and nothing else. **This module must not import models.**

Models import Base from here, so importing them back creates a cycle. Python
tolerates that cycle in one import order and raises ImportError in the other,
which means it can pass every test and still refuse to start the server —
exactly what happened when this file did import them.

Alembic still needs every model registered against Base.metadata before it
inspects it. That job belongs to app.models.__init__, which alembic/env.py
imports for the purpose.
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

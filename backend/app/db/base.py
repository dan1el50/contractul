"""Declarative base and model registry.

Every model inherits from Base. Alembic's autogenerate reads Base.metadata to
work out what the schema should look like, which means a model that is never
imported is invisible to it — importing them here is what makes them visible.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Models are imported here so they register with Base.metadata before Alembic
# inspects it. There are none yet; they arrive with the data model in phase 2.
#
# from app.models.user import User  # noqa: F401

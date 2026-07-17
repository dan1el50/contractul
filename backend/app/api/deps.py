"""Shared route dependencies.

Anything more than one route needs — the database session now; the current
user and the admin guard once authentication lands in phase 3.
"""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session

SessionDep = Annotated[AsyncSession, Depends(get_session)]

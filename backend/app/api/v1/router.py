"""Assembles the v1 API.

Every route module is included here. Feature routers arrive per phase —
auth, templates, cart, orders, wallet, documents, admin.
"""

from fastapi import APIRouter

from app.api.v1.routes import auth, health, templates, wallet

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(templates.router)
api_router.include_router(wallet.router)

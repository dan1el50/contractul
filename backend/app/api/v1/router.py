"""Assembles the v1 API.

Every route module is included here. Feature routers arrive per phase —
auth, templates, cart, orders, wallet, documents, admin.
"""

from fastapi import APIRouter

from app.api.v1.routes import auth, cart, health, orders, settings, templates, wallet

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router)
api_router.include_router(templates.router)
api_router.include_router(wallet.router)
api_router.include_router(cart.router)
api_router.include_router(orders.router)
api_router.include_router(settings.router)

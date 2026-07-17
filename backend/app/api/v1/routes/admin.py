"""Admin endpoints. Behind the admin guard — Crowe staff only.

AdminUser returns 403 for a signed-in non-admin and 401 for a stranger, so none
of these handlers repeat the check.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status

from app.api.deps import AdminUser, SessionDep
from app.schemas.admin import (
    AdminOrderResponse,
    AdminTemplateResponse,
    MonthRevenueResponse,
    PublishUpdate,
    StatsResponse,
)
from app.services import admin as admin_service

router = APIRouter(prefix="/admin", tags=["admin"])


@router.get("/stats", response_model=StatsResponse)
async def get_stats(session: SessionDep, _: AdminUser) -> StatsResponse:
    stats = await admin_service.stats(session)
    return StatsResponse.model_validate(stats, from_attributes=True)


@router.get("/revenue", response_model=list[MonthRevenueResponse])
async def get_revenue(session: SessionDep, _: AdminUser) -> list[MonthRevenueResponse]:
    series = await admin_service.revenue_by_month(session)
    return [MonthRevenueResponse.model_validate(m, from_attributes=True) for m in series]


@router.get("/orders", response_model=list[AdminOrderResponse])
async def get_orders(session: SessionDep, _: AdminUser) -> list[AdminOrderResponse]:
    orders = await admin_service.recent_orders(session)
    return [AdminOrderResponse.model_validate(o, from_attributes=True) for o in orders]


@router.get("/templates", response_model=list[AdminTemplateResponse])
async def get_templates(session: SessionDep, _: AdminUser) -> list[AdminTemplateResponse]:
    templates = await admin_service.list_all_templates(session)
    return [
        AdminTemplateResponse(
            id=t.id,
            slug=t.slug,
            name=t.name,
            category_name=t.category.name,
            price_bani=t.price_bani,
            is_published=t.is_published,
        )
        for t in templates
    ]


@router.patch("/templates/{template_id}", response_model=AdminTemplateResponse)
async def set_template_published(
    template_id: uuid.UUID, payload: PublishUpdate, session: SessionDep, _: AdminUser
) -> AdminTemplateResponse:
    try:
        template = await admin_service.set_published(
            session, template_id=template_id, is_published=payload.is_published
        )
    except admin_service.TemplateNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Șablonul nu a fost găsit."
        ) from None

    await session.commit()
    return AdminTemplateResponse(
        id=template.id,
        slug=template.slug,
        name=template.name,
        category_name=template.category.name,
        price_bani=template.price_bani,
        is_published=template.is_published,
    )

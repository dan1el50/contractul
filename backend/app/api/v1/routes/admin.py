"""Admin endpoints. Behind the admin guard — staff only.

AdminUser returns 403 for a signed-in non-admin and 401 for a stranger, so none
of these handlers repeat the check.
"""

from __future__ import annotations

import uuid

import anyio
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from app.api.deps import AdminUser, SessionDep, StorageDep
from app.documents.renderer import RenderError
from app.models.catalog import ContractTemplate
from app.schemas.admin import (
    AdminOrderResponse,
    AdminTemplateResponse,
    MonthRevenueResponse,
    PublishUpdate,
    StatsResponse,
)
from app.services import admin as admin_service

router = APIRouter(prefix="/admin", tags=["admin"])

# A generous ceiling on an uploaded template. A .docx this large is a mistake,
# and reading an unbounded upload into memory is a denial-of-service waiting to
# happen.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _template_response(template: ContractTemplate) -> AdminTemplateResponse:
    return AdminTemplateResponse(
        id=template.id,
        slug=template.slug,
        name=template.name,
        category_name=template.category.name,
        price_bani=template.price_bani,
        is_published=template.is_published,
    )


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
    return [_template_response(t) for t in templates]


@router.post(
    "/templates", response_model=AdminTemplateResponse, status_code=status.HTTP_201_CREATED
)
async def create_template(
    session: SessionDep,
    storage: StorageDep,
    admin: AdminUser,
    file: UploadFile = File(...),
    name: str = Form(..., min_length=2, max_length=200),
    category_id: uuid.UUID = Form(...),
    description: str = Form(..., min_length=1),
    price_bani: int = Form(..., ge=1),
    # Comma-separated on the wire: "ro,ru". A multipart form has no clean way to
    # send a JSON list, and this keeps the field a plain string.
    languages: str = Form("ro"),
    is_published: bool = Form(False),
) -> AdminTemplateResponse:
    docx_bytes = await file.read()
    if not docx_bytes:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Fișier gol.")
    if len(docx_bytes) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Fișierul este prea mare.",
        )

    langs = [lang.strip() for lang in languages.split(",") if lang.strip()]
    if not langs:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Selectează cel puțin o limbă."
        )

    try:
        # LibreOffice is a blocking subprocess; keep it off the event loop. This
        # also validates the upload — a non-.docx raises RenderError.
        page_count = await anyio.to_thread.run_sync(admin_service.count_pages, docx_bytes)
    except RenderError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Documentul nu a putut fi procesat. Încarcă un fișier .docx valid.",
        ) from None

    try:
        template = await admin_service.create_template(
            session,
            storage,
            name=name,
            category_id=category_id,
            description=description,
            price_bani=price_bani,
            languages=langs,
            is_published=is_published,
            docx_bytes=docx_bytes,
            page_count=page_count,
            uploaded_by=admin.id,
        )
    except admin_service.CategoryNotFound:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Categorie invalidă."
        ) from None

    await session.commit()
    return _template_response(template)


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
    return _template_response(template)


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: uuid.UUID, session: SessionDep, _: AdminUser
) -> None:
    try:
        await admin_service.delete_template(session, template_id=template_id)
    except admin_service.TemplateNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Șablonul nu a fost găsit."
        ) from None
    except admin_service.TemplateHasSales:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Șablonul are vânzări și nu poate fi șters. Ascunde-l în schimb.",
        ) from None

    await session.commit()

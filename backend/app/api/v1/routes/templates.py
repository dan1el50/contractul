"""Catalog endpoints.

Public: browsing the shop needs no account. Buying does.
"""

from __future__ import annotations

import anyio
from fastapi import APIRouter, HTTPException, Path, Query, Response, status

from app.api.deps import SessionDep, StorageDep
from app.documents.renderer import RenderError
from app.schemas.catalog import CategoryResponse, TemplateDetail, TemplateSummary
from app.services import catalog as catalog_service
from app.services import previews as preview_service

router = APIRouter(tags=["catalog"])


@router.get("/categories", response_model=list[CategoryResponse])
async def list_categories(session: SessionDep) -> list[CategoryResponse]:
    categories = await catalog_service.list_categories(session)
    return [CategoryResponse.model_validate(c) for c in categories]


@router.get("/templates", response_model=list[TemplateSummary])
async def list_templates(
    session: SessionDep,
    category: str | None = Query(default=None, description="Filter by category slug"),
) -> list[TemplateSummary]:
    templates = await catalog_service.list_templates(session, category_slug=category)
    return [TemplateSummary.model_validate(t) for t in templates]


@router.get("/templates/{slug}", response_model=TemplateDetail)
async def get_template(slug: str, session: SessionDep, storage: StorageDep) -> TemplateDetail:
    try:
        template = await catalog_service.get_template(session, slug=slug)
        version = await catalog_service.current_version(session, template=template)
    except catalog_service.TemplateNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contractul nu a fost găsit."
        ) from None

    # Recorded at upload time. Falling back to rendering here would make the
    # detail page wait on LibreOffice, so a missing count is treated as an
    # unknown rather than an excuse to go and find out.
    page_count = version.page_count or 0

    return TemplateDetail(
        **TemplateSummary.model_validate(template).model_dump(exclude={"price_mdl"}),
        page_count=page_count,
        free_pages=preview_service.FREE_PAGES,
    )


@router.get(
    "/templates/{slug}/preview/{page}",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
    summary="A preview page as PNG",
)
async def get_preview(
    slug: str,
    session: SessionDep,
    storage: StorageDep,
    # ge=1 rather than a hand-rolled check: FastAPI rejects 0 and negatives
    # before the handler runs, and documents the bound in the OpenAPI schema.
    page: int = Path(ge=1, description="1-based page number"),
) -> Response:
    """Public.

    Pages past the free one come back at a resolution too low to read. That is
    the paywall — not the CSS blur the design applies on top, which anyone can
    remove. See app.services.previews.
    """
    try:
        template = await catalog_service.get_template(session, slug=slug)
        version = await catalog_service.current_version(session, template=template)
    except catalog_service.TemplateNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Contractul nu a fost găsit."
        ) from None

    try:
        # LibreOffice is a blocking subprocess. Called directly it would stall
        # the event loop for seconds and freeze every other request on the
        # worker; to_thread keeps it off the loop.
        image = await anyio.to_thread.run_sync(
            lambda: preview_service.render_preview(
                storage,
                version_id=str(version.id),
                docx_key=version.docx_object_key,
                page=page,
            )
        )
    except RenderError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc

    return Response(
        content=image,
        media_type="image/png",
        # Immutable: a version's rendered pages never change, because a
        # template revision creates a new version rather than editing this one.
        headers={"Cache-Control": "public, max-age=86400, immutable"},
    )

"""Catalog endpoints, including the paywall.

The preview tests are the important ones. The design blurs locked pages with
CSS, and CSS is not a paywall — so these assert that the bytes we send for a
locked page cannot be read no matter what the client does with them.
"""

from __future__ import annotations

import io
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_storage
from app.integrations.storage.base import Storage
from app.main import app
from app.models.catalog import Category, ContractTemplate, TemplateVersion
from app.services import previews as preview_service

FIXTURE = "tests/fixtures/activare-2fa.docx"
DOCX_KEY = "templates/test/sample.docx"


@pytest.fixture
def storage(tmp_path_factory: pytest.TempPathFactory) -> Storage:
    """Real storage in a temp directory, overriding the app's."""
    from app.integrations.storage.local import LocalStorage

    store = LocalStorage(tmp_path_factory.mktemp("storage"))
    with open(FIXTURE, "rb") as handle:
        store.put(DOCX_KEY, handle.read())

    app.dependency_overrides[get_storage] = lambda: store
    yield store
    app.dependency_overrides.pop(get_storage, None)


async def _seed(session: AsyncSession, *, published: bool = True) -> ContractTemplate:
    category = Category(slug="servicii", name="Servicii", sort_order=1)
    session.add(category)
    await session.flush()

    template = ContractTemplate(
        category_id=category.id,
        slug="prestari-servicii",
        name="Contract de prestări servicii",
        description="Reglementează prestarea de servicii.",
        price_bani=90000,
        languages=["ro", "ru"],
        is_published=published,
    )
    session.add(template)
    await session.flush()

    session.add(
        TemplateVersion(
            template_id=template.id,
            version=1,
            docx_object_key=DOCX_KEY,
            page_count=2,
            is_current=True,
        )
    )
    await session.flush()
    return template


# ─── Browsing ────────────────────────────────────────────────────────────────


async def test_catalog_is_public(client: AsyncClient, session: AsyncSession) -> None:
    """No account needed to browse the shop. Buying is a different matter."""
    await _seed(session)

    response = await client.get("/api/v1/templates")

    assert response.status_code == 200
    assert len(response.json()) == 1


async def test_template_list_includes_price_and_languages(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _seed(session)

    body = (await client.get("/api/v1/templates")).json()[0]

    assert body["price_bani"] == 90000
    assert body["price_mdl"] == "900"
    assert body["languages"] == ["ro", "ru"]


async def test_unpublished_templates_are_invisible(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _seed(session, published=False)

    assert (await client.get("/api/v1/templates")).json() == []


async def test_an_unpublished_template_is_a_404_not_a_403(
    client: AsyncClient, session: AsyncSession
) -> None:
    """A draft's URL must not confirm that the draft exists."""
    await _seed(session, published=False)

    response = await client.get("/api/v1/templates/prestari-servicii")

    assert response.status_code == 404


async def test_category_filter(client: AsyncClient, session: AsyncSession) -> None:
    await _seed(session)

    assert len((await client.get("/api/v1/templates?category=servicii")).json()) == 1
    assert (await client.get("/api/v1/templates?category=transport")).json() == []


async def test_detail_reports_page_count_and_free_pages(
    client: AsyncClient, session: AsyncSession
) -> None:
    await _seed(session)

    body = (await client.get("/api/v1/templates/prestari-servicii")).json()

    assert body["page_count"] == 2
    assert body["free_pages"] == preview_service.FREE_PAGES


async def test_unknown_slug_is_404(client: AsyncClient, session: AsyncSession) -> None:
    assert (await client.get("/api/v1/templates/nu-exista")).status_code == 404


# ─── The paywall ─────────────────────────────────────────────────────────────


def _png_size(data: bytes) -> tuple[int, int]:
    """Width and height from the PNG IHDR chunk, without an image library."""
    header = io.BytesIO(data).read(24)
    width = int.from_bytes(header[16:20], "big")
    height = int.from_bytes(header[20:24], "big")
    return width, height


async def test_free_page_is_served_at_readable_resolution(
    client: AsyncClient, session: AsyncSession, storage: Storage
) -> None:
    await _seed(session)

    response = await client.get("/api/v1/templates/prestari-servicii/preview/1")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    width, _ = _png_size(response.content)
    assert width > 700, "Page 1 is the free sample and must be legible"


async def test_locked_page_is_served_too_small_to_read(
    client: AsyncClient, session: AsyncSession, storage: Storage
) -> None:
    """**The paywall.**

    The design blurs this page with CSS. CSS is a filter on an image the
    browser already holds — anyone can open the URL directly or delete the
    style rule. So the protection cannot live there.

    Page 2 is rendered at 18 dpi. Its text is not obscured, it is absent:
    the pixels were never drawn. No amount of upscaling recovers information
    that was never sent.
    """
    await _seed(session)

    free = await client.get("/api/v1/templates/prestari-servicii/preview/1")
    locked = await client.get("/api/v1/templates/prestari-servicii/preview/2")

    assert locked.status_code == 200

    free_width, _ = _png_size(free.content)
    locked_width, _ = _png_size(locked.content)

    assert locked_width < free_width / 4, (
        f"Locked page is {locked_width}px wide against a free page of {free_width}px. "
        "It must be far too small to read."
    )
    assert len(locked.content) < len(free.content) / 5


async def test_no_endpoint_serves_a_locked_page_at_full_quality(
    client: AsyncClient, session: AsyncSession, storage: Storage
) -> None:
    """Resolution is decided from the page number, so it cannot be asked for.

    There is deliberately no parameter a client could set. This pins that
    down: if someone later adds a `dpi` or `quality` argument as a
    convenience, the paywall quietly disappears.
    """
    await _seed(session)

    for attempt in ["?dpi=110", "?quality=full", "?locked=false", "?full=1"]:
        response = await client.get(
            f"/api/v1/templates/prestari-servicii/preview/2{attempt}"
        )
        width, _ = _png_size(response.content)
        assert width < 300, f"{attempt} produced a {width}px image — the paywall leaked"


async def test_preview_is_cached_after_the_first_render(
    client: AsyncClient, session: AsyncSession, storage: Storage
) -> None:
    """LibreOffice takes seconds. A catalog that re-rendered per request is unusable."""
    template = await _seed(session)
    version_id = str(
        (await session.scalars(
            __import__("sqlalchemy").select(TemplateVersion).where(
                TemplateVersion.template_id == template.id
            )
        )).one().id
    )

    await client.get("/api/v1/templates/prestari-servicii/preview/1")

    assert storage.exists(preview_service.preview_key(version_id, 1, locked=False))


async def test_preview_sets_a_cache_header(
    client: AsyncClient, session: AsyncSession, storage: Storage
) -> None:
    await _seed(session)

    response = await client.get("/api/v1/templates/prestari-servicii/preview/1")

    assert "immutable" in response.headers["cache-control"]


async def test_page_zero_and_negatives_are_rejected(
    client: AsyncClient, session: AsyncSession, storage: Storage
) -> None:
    await _seed(session)

    assert (await client.get("/api/v1/templates/prestari-servicii/preview/0")).status_code == 422


async def test_page_beyond_the_document_is_404(
    client: AsyncClient, session: AsyncSession, storage: Storage
) -> None:
    await _seed(session)

    assert (await client.get("/api/v1/templates/prestari-servicii/preview/9")).status_code == 404


async def test_preview_of_an_unpublished_template_is_404(
    client: AsyncClient, session: AsyncSession, storage: Storage
) -> None:
    """Otherwise the paywall is bypassed by never publishing at all."""
    await _seed(session, published=False)

    assert (await client.get("/api/v1/templates/prestari-servicii/preview/1")).status_code == 404


def test_free_pages_is_one() -> None:
    """Pinning the business rule. Raising this gives the document away."""
    assert preview_service.FREE_PAGES == 1
    assert preview_service.is_locked(1) is False
    assert preview_service.is_locked(2) is True


def test_locked_dpi_is_illegible() -> None:
    """Verified by eye at 18 dpi: body text cannot be read.

    If someone raises this to "improve the preview", the document becomes free.
    """
    assert preview_service.LOCKED_DPI <= 20
    assert preview_service.LOCKED_DPI < preview_service.FULL_DPI / 4

"""Document preview images.

The contract detail page shows page one of a document and locks the rest behind
the paywall.

**How the paywall actually works.** The design blurs the locked pages with CSS.
CSS is not protection — it is a filter applied to an image the browser already
has, and anyone can open the image URL directly, or just delete the style rule.
If we served the real pages and blurred them client-side, the entire document
would be free to anyone who opened devtools.

So locked pages are rendered at LOW RESOLUTION and never at full. The pixels
carrying the text simply are not sent. At 18 dpi the body text is not blurred,
it is *gone* — no amount of upscaling recovers information that was never
there. The CSS blur stays, purely as decoration on top of an image that is
already safe.

Previews are cached in storage after the first render: LibreOffice takes
seconds, and a catalog page rendering documents on every request would be
unusable.
"""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from app.documents.renderer import RenderError, docx_to_pdf, fill_template, pdf_to_previews
from app.integrations.storage.base import ObjectNotFound, Storage

logger = logging.getLogger(__name__)

# Readable on screen.
FULL_DPI = 110

# Deliberately illegible. Verified by eye and by test: body text at this
# resolution cannot be read, and cannot be recovered.
LOCKED_DPI = 18

# Page 1 is the free sample. Everything after it is locked.
FREE_PAGES = 1


def preview_key(version_id: str, page: int, *, locked: bool) -> str:
    quality = "locked" if locked else "full"
    return f"previews/{version_id}/{quality}-{page}.png"


def is_locked(page: int) -> bool:
    return page > FREE_PAGES


def render_preview(
    storage: Storage,
    *,
    version_id: str,
    docx_key: str,
    page: int,
) -> bytes:
    """The PNG for one page, rendering and caching it on first request.

    Resolution is decided here, from the page number alone — a caller cannot
    ask for a locked page at full quality, because there is no argument for it.
    """
    locked = is_locked(page)
    key = preview_key(version_id, page, locked=locked)

    try:
        return storage.get(key)
    except ObjectNotFound:
        pass

    logger.info("Rendering preview page %s of version %s (locked=%s)", page, version_id, locked)

    with tempfile.TemporaryDirectory(prefix="preview-") as tmp:
        workdir = Path(tmp)

        source = workdir / "template.docx"
        source.write_bytes(storage.get(docx_key))

        filled = fill_template(source, {}, workdir / "filled.docx")
        pdf = docx_to_pdf(filled, workdir)
        pages = pdf_to_previews(pdf, workdir / "png", dpi=LOCKED_DPI if locked else FULL_DPI)

        if page > len(pages):
            raise RenderError(f"Page {page} does not exist (document has {len(pages)})")

        data = pages[page - 1].read_bytes()

    storage.put(key, data)
    return data


def count_pages(storage: Storage, *, docx_key: str) -> int:
    """How many pages the rendered document has."""
    with tempfile.TemporaryDirectory(prefix="pagecount-") as tmp:
        workdir = Path(tmp)
        source = workdir / "template.docx"
        source.write_bytes(storage.get(docx_key))

        filled = fill_template(source, {}, workdir / "filled.docx")
        pdf = docx_to_pdf(filled, workdir)

        from pypdf import PdfReader

        return len(PdfReader(str(pdf)).pages)

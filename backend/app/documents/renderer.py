"""DOCX rendering and PDF conversion.

The product is the document, so this is the part of the system that matters
most. Two steps, deliberately separate:

    1. Fill    — merge data into a .docx template, preserving Word formatting.
    2. Convert — turn the filled .docx into a PDF via headless LibreOffice.

Both outputs are sold: the PDF to read and the .docx to edit.

Phase 1 status: this is the spike promoted into real code. It renders and
converts correctly (proven by tests/integration/test_renderer.py against a
bilingual RO/RU fixture). It is not yet wired to orders or storage — that is
phase 7. See docs/roadmap.md.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from docxtpl import DocxTemplate

logger = logging.getLogger(__name__)

# LibreOffice occasionally wedges on a malformed document. Without a timeout
# that is a hung worker rather than a failed request.
CONVERSION_TIMEOUT_SECONDS = 120


class RenderError(RuntimeError):
    """Raised when a document cannot be produced.

    Always recoverable at the business level: a paid order whose document
    failed to render is retried, never refunded silently. Rendering happens
    outside the payment transaction precisely so this cannot undo a payment.
    """


def fill_template(template_path: Path, context: dict[str, Any], output_path: Path) -> Path:
    """Merge `context` into a .docx template and write the result.

    A template with no placeholders is copied through unchanged, which is a
    valid outcome rather than an error — it is how a fixed-text document works.
    """
    if not template_path.is_file():
        raise RenderError(f"Template not found: {template_path}")

    try:
        document = DocxTemplate(str(template_path))
        document.render(context)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        document.save(str(output_path))
    except Exception as exc:  # docxtpl surfaces template errors as bare Exception
        raise RenderError(f"Could not fill template {template_path.name}: {exc}") from exc

    return output_path


def docx_to_pdf(docx_path: Path, output_dir: Path) -> Path:
    """Convert a .docx to PDF with headless LibreOffice.

    LibreOffice is a subprocess, not a library, and it is opinionated about
    where it keeps its profile. Each call gets a private profile directory:
    concurrent conversions sharing one profile corrupt each other, and the
    failure looks like a random hang rather than a lock error.
    """
    if not docx_path.is_file():
        raise RenderError(f"Document not found: {docx_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="soffice-profile-") as profile_dir:
        command = [
            "soffice",
            f"-env:UserInstallation=file://{profile_dir}",
            "--headless",
            "--norestore",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(docx_path),
        ]
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=CONVERSION_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise RenderError(
                f"LibreOffice timed out after {CONVERSION_TIMEOUT_SECONDS}s "
                f"converting {docx_path.name}"
            ) from exc

    pdf_path = output_dir / f"{docx_path.stem}.pdf"

    # LibreOffice reports success in its exit code unreliably — it can exit 0
    # having produced nothing. The file existing is the only honest check.
    if not pdf_path.is_file():
        raise RenderError(
            f"LibreOffice produced no PDF for {docx_path.name}. "
            f"exit={result.returncode} stdout={result.stdout.strip()} "
            f"stderr={result.stderr.strip()}"
        )

    logger.info("Converted %s -> %s", docx_path.name, pdf_path.name)
    return pdf_path


def pdf_to_previews(pdf_path: Path, output_dir: Path, dpi: int = 110) -> list[Path]:
    """Rasterise every page of a PDF to PNG, for on-screen previews.

    Used by the contract detail page, which shows page one and locks the rest
    behind the paywall.
    """
    if not shutil.which("pdftoppm"):
        raise RenderError("pdftoppm not found — poppler-utils is not installed")

    output_dir.mkdir(parents=True, exist_ok=True)
    prefix = output_dir / pdf_path.stem

    try:
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), str(pdf_path), str(prefix)],
            capture_output=True,
            text=True,
            timeout=CONVERSION_TIMEOUT_SECONDS,
            check=True,
        )
    except subprocess.CalledProcessError as exc:
        raise RenderError(f"pdftoppm failed on {pdf_path.name}: {exc.stderr}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RenderError(f"pdftoppm timed out on {pdf_path.name}") from exc

    pages = sorted(output_dir.glob(f"{pdf_path.stem}-*.png"))
    if not pages:
        raise RenderError(f"pdftoppm produced no pages for {pdf_path.name}")

    return pages

"""Regenerate the design prototype's document preview images.

The prototype has no backend, so its Detaliu Contract preview shows committed
PNGs. They are real output — this script runs the actual phase 1 pipeline
(docxtpl -> LibreOffice -> PDF -> pdftoppm) over the fixture and writes the
pages the prototype displays.

Run from the backend container, which is where LibreOffice lives:

    docker compose exec backend python -m scripts.render_preview
    docker compose cp backend:/tmp/doc-preview/. ./assets/doc-preview/

Temporary: dies with the prototype in phase 4, when the real screen renders
previews on demand from real templates.
"""

import shutil
import sys
import tempfile
from pathlib import Path

from app.documents.renderer import RenderError, docx_to_pdf, fill_template, pdf_to_previews

FIXTURE = Path("tests/fixtures/activare-2fa.docx")
OUTPUT_DIR = Path("/tmp/doc-preview")


def main() -> int:
    if not FIXTURE.is_file():
        print(f"Fixture not found: {FIXTURE.resolve()}", file=sys.stderr)
        return 1

    workdir = Path(tempfile.mkdtemp(prefix="preview-"))

    try:
        filled = fill_template(FIXTURE, {}, workdir / "doc.docx")
        pdf = docx_to_pdf(filled, workdir)
        pages = pdf_to_previews(pdf, workdir / "png", dpi=110)
    except RenderError as exc:
        print(f"Rendering failed: {exc}", file=sys.stderr)
        return 1

    if OUTPUT_DIR.exists():
        shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)

    for page in pages:
        shutil.copy2(page, OUTPUT_DIR / page.name)
        print(f"  {OUTPUT_DIR / page.name}  ({page.stat().st_size:,} bytes)")

    print(f"\n{len(pages)} page(s) written to {OUTPUT_DIR}")
    print("Copy them out with:")
    print(f"  docker compose cp backend:{OUTPUT_DIR}/. ./assets/doc-preview/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

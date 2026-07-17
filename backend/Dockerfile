FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Document rendering toolchain.
#
#   libreoffice-writer  DOCX -> PDF. Writer only, not the whole suite — we have
#                       no use for spreadsheets or slides and they are large.
#   poppler-utils       pdftoppm, for rasterising PDF pages to preview images.
#   fonts-*             The reason this list is explicit. The templates carry
#                       Romanian diacritics (ă î ș ț â) and Cyrillic, and
#                       LibreOffice substitutes fonts silently: a missing glyph
#                       becomes a box in the PDF with no error anywhere. DejaVu
#                       and Liberation both cover Latin Extended-A and Cyrillic,
#                       and Liberation is metric-compatible with the Arial and
#                       Times the templates are authored against.
#
# This is the expensive layer — a few hundred MB and several minutes. It is
# placed before the dependency install so that editing pyproject.toml does not
# reinstall LibreOffice.
RUN apt-get update && apt-get install -y --no-install-recommends \
        libreoffice-writer \
        poppler-utils \
        fonts-dejavu \
        fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first, in their own layer. The editable install needs the
# package directory to exist, so app/ is copied before it — but only the
# source tree, not tests or config, so that editing a test does not
# reinstall every dependency.
COPY pyproject.toml ./
COPY app ./app
RUN pip install --upgrade pip && pip install -e ".[dev]"

COPY . .

EXPOSE 8000

# Development overrides this with --reload. See docker-compose.override.yml.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

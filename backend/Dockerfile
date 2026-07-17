FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# LibreOffice is NOT installed here yet. It arrives in phase 1 (the rendering
# spike) and will add several hundred megabytes and minutes to this build.
# See docs/roadmap.md.

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

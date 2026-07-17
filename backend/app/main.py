"""Application construction.

Deliberately thin. This file wires things together; it does not decide
anything. Logic lives in services, HTTP concerns live in routes.
"""

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import get_settings

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s: %(message)s",
)

settings = get_settings()

app = FastAPI(
    title="Contractul.md API",
    description="Self-service legal contracts",
    version="0.1.0",
    docs_url="/docs",
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    # Explicit origins, never "*". Credentials cross this boundary once
    # authentication lands, and a wildcard would be a real hole.
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Versioned from the first commit. Retrofitting versioning later means either
# breaking every client at once or bolting a scheme onto a structure that
# fights it. See docs/project-structure.md.
app.include_router(api_router, prefix="/api/v1")


@app.get("/", include_in_schema=False)
async def root() -> dict[str, str]:
    return {
        "service": "contractul-backend",
        "docs": "/docs",
        "health": "/api/v1/health",
    }

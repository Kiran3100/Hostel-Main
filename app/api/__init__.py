# api/__init__.py
from __future__ import annotations

"""
Top-level API router package.

Usage in FastAPI app:

    from api import api_router
    app.include_router(api_router, prefix="/api")
"""

from fastapi import APIRouter

from .v1 import api_router as v1_router

api_router = APIRouter()

# All v1 routes will end up under /api/v1 when mounted with prefix="/api"
api_router.include_router(v1_router, prefix="/v1")

__all__ = ["APIRouter", "api_router"]
# app/api/v1/__init__.py
from __future__ import annotations

"""
API v1 package.

This module re-exports the main FastAPI router that aggregates all
v1 sub-routers (auth, users, hostels, bookings, etc.).

The actual router composition lives in `app.api.v1.router`.
"""

from fastapi import APIRouter

from .router import router as api_router  # main v1 router

# `api_router` is what you typically include into the FastAPI app:
#
#     from app.api.v1 import api_router as api_v1_router
#     app.include_router(api_v1_router, prefix="/api/v1")
#

__all__ = [
    "APIRouter",
    "api_router",
]
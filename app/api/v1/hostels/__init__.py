# api/v1/hostels/__init__.py
from __future__ import annotations

from fastapi import APIRouter

from . import hostels
from . import details
from . import analytics
from . import comparison
from . import public
from . import search

router = APIRouter(prefix="/hostels")

router.include_router(hostels.router, tags=["Hostels - Internal"])
router.include_router(details.router, tags=["Hostels - Admin View"])
router.include_router(analytics.router, tags=["Hostels - Analytics"])
router.include_router(comparison.router, tags=["Hostels - Comparison"])
router.include_router(public.router, tags=["Hostels - Public"])
router.include_router(search.router, tags=["Hostels - Search"])

__all__ = ["router"]
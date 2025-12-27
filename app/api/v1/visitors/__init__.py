"""
Visitor API router aggregation module.

This module combines all visitor-related API routers into a single router
for easy inclusion in the main application router.
"""

from fastapi import APIRouter

from .dashboard import router as dashboard_router
from .favorites import router as favorites_router
from .preferences import router as preferences_router
from .recommendations import router as recommendations_router
from .saved_searches import router as saved_searches_router
from .visitors import router as visitors_router

# Create main visitors router
router = APIRouter()

# Include all sub-routers
router.include_router(visitors_router)
router.include_router(dashboard_router)
router.include_router(favorites_router)
router.include_router(preferences_router)
router.include_router(recommendations_router)
router.include_router(saved_searches_router)

__all__ = ["router"]
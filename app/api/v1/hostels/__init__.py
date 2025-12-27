"""
Hostel API Router Module
Aggregates all hostel-related API endpoints
"""
from fastapi import APIRouter

from . import (
    amenities,
    analytics,
    comparison,
    hostels,
    media,
    policies,
    public,
    rooms,
    settings,
)

# Create main router
router = APIRouter()

# Include all sub-routers in logical order
# Core hostel endpoints first
router.include_router(hostels.router)

# Public endpoints (no auth required)
router.include_router(public.router)

# Feature-specific endpoints
router.include_router(rooms.router)
router.include_router(amenities.router)
router.include_router(media.router)
router.include_router(policies.router)

# Advanced features
router.include_router(analytics.router)
router.include_router(comparison.router)
router.include_router(settings.router)

# Export router for use in main application
__all__ = ["router"]
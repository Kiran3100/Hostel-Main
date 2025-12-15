"""
Admin API module for hostel management platform.

Provides comprehensive administrative functionality including:
- Dashboard and analytics
- Hostel management
- Admin-hostel assignments
- Permission matrix management
- Administrative overrides
- Multi-hostel dashboard views

All endpoints are designed for administrative users and include
proper authorization checks, audit logging, and error handling.
"""

from fastapi import APIRouter

from . import (
    dashboard,
    hostels,
    assignments,
    permissions,
    overrides,
    multi_hostel,
)

# Create main admin router
router = APIRouter(prefix="/admin", tags=["Admin"])

# Include sub-routers with clear organization
router.include_router(dashboard.router)
router.include_router(hostels.router)
router.include_router(assignments.router)
router.include_router(permissions.router)
router.include_router(overrides.router)
router.include_router(multi_hostel.router)

__all__ = [
    "router",
    "dashboard",
    "hostels",
    "assignments",
    "permissions",
    "overrides",
    "multi_hostel",
]
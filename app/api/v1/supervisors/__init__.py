"""
Supervisor API v1 Module

This module provides comprehensive supervisor management endpoints including:
- Core CRUD operations
- Activity tracking and logging
- Hostel assignments
- Dashboard analytics
- Performance metrics and reviews
- Permission management

All routers are aggregated here for easy inclusion in the main API router.
"""

from fastapi import APIRouter

from .supervisors import router as supervisors_router
from .activity import router as activity_router
from .assignments import router as assignments_router
from .dashboard import router as dashboard_router
from .performance import router as performance_router
from .permissions import router as permissions_router

# Create main router with common prefix and tags
router = APIRouter(prefix="/supervisors", tags=["Supervisors"])

# Include all sub-routers (they already have their own prefixes and tags)
router.include_router(supervisors_router)
router.include_router(activity_router)
router.include_router(assignments_router)
router.include_router(dashboard_router)
router.include_router(performance_router)
router.include_router(permissions_router)

__all__ = [
    "router",
    "supervisors_router",
    "activity_router",
    "assignments_router",
    "dashboard_router",
    "performance_router",
    "permissions_router",
]
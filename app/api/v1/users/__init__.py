"""
User management API module.

Aggregates all user-related routers:
- Core user CRUD operations
- Profile management
- Preferences configuration
- Session management
- Data export functionality
"""
from fastapi import APIRouter

from . import (
    users,
    profile,
    preferences,
    sessions,
    data_export,
)

# Create main user router
router = APIRouter()

# Include all sub-routers
router.include_router(users.router)
router.include_router(profile.router)
router.include_router(preferences.router)
router.include_router(sessions.router)
router.include_router(data_export.router)

# Export router for main API aggregation
__all__ = ["router"]
"""
Notification API Module

Aggregates all notification-related routers:
- Main notifications (sending, listing, analytics)
- Device token management
- User preferences
- Template management
"""

from fastapi import APIRouter

from . import notifications, devices, preferences, templates

# Create main notification router
router = APIRouter()

# Include all sub-routers
router.include_router(notifications.router)
router.include_router(devices.router)
router.include_router(preferences.router)
router.include_router(templates.router)

__all__ = ["router"]
"""
Room Management API Module

This module provides comprehensive room management endpoints including:
- Room CRUD operations
- Bed management and assignments
- Room type definitions
- Availability checking and forecasting
- Dynamic pricing management
"""

from fastapi import APIRouter

from .rooms import router as rooms_router
from .beds import router as beds_router
from .types import router as types_router
from .availability import router as availability_router
from .pricing import router as pricing_router

# Main router for room-related endpoints
router = APIRouter()

# Include sub-routers in logical order
router.include_router(types_router)  # Types first (foundation)
router.include_router(rooms_router)  # Rooms second
router.include_router(beds_router)   # Beds third
router.include_router(availability_router)  # Availability fourth
router.include_router(pricing_router)  # Pricing last

__all__ = ["router"]
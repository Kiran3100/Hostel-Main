"""
Booking API Router Module

This module aggregates all booking-related API endpoints including:
- Core booking operations (CRUD)
- Approval workflows
- Room/bed assignments
- Calendar and availability
- Cancellations and refunds
- Booking modifications
- Student conversions
- Waitlist management
- Advanced search and export
"""

from fastapi import APIRouter

from .approval import router as approval_router
from .assignment import router as assignment_router
from .bookings import router as bookings_router
from .calendar import router as calendar_router
from .cancellation import router as cancellation_router
from .conversion import router as conversion_router
from .modification import router as modification_router
from .search import router as search_router
from .waitlist import router as waitlist_router

# Initialize main router
router = APIRouter()

# Include all sub-routers in logical order
router.include_router(bookings_router)
router.include_router(search_router)
router.include_router(calendar_router)
router.include_router(approval_router)
router.include_router(assignment_router)
router.include_router(modification_router)
router.include_router(cancellation_router)
router.include_router(conversion_router)
router.include_router(waitlist_router)

__all__ = ["router"]
# api/v1/bookings/__init__.py
from __future__ import annotations

from fastapi import APIRouter

from . import bookings
from . import approval
from . import calendar
from . import assignment
from . import cancellation
from . import modification
from . import waitlist
from . import conversion
from . import analytics

router = APIRouter(prefix="/bookings")

router.include_router(bookings.router, tags=["Bookings - Core"])
router.include_router(approval.router, tags=["Bookings - Approval"])
router.include_router(calendar.router, tags=["Bookings - Calendar"])
router.include_router(assignment.router, tags=["Bookings - Assignment"])
router.include_router(cancellation.router, tags=["Bookings - Cancellation"])
router.include_router(modification.router, tags=["Bookings - Modification"])
router.include_router(waitlist.router, tags=["Bookings - Waitlist"])
router.include_router(conversion.router, tags=["Bookings - Conversion"])
router.include_router(analytics.router, tags=["Bookings - Analytics"])

__all__ = ["router"]
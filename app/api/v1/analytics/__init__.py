from __future__ import annotations

from fastapi import APIRouter

from . import dashboard
from . import financial
from . import occupancy
from . import complaints
from . import visitors
from . import bookings
from . import supervisors
from . import platform
from . import custom

router = APIRouter(prefix="/analytics")

router.include_router(dashboard.router, tags=["Analytics - Dashboard"])
router.include_router(financial.router, tags=["Analytics - Financial"])
router.include_router(occupancy.router, tags=["Analytics - Occupancy"])
router.include_router(complaints.router, tags=["Analytics - Complaints"])
router.include_router(visitors.router, tags=["Analytics - Visitors"])
router.include_router(bookings.router, tags=["Analytics - Bookings"])
router.include_router(supervisors.router, tags=["Analytics - Supervisors"])
router.include_router(platform.router, tags=["Analytics - Platform"])
router.include_router(custom.router, tags=["Analytics - Custom Reports"])

__all__ = ["router"]
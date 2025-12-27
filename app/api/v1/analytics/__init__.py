"""
Analytics API Router Module.

Aggregates all analytics sub-routers under the /analytics prefix.
Provides comprehensive analytics capabilities for:
- Bookings
- Complaints
- Dashboard
- Financial
- Occupancy
- Platform
- Reports/Exports
"""

from fastapi import APIRouter

from .bookings import router as bookings_router
from .complaints import router as complaints_router
from .dashboard import router as dashboard_router
from .financial import router as financial_router
from .occupancy import router as occupancy_router
from .platform import router as platform_router
from .reports import router as reports_router

router = APIRouter(prefix="/analytics")

# Include all sub-routers with explicit ordering
_sub_routers = [
    bookings_router,
    complaints_router,
    dashboard_router,
    financial_router,
    occupancy_router,
    platform_router,
    reports_router,
]

for sub_router in _sub_routers:
    router.include_router(sub_router)

__all__ = ["router"]
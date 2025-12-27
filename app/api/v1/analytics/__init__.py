from fastapi import APIRouter

from . import bookings, complaints, dashboard, financial, occupancy, platform, reports

router = APIRouter(prefix="/analytics")
router.include_router(bookings.router)
router.include_router(complaints.router)
router.include_router(dashboard.router)
router.include_router(financial.router)
router.include_router(occupancy.router)
router.include_router(platform.router)
router.include_router(reports.router)

__all__ = ["router"]
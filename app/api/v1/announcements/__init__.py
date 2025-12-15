# api/v1/announcements/__init__.py

from fastapi import APIRouter

from . import announcements
from . import targeting
from . import scheduling
from . import approval
from . import delivery
from . import tracking

router = APIRouter(prefix="/announcements")

router.include_router(announcements.router, tags=["Announcements - Core"])
router.include_router(targeting.router, tags=["Announcements - Targeting"])
router.include_router(scheduling.router, tags=["Announcements - Scheduling"])
router.include_router(approval.router, tags=["Announcements - Approval"])
router.include_router(delivery.router, tags=["Announcements - Delivery"])
router.include_router(tracking.router, tags=["Announcements - Tracking"])

__all__ = ["router"]
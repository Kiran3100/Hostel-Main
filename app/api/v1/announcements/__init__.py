from fastapi import APIRouter

from . import announcements, approval, scheduling, targeting, tracking

router = APIRouter()
router.include_router(announcements.router)
router.include_router(approval.router)
router.include_router(scheduling.router)
router.include_router(targeting.router)
router.include_router(tracking.router)

__all__ = ["router"]
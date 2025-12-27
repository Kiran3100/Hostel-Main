from fastapi import APIRouter

from . import alerts, attendance, check_in, policies, reports

router = APIRouter()
router.include_router(attendance.router)
router.include_router(check_in.router)
router.include_router(alerts.router)
router.include_router(policies.router)
router.include_router(reports.router)

__all__ = ["router"]
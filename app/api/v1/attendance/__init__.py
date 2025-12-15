# api/v1/attendance/__init__.py
from __future__ import annotations

from fastapi import APIRouter

from . import attendance
from . import record
from . import bulk
from . import reports
from . import policy
from . import alerts

router = APIRouter(prefix="/attendance")

router.include_router(attendance.router, tags=["Attendance - Records"])
router.include_router(record.router, tags=["Attendance - Marking"])
router.include_router(bulk.router, tags=["Attendance - Bulk"])
router.include_router(reports.router, tags=["Attendance - Reports"])
router.include_router(policy.router, tags=["Attendance - Policy"])
router.include_router(alerts.router, tags=["Attendance - Alerts"])

__all__ = ["router"]
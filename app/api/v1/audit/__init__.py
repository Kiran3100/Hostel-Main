# api/v1/audit/__init__.py
from __future__ import annotations

from fastapi import APIRouter

from . import logs
from . import overrides
from . import activity
from . import reports

router = APIRouter(prefix="/audit")

router.include_router(logs.router, tags=["Audit - Logs"])
router.include_router(overrides.router, tags=["Audit - Admin Overrides"])
router.include_router(activity.router, tags=["Audit - Supervisor Activity"])
router.include_router(reports.router, tags=["Audit - Reports"])

__all__ = ["router"]
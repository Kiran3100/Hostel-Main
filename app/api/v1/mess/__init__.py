# api/v1/mess/__init__.py
from __future__ import annotations

from fastapi import APIRouter

from . import menu
from . import planning
from . import feedback
from . import approval
from . import duplicate

router = APIRouter(prefix="/mess")

router.include_router(menu.router, tags=["Mess - Menu"])
router.include_router(planning.router, tags=["Mess - Planning"])
router.include_router(feedback.router, tags=["Mess - Feedback"])
router.include_router(approval.router, tags=["Mess - Approval"])
router.include_router(duplicate.router, tags=["Mess - Duplication"])

__all__ = ["router"]
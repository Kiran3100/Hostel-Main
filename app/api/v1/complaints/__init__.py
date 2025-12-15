# api/v1/complaints/__init__.py
from __future__ import annotations

from fastapi import APIRouter

from . import complaints
from . import assignment
from . import resolution
from . import escalation
from . import feedback
from . import comments
from . import analytics

router = APIRouter(prefix="/complaints")

router.include_router(complaints.router, tags=["Complaints - Core"])
router.include_router(assignment.router, tags=["Complaints - Assignment"])
router.include_router(resolution.router, tags=["Complaints - Resolution"])
router.include_router(escalation.router, tags=["Complaints - Escalation"])
router.include_router(feedback.router, tags=["Complaints - Feedback"])
router.include_router(comments.router, tags=["Complaints - Comments"])
router.include_router(analytics.router, tags=["Complaints - Analytics"])

__all__ = ["router"]
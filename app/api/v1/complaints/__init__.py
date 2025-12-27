from fastapi import APIRouter

from . import (
    assignment,
    comments,
    complaints,
    escalation,
    feedback,
    resolution,
)

router = APIRouter()

router.include_router(complaints.router)
router.include_router(assignment.router)
router.include_router(comments.router)
router.include_router(escalation.router)
router.include_router(resolution.router)
router.include_router(feedback.router)

__all__ = ["router"]
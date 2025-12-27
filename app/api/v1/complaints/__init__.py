"""
Complaint Management API Module
Aggregates all complaint-related routers and exposes a unified router.
"""
from fastapi import APIRouter

from . import (
    assignment,
    comments,
    complaints,
    escalation,
    feedback,
    resolution,
)

# Create main router for complaint management
router = APIRouter()

# Include all sub-routers
router.include_router(complaints.router)
router.include_router(assignment.router)
router.include_router(comments.router)
router.include_router(escalation.router)
router.include_router(resolution.router)
router.include_router(feedback.router)

# Export router and all sub-modules
__all__ = [
    "router",
    "assignment",
    "comments",
    "complaints",
    "escalation",
    "feedback",
    "resolution",
]
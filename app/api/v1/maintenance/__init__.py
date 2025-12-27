"""
Maintenance API Module
Handles all maintenance-related operations including requests, assignments,
approvals, completions, schedules, and vendor management.
"""

from fastapi import APIRouter

from app.api.v1.maintenance import (
    approval,
    assignment,
    completion,
    requests,
    schedules,
    vendors,
)

# Initialize main maintenance router
router = APIRouter()

# Register all sub-routers with consistent ordering
router.include_router(requests.router)
router.include_router(assignment.router)
router.include_router(approval.router)
router.include_router(completion.router)
router.include_router(schedules.router)
router.include_router(vendors.router)

__all__ = ["router"]
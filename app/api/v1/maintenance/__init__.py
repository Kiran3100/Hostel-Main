from fastapi import APIRouter

from . import (
    approval,
    assignment,
    completion,
    requests,
    schedules,
    vendors,
)

router = APIRouter()

router.include_router(requests.router)
router.include_router(assignment.router)
router.include_router(approval.router)
router.include_router(completion.router)
router.include_router(schedules.router)
router.include_router(vendors.router)

__all__ = ["router"]
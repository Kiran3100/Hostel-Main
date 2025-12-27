from fastapi import APIRouter

from . import (
    approval,
    assignment,
    bookings,
    calendar,
    cancellation,
    conversion,
    modification,
    search,
    waitlist,
)

router = APIRouter()

router.include_router(bookings.router)
router.include_router(approval.router)
router.include_router(assignment.router)
router.include_router(calendar.router)
router.include_router(cancellation.router)
router.include_router(conversion.router)
router.include_router(modification.router)
router.include_router(search.router)
router.include_router(waitlist.router)

__all__ = ["router"]
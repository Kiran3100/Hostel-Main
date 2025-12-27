from fastapi import APIRouter

from . import approval, balance, calendar, leaves

router = APIRouter()

router.include_router(leaves.router)
router.include_router(approval.router)
router.include_router(balance.router)
router.include_router(calendar.router)

__all__ = ["router"]
from fastapi import APIRouter

from . import follow_ups, inquiries

router = APIRouter()

router.include_router(inquiries.router)
router.include_router(follow_ups.router)

__all__ = ["router"]
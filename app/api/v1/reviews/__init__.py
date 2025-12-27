from fastapi import APIRouter

from . import reviews, moderation, responses, voting

router = APIRouter()
router.include_router(reviews.router)
router.include_router(moderation.router)
router.include_router(responses.router)
router.include_router(voting.router)

__all__ = ["router"]
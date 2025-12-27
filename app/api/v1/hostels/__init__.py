from fastapi import APIRouter

from . import (
    amenities,
    analytics,
    comparison,
    hostels,
    media,
    policies,
    public,
    rooms,
    settings,
)

router = APIRouter()

router.include_router(hostels.router)
router.include_router(public.router)  # Public endpoints often at top level or under specific prefix
router.include_router(amenities.router)
router.include_router(analytics.router)
router.include_router(comparison.router)
router.include_router(media.router)
router.include_router(policies.router)
router.include_router(rooms.router)
router.include_router(settings.router)

__all__ = ["router"]
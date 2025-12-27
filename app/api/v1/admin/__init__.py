from fastapi import APIRouter

from . import admins, context, dashboard, hostel_assignments, overrides, permissions

router = APIRouter()
router.include_router(admins.router)
router.include_router(hostel_assignments.router)
router.include_router(overrides.router)
router.include_router(permissions.router)
router.include_router(context.router)
router.include_router(dashboard.router)

__all__ = ["router"]
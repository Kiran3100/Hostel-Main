"""
Mess Management API Module

This module aggregates all mess-related API routers including menus, items,
approval workflows, feedback, dietary options, and planning features.
"""

from fastapi import APIRouter

from . import menus, items, approval, feedback, dietary, planning

# Create main router for mess module
router = APIRouter()

# Include all sub-routers
router.include_router(menus.router)
router.include_router(items.router)
router.include_router(approval.router)
router.include_router(feedback.router)
router.include_router(dietary.router)
router.include_router(planning.router)

__all__ = ["router"]
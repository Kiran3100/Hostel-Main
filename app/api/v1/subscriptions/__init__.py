# --- File: C:\Hostel-Main\app\api\v1\subscriptions\__init__.py ---
"""
Subscription API module initialization.

This module aggregates all subscription-related routers and provides
a unified API interface for subscription management.
"""
from fastapi import APIRouter

from . import billing, invoices, plans, subscriptions, upgrade

# Create main router with common configuration
router = APIRouter(
    responses={
        401: {"description": "Authentication required"},
        403: {"description": "Insufficient permissions"},
        500: {"description": "Internal server error"},
    }
)

# Include all sub-routers
router.include_router(subscriptions.router)
router.include_router(plans.router)
router.include_router(billing.router)
router.include_router(invoices.router)
router.include_router(upgrade.router)

__all__ = ["router"]
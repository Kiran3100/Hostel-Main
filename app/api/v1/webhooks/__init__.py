"""
Webhook API Module

This module provides endpoints for handling webhooks from various external services
including payment gateways and calendar integrations.

Routes:
    - /webhooks/payment: Payment gateway webhooks
    - /webhooks/calendar: Calendar provider webhooks
"""

from fastapi import APIRouter

from . import calendar, payment

# Create main webhook router
router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# Include sub-routers without redundant prefixes (already defined in sub-modules)
router.include_router(payment.router)
router.include_router(calendar.router)

__all__ = ["router"]
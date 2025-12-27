"""
Payment API module for hostel management system.

This module provides comprehensive payment management including:
- Payment CRUD operations
- Online payment initiation
- Webhook handling
- Refund management
- Ledger and accounting
- Payment reminders
- Payment schedules
"""

from fastapi import APIRouter

from .payments import router as payments_router
from .initiate import router as initiate_router
from .webhook import router as webhook_router
from .refunds import router as refunds_router
from .ledger import router as ledger_router
from .reminders import router as reminders_router
from .schedules import router as schedules_router

# Create main router for payments
router = APIRouter(prefix="/payments", tags=["Payments"])

# Include all payment-related sub-routers
router.include_router(payments_router)
router.include_router(initiate_router)
router.include_router(webhook_router)
router.include_router(refunds_router)
router.include_router(ledger_router)
router.include_router(reminders_router)
router.include_router(schedules_router)

__all__ = ["router"]
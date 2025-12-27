"""
Inquiry Management API Module

This module provides comprehensive inquiry management functionality including:
- Core CRUD operations for inquiries
- Follow-up tracking and scheduling
- Status management and workflow
- Assignment and conversion capabilities
- Analytics and reporting
"""

from fastapi import APIRouter

from .inquiries import router as inquiries_router
from .follow_ups import router as follow_ups_router

# Initialize main router for inquiry module
router = APIRouter()

# Include sub-routers
router.include_router(inquiries_router)
router.include_router(follow_ups_router)

__all__ = ["router"]
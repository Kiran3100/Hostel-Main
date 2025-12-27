"""
Student API Module

Aggregates all student-related routers into a single module.
Provides comprehensive student management endpoints including:
- Core student CRUD operations
- Profile and guardian management
- Document management
- Room transfers and swaps
- Dashboard and analytics
- Attendance tracking
- Complaint management
- Leave applications
- Payment history
"""
from fastapi import APIRouter

from . import (
    students,
    profile,
    documents,
    room_transfers,
    dashboard,
    attendance,
    complaints,
    leaves,
    payments,
)

# Create main router for student endpoints
router = APIRouter()

# Include all sub-routers
router.include_router(students.router)
router.include_router(profile.router)
router.include_router(documents.router)
router.include_router(room_transfers.router)
router.include_router(dashboard.router)
router.include_router(attendance.router)
router.include_router(complaints.router)
router.include_router(leaves.router)
router.include_router(payments.router)

__all__ = ["router"]
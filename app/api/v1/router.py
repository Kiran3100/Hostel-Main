# app/api/v1/router.py
from __future__ import annotations

from fastapi import APIRouter

from . import (
    admin,
    analytics,
    announcements,
    attendance,
    audit,
    auth,
    bookings,
    complaints,
    fee_structures,
    files,
    hostels,
    inquiries,
    leaves,
    maintenance,
    mess,
    notifications,
    payments,
    referrals,
    reviews,
    rooms,
    search,
    students,
    supervisors,
    users,
    visitors,
    
)

router = APIRouter()

# Core auth & user management
router.include_router(auth.router)
router.include_router(users.router)

# Domain routers
router.include_router(admin.router)
router.include_router(analytics.router)
router.include_router(announcements.router)
router.include_router(attendance.router)
router.include_router(audit.router)
router.include_router(bookings.router)
router.include_router(complaints.router)
router.include_router(fee_structures.router)
router.include_router(files.router)
router.include_router(hostels.router)
router.include_router(inquiries.router)
router.include_router(leaves.router)
router.include_router(maintenance.router)
router.include_router(mess.router)
router.include_router(notifications.router)
router.include_router(payments.router)
router.include_router(referrals.router)
router.include_router(reviews.router)
router.include_router(rooms.router)
router.include_router(search.router)
router.include_router(students.router)
router.include_router(supervisors.router)
router.include_router(visitors.router)

__all__ = ["router"]
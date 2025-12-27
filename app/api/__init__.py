# D:\Last Github Push\Last\Hostel-Main\app\api\__init__.py

from fastapi import APIRouter

# This is the main API router that should be included in your FastAPI app:
#
#     from app.api import api_router
#     app.include_router(api_router, prefix="/api")
#
api_router = APIRouter()


# As you add per‑module routers (e.g. bookings, complaints, hostels), import them
# here and register them on api_router.
#
# Example (once you have these modules created under app/api/routes/):
#
# from app.api.routes import (
#     auth,
#     users,
#     hostels,
#     rooms,
#     bookings,
#     complaints,
#     attendance,
#     payments,
#     notifications,
#     files,
#     maintenance,
#     mess,
#     leaves,
#     inquiries,
#     visitors,
#     reviews,
#     referrals,
# )
#
# api_router.include_router(auth.router,        prefix="/auth",        tags=["auth"])
# api_router.include_router(users.router,       prefix="/users",       tags=["users"])
# api_router.include_router(hostels.router,     prefix="/hostels",     tags=["hostels"])
# api_router.include_router(rooms.router,       prefix="/rooms",       tags=["rooms"])
# api_router.include_router(bookings.router,    prefix="/bookings",    tags=["bookings"])
# api_router.include_router(complaints.router,  prefix="/complaints",  tags=["complaints"])
# api_router.include_router(attendance.router,  prefix="/attendance",  tags=["attendance"])
# api_router.include_router(payments.router,    prefix="/payments",    tags=["payments"])
# api_router.include_router(notifications.router, prefix="/notifications", tags=["notifications"])
# api_router.include_router(files.router,       prefix="/files",       tags=["files"])
# api_router.include_router(maintenance.router, prefix="/maintenance", tags=["maintenance"])
# api_router.include_router(mess.router,        prefix="/mess",        tags=["mess"])
# api_router.include_router(leaves.router,      prefix="/leaves",      tags=["leaves"])
# api_router.include_router(inquiries.router,   prefix="/inquiries",   tags=["inquiries"])
# api_router.include_router(visitors.router,    prefix="/visitors",    tags=["visitors"])
# api_router.include_router(reviews.router,     prefix="/reviews",     tags=["reviews"])
# api_router.include_router(referrals.router,   prefix="/referrals",   tags=["referrals"])


__all__ = ["api_router"]

# app/api/__init__.py
from fastapi import APIRouter
from app.api.v1.admin import router as admin_router

api_router = APIRouter()
api_router.include_router(admin_router, prefix="/v1/admin")


# app/api/__init__.py
from fastapi import APIRouter
from app.api.v1.analytics import router as analytics_router

api_router = APIRouter()
api_router.include_router(analytics_router, prefix="/v1")

# app/api/__init__.py
from fastapi import APIRouter
from app.api.v1.announcements import router as announcements_router

api_router = APIRouter()
api_router.include_router(announcements_router, prefix="/v1")

# app/api/__init__.py
from fastapi import APIRouter
from app.api.v1.attendance import router as attendance_router

api_router = APIRouter()
api_router.include_router(attendance_router, prefix="/v1")
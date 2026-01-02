# D:\Last Github Push\Last\Hostel-Main\app\api\__init__.py

from fastapi import APIRouter

api_router = APIRouter()


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


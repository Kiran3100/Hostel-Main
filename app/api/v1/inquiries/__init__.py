# api/v1/inquiries/__init__.py
from __future__ import annotations

from fastapi import APIRouter

from . import inquiries
from . import status

router = APIRouter(prefix="/inquiries")

router.include_router(inquiries.router, tags=["Inquiries - Core"])
router.include_router(status.router, tags=["Inquiries - Status & Assignment"])

__all__ = ["router"]
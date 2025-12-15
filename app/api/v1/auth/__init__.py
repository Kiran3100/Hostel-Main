# app/api/v1/auth/__init__.py
from __future__ import annotations

from fastapi import APIRouter

from .login import router as login_router
from .register import router as register_router
from .token import router as token_router
from .password import router as password_router
from .otp import router as otp_router
from .social import router as social_router

router = APIRouter()

# All routes under /auth/*
router.include_router(login_router)
router.include_router(register_router)
router.include_router(token_router)
router.include_router(password_router)
router.include_router(otp_router)
router.include_router(social_router)

__all__ = ["router"]
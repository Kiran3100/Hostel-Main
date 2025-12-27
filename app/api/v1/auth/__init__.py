"""
Authentication API module.

This module aggregates all authentication-related routers including:
- Login/Logout
- Registration and verification
- Password management
- OTP operations
- MFA management
- Social authentication
- Token management
"""

from fastapi import APIRouter

from . import (
    login,
    logout,
    mfa,
    otp,
    password,
    register,
    social,
    token,
)

# Create main authentication router
router = APIRouter()

# Include all sub-routers
router.include_router(login.router)
router.include_router(logout.router)
router.include_router(register.router)
router.include_router(password.router)
router.include_router(otp.router)
router.include_router(mfa.router)
router.include_router(social.router)
router.include_router(token.router)

# Export router
__all__ = ["router"]
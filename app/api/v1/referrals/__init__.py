"""
Referral System API Module

This module aggregates all referral-related API routers including:
- Programs: Referral program management
- Codes: Referral code generation and tracking
- Referrals: Core referral tracking and conversion
- Rewards: Reward distribution and payout management

Usage:
    from app.api.v1.referrals import router
    app.include_router(router, prefix="/api/v1")
"""

from fastapi import APIRouter

from . import programs, codes, referrals, rewards

# Create main referral router
router = APIRouter()

# Include sub-routers with proper ordering
# Order matters for path matching - more specific routes first
router.include_router(codes.router)
router.include_router(programs.router)
router.include_router(referrals.router)
router.include_router(rewards.router)

# Export router for use in main application
__all__ = ["router"]
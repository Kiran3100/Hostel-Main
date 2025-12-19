# --- File: app/repositories/referral/__init__.py ---
"""
Referral Repositories Package.

Provides data access layer for referral management including
programs, codes, referrals, rewards, and analytics.
"""

from app.repositories.referral.referral_repository import ReferralRepository
from app.repositories.referral.referral_code_repository import ReferralCodeRepository
from app.repositories.referral.referral_program_repository import ReferralProgramRepository
from app.repositories.referral.referral_reward_repository import ReferralRewardRepository
from app.repositories.referral.referral_aggregate_repository import ReferralAggregateRepository

__all__ = [
    "ReferralRepository",
    "ReferralCodeRepository",
    "ReferralProgramRepository",
    "ReferralRewardRepository",
    "ReferralAggregateRepository",
]
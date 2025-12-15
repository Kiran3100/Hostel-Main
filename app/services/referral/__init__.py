# app/services/referral/__init__.py
"""
Referral-related services.

- ReferralProgramService:
    Manage referral program definitions.

- ReferralService:
    Handle referral code generation, validation, and individual referral records.

- ReferralRewardService:
    Compute referral rewards and handle payout requests.
"""

from .referral_program_service import ReferralProgramService
from .referral_service import ReferralService
from .referral_reward_service import ReferralRewardService, RewardConfigStore, PayoutStore

__all__ = [
    "ReferralProgramService",
    "ReferralService",
    "ReferralRewardService",
    "RewardConfigStore",
    "PayoutStore",
]
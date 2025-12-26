"""
Referral Services Package

Provides comprehensive services for the referral system:

Services:
    - ReferralProgramService: Program management and analytics
    - ReferralCodeService: Code generation, validation, and tracking
    - ReferralService: Core referral lifecycle and conversions
    - ReferralRewardService: Reward calculation, tracking, and payouts

Features:
    - Comprehensive validation and error handling
    - Structured logging for audit trails
    - Performance optimizations with caching support
    - Idempotent operations where applicable
    - Detailed analytics and reporting

Usage:
    from app.services.referral import (
        ReferralProgramService,
        ReferralCodeService,
        ReferralService,
        ReferralRewardService,
    )
"""

from __future__ import annotations

from .referral_code_service import ReferralCodeService
from .referral_program_service import ReferralProgramService
from .referral_reward_service import ReferralRewardService
from .referral_service import ReferralService

__all__ = [
    "ReferralCodeService",
    "ReferralProgramService",
    "ReferralRewardService",
    "ReferralService",
]

__version__ = "1.0.0"

# Service initialization helpers for dependency injection
def create_referral_services(
    referral_repo,
    referral_code_repo,
    referral_program_repo,
    reward_repo,
    payout_repo,
    tracking_repo,
    aggregate_repo,
):
    """
    Factory function to create all referral services with proper dependencies.
    
    Args:
        referral_repo: ReferralRepository instance
        referral_code_repo: ReferralCodeRepository instance
        referral_program_repo: ReferralProgramRepository instance
        reward_repo: ReferralRewardRepository instance
        payout_repo: RewardPayoutRepository instance
        tracking_repo: RewardTrackingRepository instance
        aggregate_repo: ReferralAggregateRepository instance
    
    Returns:
        dict: Dictionary containing all initialized services
    
    Example:
        services = create_referral_services(
            referral_repo=referral_repo,
            referral_code_repo=code_repo,
            # ... other repos
        )
        
        program_service = services['program']
        code_service = services['code']
        referral_service = services['referral']
        reward_service = services['reward']
    """
    return {
        'program': ReferralProgramService(program_repo=referral_program_repo),
        'code': ReferralCodeService(code_repo=referral_code_repo),
        'referral': ReferralService(
            referral_repo=referral_repo,
            aggregate_repo=aggregate_repo,
        ),
        'reward': ReferralRewardService(
            reward_repo=reward_repo,
            payout_repo=payout_repo,
            tracking_repo=tracking_repo,
            aggregate_repo=aggregate_repo,
        ),
    }
# --- File: app/schemas/referral/__init__.py ---
"""
Referral schemas package.

Provides comprehensive schemas for referral program management including
programs, referrals, codes, rewards, and analytics.
"""

# Program base schemas
from app.schemas.referral.referral_program_base import (
    ProgramCreate,
    ProgramType,
    ProgramUpdate,
    ReferralProgramBase,
    RewardType,
)

# Program response schemas
from app.schemas.referral.referral_program_response import (
    ProgramAnalytics,
    ProgramList,
    ProgramPerformance,
    ProgramResponse,
    ProgramStats,
)

# Referral base schemas
from app.schemas.referral.referral_base import (
    ReferralBase,
    ReferralConversion,
    ReferralCreate,
    ReferralUpdate,
)

# Referral code schemas
from app.schemas.referral.referral_code import (
    CodeValidationRequest,
    CodeValidationResponse,
    ReferralCodeGenerate,
    ReferralCodeResponse,
    ReferralCodeStats,
    ReferralCodeValidationResponse,
)

# Response schemas
from app.schemas.referral.referral_response import (
    LeaderboardEntry,
    ReferralAnalytics,
    ReferralDetail,
    ReferralLeaderboard,
    ReferralResponse,
    ReferralStats,
    ReferralTimeline,
    TimelineEvent,
)

# Reward schemas
from app.schemas.referral.referral_rewards import (
    PayoutHistory,
    PayoutRequest,
    PayoutRequestCreate,
    PayoutRequestResponse,
    RewardCalculation,
    RewardConfig,
    RewardSummary,
    RewardTracking,
)

# List response schemas
from app.schemas.referral.referral_list_responses import (
    ReferralCodeListResponse,
    ReferralProgramListResponse,
    ReferralListResponse,
    PayoutListResponse,
)

# Request schemas
from app.schemas.referral.referral_requests import (
    ReferralConversionRequest,
    ReferralCancellationRequest,
    PayoutProcessRequest,
)

# Transaction schemas
from app.schemas.referral.reward_transaction import (
    RewardTransaction,
    RewardTransactionDetail,
)

# API-compatible aliases for programs
ReferralProgramResponse = ProgramResponse
ReferralProgramCreate = ProgramCreate
ReferralProgramUpdate = ProgramUpdate
ReferralProgramStats = ProgramStats
ReferralProgramAnalytics = ProgramAnalytics

__all__ = [
    # Program Base
    "ReferralProgramBase",
    "ProgramCreate",
    "ProgramUpdate",
    "ProgramType",
    "RewardType",
    # Program Response
    "ProgramResponse",
    "ProgramList",
    "ProgramStats",
    "ProgramAnalytics",
    "ProgramPerformance",
    # Referral Base
    "ReferralBase",
    "ReferralCreate",
    "ReferralUpdate",
    "ReferralConversion",
    # Code
    "ReferralCodeGenerate",
    "ReferralCodeResponse",
    "CodeValidationRequest",
    "CodeValidationResponse",
    "ReferralCodeValidationResponse",
    "ReferralCodeStats",
    # Response
    "ReferralResponse",
    "ReferralDetail",
    "ReferralStats",
    "ReferralLeaderboard",
    "LeaderboardEntry",
    "ReferralTimeline",
    "TimelineEvent",
    "ReferralAnalytics",
    # Rewards
    "RewardConfig",
    "RewardTracking",
    "RewardCalculation",
    "PayoutRequest",
    "PayoutRequestCreate",
    "PayoutRequestResponse",
    "PayoutHistory",
    "RewardSummary",
    # List Responses
    "ReferralCodeListResponse",
    "ReferralProgramListResponse",
    "ReferralListResponse",
    "PayoutListResponse",
    # Request Schemas
    "ReferralConversionRequest",
    "ReferralCancellationRequest",
    "PayoutProcessRequest",
    # Transactions
    "RewardTransaction",
    "RewardTransactionDetail",
    # API Aliases
    "ReferralProgramResponse",
    "ReferralProgramCreate",
    "ReferralProgramUpdate",
    "ReferralProgramStats",
    "ReferralProgramAnalytics",
]
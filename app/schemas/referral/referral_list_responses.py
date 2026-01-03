# --- File: app/schemas/referral/referral_list_responses.py ---
"""
List and pagination response schemas for referral system.

This module provides standardized list responses with pagination
for codes, programs, referrals, and payouts.
"""

from typing import List
from pydantic import Field

from app.schemas.common.base import BaseSchema
from app.schemas.referral.referral_code import ReferralCodeResponse
from app.schemas.referral.referral_program_response import ProgramResponse
from app.schemas.referral.referral_response import ReferralResponse
from app.schemas.referral.referral_rewards import PayoutRequestResponse

__all__ = [
    "ReferralCodeListResponse",
    "ReferralProgramListResponse",
    "ReferralListResponse",
    "PayoutListResponse",
]


class ReferralCodeListResponse(BaseSchema):
    """
    Paginated list response for referral codes.
    
    Provides codes with pagination metadata.
    """
    
    items: List[ReferralCodeResponse] = Field(
        ...,
        description="List of referral codes",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of codes",
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page number",
    )
    page_size: int = Field(
        ...,
        ge=1,
        le=100,
        description="Number of items per page",
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description="Total number of pages",
    )
    has_next: bool = Field(
        ...,
        description="Whether there are more pages",
    )
    has_previous: bool = Field(
        ...,
        description="Whether there are previous pages",
    )


class ReferralProgramListResponse(BaseSchema):
    """
    Paginated list response for referral programs.
    
    Provides programs with pagination metadata and summary statistics.
    """
    
    items: List[ProgramResponse] = Field(
        ...,
        description="List of referral programs",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of programs",
    )
    active_count: int = Field(
        default=0,
        ge=0,
        description="Number of active programs",
    )
    inactive_count: int = Field(
        default=0,
        ge=0,
        description="Number of inactive programs",
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page number",
    )
    page_size: int = Field(
        ...,
        ge=1,
        le=100,
        description="Number of items per page",
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description="Total number of pages",
    )
    has_next: bool = Field(
        ...,
        description="Whether there are more pages",
    )
    has_previous: bool = Field(
        ...,
        description="Whether there are previous pages",
    )


class ReferralListResponse(BaseSchema):
    """
    Paginated list response for referrals.
    
    Provides referrals with pagination metadata and summary statistics.
    """
    
    items: List[ReferralResponse] = Field(
        ...,
        description="List of referrals",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of referrals",
    )
    pending_count: int = Field(
        default=0,
        ge=0,
        description="Number of pending referrals",
    )
    converted_count: int = Field(
        default=0,
        ge=0,
        description="Number of converted referrals",
    )
    cancelled_count: int = Field(
        default=0,
        ge=0,
        description="Number of cancelled referrals",
    )
    total_reward_amount: str = Field(
        default="0.00",
        description="Total reward amount across all referrals",
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page number",
    )
    page_size: int = Field(
        ...,
        ge=1,
        le=100,
        description="Number of items per page",
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description="Total number of pages",
    )
    has_next: bool = Field(
        ...,
        description="Whether there are more pages",
    )
    has_previous: bool = Field(
        ...,
        description="Whether there are previous pages",
    )


class PayoutListResponse(BaseSchema):
    """
    Paginated list response for payout requests.
    
    Provides payout requests with pagination and summary statistics.
    """
    
    items: List[PayoutRequestResponse] = Field(
        ...,
        description="List of payout requests",
    )
    total: int = Field(
        ...,
        ge=0,
        description="Total number of payout requests",
    )
    pending_count: int = Field(
        default=0,
        ge=0,
        description="Number of pending payouts",
    )
    approved_count: int = Field(
        default=0,
        ge=0,
        description="Number of approved payouts",
    )
    completed_count: int = Field(
        default=0,
        ge=0,
        description="Number of completed payouts",
    )
    rejected_count: int = Field(
        default=0,
        ge=0,
        description="Number of rejected payouts",
    )
    total_amount: str = Field(
        default="0.00",
        description="Total payout amount",
    )
    page: int = Field(
        ...,
        ge=1,
        description="Current page number",
    )
    page_size: int = Field(
        ...,
        ge=1,
        le=100,
        description="Number of items per page",
    )
    total_pages: int = Field(
        ...,
        ge=0,
        description="Total number of pages",
    )
    has_next: bool = Field(
        ...,
        description="Whether there are more pages",
    )
    has_previous: bool = Field(
        ...,
        description="Whether there are previous pages",
    )
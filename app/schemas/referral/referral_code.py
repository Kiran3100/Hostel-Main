# --- File: app/schemas/referral/referral_code.py ---
"""
Referral code generation and validation schemas.

This module provides schemas for generating unique referral codes
and validating their usage.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "ReferralCodeGenerate",
    "ReferralCodeResponse",
    "CodeValidationRequest",
    "CodeValidationResponse",
    "ReferralCodeStats",
]


class ReferralCodeGenerate(BaseCreateSchema):
    """
    Schema for generating a referral code for a user.

    Creates a unique, personalized referral code for sharing.
    """

    user_id: UUID = Field(
        ...,
        description="User ID to generate code for",
    )
    program_id: UUID = Field(
        ...,
        description="Referral program ID",
    )

    # Optional customization
    prefix: str = Field(
        default="HOSTEL",
        min_length=3,
        max_length=10,
        pattern="^[A-Z]+$",
        description="Code prefix (uppercase letters only)",
    )
    custom_suffix: Optional[str] = Field(
        None,
        min_length=3,
        max_length=10,
        pattern="^[A-Z0-9]+$",
        description="Optional custom suffix",
    )

    # Validity
    expires_at: Optional[datetime] = Field(
        None,
        description="Code expiration date (optional)",
    )
    max_uses: int = Field(
        default=100,
        ge=1,
        le=1000,
        description="Maximum number of times code can be used",
    )

    @field_validator("prefix")
    @classmethod
    def validate_prefix(cls, v: str) -> str:
        """Validate and normalize prefix."""
        v = v.upper().strip()
        if not v.isalpha():
            raise ValueError("Prefix must contain only letters")
        return v

    @field_validator("expires_at")
    @classmethod
    def validate_expiration(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Validate expiration date is in future."""
        if v is not None and v <= datetime.utcnow():
            raise ValueError("Expiration date must be in the future")
        return v


class ReferralCodeResponse(BaseSchema):
    """
    Response schema for generated referral code.

    Returns the code and associated metadata.
    """

    user_id: UUID = Field(..., description="User ID")
    program_id: UUID = Field(..., description="Program ID")
    referral_code: str = Field(..., description="Generated referral code")
    
    # Code details
    share_url: str = Field(
        ...,
        description="Shareable URL with embedded code",
    )
    qr_code_url: Optional[str] = Field(
        None,
        description="QR code image URL",
    )
    
    # Usage tracking
    times_used: int = Field(
        default=0,
        ge=0,
        description="Number of times code has been used",
    )
    max_uses: int = Field(
        ...,
        ge=1,
        description="Maximum allowed uses",
    )
    remaining_uses: int = Field(
        ...,
        ge=0,
        description="Remaining uses available",
    )
    
    # Validity
    is_active: bool = Field(..., description="Whether code is currently active")
    created_at: datetime = Field(..., description="Code creation time")
    expires_at: Optional[datetime] = Field(None, description="Expiration time")


class CodeValidationRequest(BaseCreateSchema):
    """
    Request schema for validating a referral code.

    Used when a user attempts to use a referral code.
    """

    referral_code: str = Field(
        ...,
        min_length=5,
        max_length=50,
        description="Referral code to validate",
    )
    user_id: Optional[UUID] = Field(
        None,
        description="User ID attempting to use the code",
    )
    context: Optional[str] = Field(
        None,
        max_length=100,
        description="Context where code is being used (e.g., 'booking', 'registration')",
    )

    @field_validator("referral_code")
    @classmethod
    def normalize_code(cls, v: str) -> str:
        """Normalize referral code."""
        return v.upper().strip()


class CodeValidationResponse(BaseSchema):
    """
    Response schema for code validation.

    Indicates whether code is valid and provides relevant details.
    """

    referral_code: str = Field(..., description="Validated code")
    is_valid: bool = Field(..., description="Whether code is valid")
    
    # Program details (if valid)
    program_id: Optional[UUID] = Field(
        None,
        description="Associated program ID",
    )
    program_name: Optional[str] = Field(
        None,
        description="Program name",
    )
    
    # Referrer details (if valid)
    referrer_id: Optional[UUID] = Field(
        None,
        description="Referrer user ID",
    )
    referrer_name: Optional[str] = Field(
        None,
        description="Referrer name",
    )
    
    # Reward information (if valid)
    referee_reward_amount: Optional[str] = Field(
        None,
        description="Reward amount for new user",
    )
    reward_type: Optional[str] = Field(
        None,
        description="Type of reward",
    )
    
    # Validation result
    message: str = Field(
        ...,
        description="Validation message or error reason",
    )
    validation_errors: list[str] = Field(
        default_factory=list,
        description="List of validation errors if invalid",
    )
    
    # Usage information
    times_used: int = Field(default=0, ge=0, description="Times code has been used")
    max_uses: int = Field(default=0, ge=0, description="Maximum allowed uses")
    expires_at: Optional[datetime] = Field(None, description="Expiration date")


class ReferralCodeStats(BaseSchema):
    """
    Statistics for a referral code.

    Provides detailed analytics for code performance.
    """

    referral_code: str = Field(..., description="Referral code")
    user_id: UUID = Field(..., description="Code owner")
    program_id: UUID = Field(..., description="Program ID")
    
    # Usage statistics
    total_shares: int = Field(
        default=0,
        ge=0,
        description="Total times code was shared",
    )
    total_clicks: int = Field(
        default=0,
        ge=0,
        description="Total clicks on referral link",
    )
    total_uses: int = Field(
        default=0,
        ge=0,
        description="Total successful uses",
    )
    
    # Conversion statistics
    total_registrations: int = Field(
        default=0,
        ge=0,
        description="Registrations from this code",
    )
    total_bookings: int = Field(
        default=0,
        ge=0,
        description="Bookings from this code",
    )
    conversion_rate: float = Field(
        default=0.0,
        ge=0,
        le=100,
        description="Click-to-booking conversion rate",
    )
    
    # Rewards earned
    total_rewards_earned: str = Field(
        default="0.00",
        description="Total rewards earned from this code",
    )
    pending_rewards: str = Field(
        default="0.00",
        description="Pending reward amount",
    )
    
    # Time period
    created_at: datetime = Field(..., description="Code creation date")
    last_used_at: Optional[datetime] = Field(None, description="Last usage date")
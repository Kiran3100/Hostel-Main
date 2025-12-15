# --- File: app/schemas/referral/referral_base.py ---
"""
Referral tracking schemas.

This module provides schemas for tracking individual referrals,
their status, and associated rewards.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import EmailStr, Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema
from app.schemas.common.enums import ReferralStatus, RewardStatus

__all__ = [
    "ReferralBase",
    "ReferralCreate",
    "ReferralUpdate",
    "ReferralConversion",
]


class ReferralBase(BaseSchema):
    """
    Base referral record schema.

    Tracks a single referral from one user to another with status
    and reward information.
    """

    # Program and referrer
    program_id: UUID = Field(
        ...,
        description="Referral program ID",
    )
    referrer_id: UUID = Field(
        ...,
        description="User ID of the person making the referral",
    )

    # Referee information (at least one required)
    referee_email: Optional[EmailStr] = Field(
        None,
        description="Email address of referred person",
    )
    referee_phone: Optional[str] = Field(
        None,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Phone number of referred person",
    )
    referee_user_id: Optional[UUID] = Field(
        None,
        description="User ID of referred person (after registration)",
    )
    referee_name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=100,
        description="Name of referred person",
    )

    # Referral code
    referral_code: str = Field(
        ...,
        min_length=5,
        max_length=50,
        pattern="^[A-Z0-9-]+$",
        description="Unique referral code used",
    )

    # Status tracking
    status: ReferralStatus = Field(
        default=ReferralStatus.PENDING,
        description="Current referral status",
    )

    # Conversion tracking
    booking_id: Optional[UUID] = Field(
        None,
        description="Booking ID if referral converted",
    )
    conversion_date: Optional[datetime] = Field(
        None,
        description="When referral converted to booking",
    )

    # Reward tracking
    # Note: Decimal precision handled in field validators for Pydantic v2 compatibility
    referrer_reward_amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Reward amount for referrer",
    )
    referee_reward_amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Reward amount for referee",
    )
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        description="Currency code",
    )

    # Reward status
    referrer_reward_status: RewardStatus = Field(
        default=RewardStatus.PENDING,
        description="Status of referrer's reward",
    )
    referee_reward_status: RewardStatus = Field(
        default=RewardStatus.PENDING,
        description="Status of referee's reward",
    )

    # Source tracking
    referral_source: Optional[str] = Field(
        None,
        max_length=100,
        description="Source of referral (e.g., 'whatsapp', 'email', 'social')",
    )
    campaign_id: Optional[UUID] = Field(
        None,
        description="Marketing campaign ID if applicable",
    )

    # Metadata
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional notes or context",
    )

    @field_validator("referral_code")
    @classmethod
    def validate_referral_code(cls, v: str) -> str:
        """Validate and normalize referral code."""
        v = v.upper().strip()
        if not v:
            raise ValueError("Referral code cannot be empty")
        return v

    @field_validator("referee_phone")
    @classmethod
    def normalize_phone_number(cls, v: Optional[str]) -> Optional[str]:
        """Normalize phone number format."""
        if v is None:
            return None
        
        # Remove spaces, hyphens, parentheses
        normalized = v.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        
        # Add + prefix if missing
        if not normalized.startswith("+"):
            if len(normalized) == 10:
                normalized = f"+91{normalized}"  # Assume India
            else:
                normalized = f"+{normalized}"
        
        return normalized

    @field_validator("referrer_reward_amount", "referee_reward_amount")
    @classmethod
    def validate_decimal_places(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure decimal values have at most 2 decimal places."""
        if v is None:
            return None
        # Quantize to 2 decimal places
        return v.quantize(Decimal("0.01"))

    @model_validator(mode="after")
    def validate_referee_info(self) -> "ReferralBase":
        """Ensure at least one referee identifier is provided."""
        if not any([self.referee_email, self.referee_phone, self.referee_user_id]):
            raise ValueError(
                "At least one referee identifier (email, phone, or user_id) is required"
            )
        return self

    @model_validator(mode="after")
    def validate_conversion_data(self) -> "ReferralBase":
        """Validate conversion-related data consistency."""
        # If status is COMPLETED, booking_id and conversion_date should be set
        if self.status == ReferralStatus.COMPLETED:
            if not self.booking_id:
                raise ValueError(
                    "booking_id required when status is COMPLETED"
                )
            if not self.conversion_date:
                raise ValueError(
                    "conversion_date required when status is COMPLETED"
                )
        
        # If booking_id is set, conversion_date should also be set
        if self.booking_id and not self.conversion_date:
            raise ValueError(
                "conversion_date required when booking_id is provided"
            )
        
        return self


class ReferralCreate(ReferralBase, BaseCreateSchema):
    """
    Schema for creating a new referral record.

    Generated when a user shares a referral code or when a referred
    person uses the code.
    """

    # Override to make some fields optional for creation
    referral_code: Optional[str] = Field(
        None,
        description="Referral code (auto-generated if not provided)",
    )
    
    @model_validator(mode="before")
    @classmethod
    def generate_referral_code(cls, data):
        """Generate referral code if not provided."""
        if isinstance(data, dict) and data.get("referral_code") is None:
            # Generate unique code
            import secrets
            import string
            
            # Get referrer_id for personalization
            referrer_id = data.get("referrer_id")
            if referrer_id:
                # Use last 6 chars of UUID + random string
                user_suffix = str(referrer_id).replace("-", "")[-6:].upper()
            else:
                user_suffix = ""
            
            # Generate random alphanumeric string
            random_part = ''.join(
                secrets.choice(string.ascii_uppercase + string.digits)
                for _ in range(6)
            )
            
            data["referral_code"] = f"REF-{user_suffix}{random_part}"
        
        return data


class ReferralUpdate(BaseSchema):
    """
    Schema for updating a referral record.

    Allows updating status, conversion information, and reward status.
    """

    # Referee information updates
    referee_user_id: Optional[UUID] = Field(
        None,
        description="Update referee user ID after registration",
    )
    referee_name: Optional[str] = Field(
        None,
        min_length=2,
        max_length=100,
        description="Update referee name",
    )

    # Status updates
    status: Optional[ReferralStatus] = Field(
        None,
        description="Update referral status",
    )

    # Conversion updates
    booking_id: Optional[UUID] = Field(
        None,
        description="Link booking to referral",
    )
    conversion_date: Optional[datetime] = Field(
        None,
        description="Set conversion Date",
    )

    # Reward updates
    referrer_reward_status: Optional[RewardStatus] = Field(
        None,
        description="Update referrer reward status",
    )
    referee_reward_status: Optional[RewardStatus] = Field(
        None,
        description="Update referee reward status",
    )

    # Notes
    notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Add or update notes",
    )


class ReferralConversion(BaseCreateSchema):
    """
    Schema for converting a referral to a booking.

    Used when a referred person completes a booking.
    """

    referral_id: UUID = Field(
        ...,
        description="Referral record ID",
    )
    booking_id: UUID = Field(
        ...,
        description="Booking ID",
    )
    booking_amount: Decimal = Field(
        ...,
        ge=0,
        description="Booking amount",
    )
    stay_duration_months: int = Field(
        ...,
        ge=1,
        le=24,
        description="Stay duration in months",
    )
    conversion_date: Optional[datetime] = Field(
        default_factory=datetime.utcnow,
        description="Conversion timestamp",
    )

    @field_validator("booking_amount")
    @classmethod
    def validate_decimal_places(cls, v: Decimal) -> Decimal:
        """Ensure decimal values have at most 2 decimal places."""
        return v.quantize(Decimal("0.01"))

    @model_validator(mode="after")
    def validate_conversion_date(self) -> "ReferralConversion":
        """Ensure conversion Date is not in future."""
        if self.conversion_date > datetime.utcnow():
            raise ValueError("Conversion Date cannot be in the future")
        return self
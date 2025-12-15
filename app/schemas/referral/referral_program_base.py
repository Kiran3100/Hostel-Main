# --- File: app/schemas/referral/referral_program_base.py ---
"""
Referral program definition schemas.

This module provides schemas for creating and managing referral programs
with reward structures, eligibility criteria, and validity periods.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import (
    BaseCreateSchema,
    BaseSchema,
    BaseUpdateSchema,
)

__all__ = [
    "ReferralProgramBase",
    "ProgramCreate",
    "ProgramUpdate",
    "ProgramType",
    "RewardType",
]


class ProgramType(str):
    """Referral program types."""

    STUDENT_REFERRAL = "student_referral"
    VISITOR_REFERRAL = "visitor_referral"
    AFFILIATE = "affiliate"
    CORPORATE = "corporate"


class RewardType(str):
    """Reward types for referral programs."""

    CASH = "cash"
    DISCOUNT = "discount"
    VOUCHER = "voucher"
    FREE_MONTH = "free_month"
    POINTS = "points"


class ReferralProgramBase(BaseSchema):
    """
    Base referral program schema.

    Defines the structure and rules for a referral program including
    reward types, eligibility criteria, and validity periods.
    """

    # Program identification
    program_name: str = Field(
        ...,
        min_length=3,
        max_length=100,
        description="Unique program name",
    )
    program_code: Optional[str] = Field(
        None,
        min_length=3,
        max_length=50,
        pattern="^[A-Z0-9_]+$",
        description="Unique program code (auto-generated if not provided)",
    )
    program_type: str = Field(
        ...,
        pattern="^(student_referral|visitor_referral|affiliate|corporate)$",
        description="Type of referral program",
    )

    # Program description
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Program description and benefits",
    )

    # Reward configuration
    reward_type: str = Field(
        ...,
        pattern="^(cash|discount|voucher|free_month|points)$",
        description="Type of reward offered",
    )
    referrer_reward_amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Reward amount for the referrer",
    )
    referee_reward_amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Reward amount for the referee (new user)",
    )
    currency: str = Field(
        default="INR",
        min_length=3,
        max_length=3,
        pattern="^[A-Z]{3}$",
        description="Currency code (ISO 4217)",
    )

    # Reward caps
    max_referrer_rewards_per_month: Optional[int] = Field(
        None,
        ge=1,
        le=100,
        description="Maximum rewards referrer can earn per month",
    )
    max_total_reward_amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Maximum total reward amount per referrer",
    )

    # Eligibility criteria
    min_booking_amount: Optional[Decimal] = Field(
        None,
        ge=0,
        description="Minimum booking amount to qualify for reward",
    )
    min_stay_months: Optional[int] = Field(
        None,
        ge=1,
        le=24,
        description="Minimum stay duration in months to qualify",
    )
    min_referrer_stay_months: Optional[int] = Field(
        None,
        ge=0,
        le=12,
        description="Minimum months referrer must have stayed",
    )

    # Referral limitations
    max_referrals_per_user: Optional[int] = Field(
        None,
        ge=1,
        le=1000,
        description="Maximum referrals allowed per user",
    )
    allowed_user_roles: List[str] = Field(
        default_factory=lambda: ["student", "alumni"],
        description="User roles eligible to participate",
    )

    # Validity period
    is_active: bool = Field(
        default=True,
        description="Whether program is currently active",
    )
    valid_from: Optional[Date] = Field(
        None,
        description="Program start Date",
    )
    valid_to: Optional[Date] = Field(
        None,
        description="Program end Date",
    )

    # Terms and conditions
    terms_and_conditions: Optional[str] = Field(
        None,
        max_length=5000,
        description="Detailed terms and conditions",
    )
    auto_approve_rewards: bool = Field(
        default=False,
        description="Automatically approve rewards without manual review",
    )

    # Tracking
    track_conversion: bool = Field(
        default=True,
        description="Track conversion metrics",
    )

    @field_validator("program_name")
    @classmethod
    def validate_program_name(cls, v: str) -> str:
        """Validate program name is unique and well-formed."""
        # Remove extra spaces
        v = " ".join(v.split())
        if len(v) < 3:
            raise ValueError("Program name must be at least 3 characters")
        return v

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str) -> str:
        """Validate currency code."""
        v = v.upper()
        # Common currency codes
        valid_currencies = {
            "INR", "USD", "EUR", "GBP", "AED", "SGD", "MYR", "AUD", "CAD"
        }
        if v not in valid_currencies:
            raise ValueError(
                f"Invalid currency code. Supported: {', '.join(valid_currencies)}"
            )
        return v

    @field_validator("allowed_user_roles")
    @classmethod
    def validate_allowed_roles(cls, v: List[str]) -> List[str]:
        """Validate user roles."""
        valid_roles = {"student", "alumni", "visitor", "supervisor", "admin"}
        for role in v:
            if role not in valid_roles:
                raise ValueError(f"Invalid user role: {role}")
        return list(set(v))  # Remove duplicates

    @field_validator("referrer_reward_amount", "referee_reward_amount", "min_booking_amount", "max_total_reward_amount")
    @classmethod
    def validate_decimal_places(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure decimal values have at most 2 decimal places."""
        if v is None:
            return None
        return v.quantize(Decimal("0.01"))

    @model_validator(mode="after")
    def validate_reward_amounts(self) -> "ReferralProgramBase":
        """Validate reward amounts are provided for reward types that need them."""
        if self.reward_type in ["cash", "discount", "voucher"]:
            if self.referrer_reward_amount is None and self.referee_reward_amount is None:
                raise ValueError(
                    f"At least one reward amount required for reward_type '{self.reward_type}'"
                )
            
            # Ensure amounts are reasonable
            if self.referrer_reward_amount and self.referrer_reward_amount > 100000:
                raise ValueError("Referrer reward amount seems unreasonably high")
            
            if self.referee_reward_amount and self.referee_reward_amount > 100000:
                raise ValueError("Referee reward amount seems unreasonably high")
        
        return self

    @model_validator(mode="after")
    def validate_validity_period(self) -> "ReferralProgramBase":
        """Validate validity period dates."""
        if self.valid_from and self.valid_to:
            if self.valid_to <= self.valid_from:
                raise ValueError("valid_to must be after valid_from")
            
            # Check if period is too long (e.g., more than 2 years)
            days_difference = (self.valid_to - self.valid_from).days
            if days_difference > 730:  # 2 years
                raise ValueError("Program validity period cannot exceed 2 years")
        
        return self

    @model_validator(mode="after")
    def validate_eligibility_criteria(self) -> "ReferralProgramBase":
        """Validate eligibility criteria are logical."""
        if self.min_stay_months and self.min_booking_amount:
            # If stay duration is required, booking amount should be reasonable
            monthly_rate = self.min_booking_amount / self.min_stay_months
            if monthly_rate < 1000:  # Minimum monthly rate threshold
                raise ValueError(
                    "Minimum booking amount seems too low for required stay duration"
                )
        
        return self


class ProgramCreate(ReferralProgramBase, BaseCreateSchema):
    """
    Schema for creating a new referral program.

    Inherits all fields from ReferralProgramBase with creation-specific validation.
    """

    @model_validator(mode="before")
    @classmethod
    def generate_program_code(cls, data):
        """Generate program code if not provided."""
        if isinstance(data, dict) and data.get("program_code") is None:
            # Generate from program name
            program_name = data.get("program_name", "")
            code = program_name.upper().replace(" ", "_")[:20]
            
            # Add timestamp suffix for uniqueness
            import time
            timestamp = str(int(time.time()))[-6:]
            data["program_code"] = f"{code}_{timestamp}"
        
        return data


class ProgramUpdate(BaseUpdateSchema):
    """
    Schema for updating an existing referral program.

    Allows partial updates with proper validation.
    """

    program_name: Optional[str] = Field(
        None,
        min_length=3,
        max_length=100,
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
    )
    reward_type: Optional[str] = Field(
        None,
        pattern="^(cash|discount|voucher|free_month|points)$",
    )
    referrer_reward_amount: Optional[Decimal] = Field(
        None,
        ge=0,
    )
    referee_reward_amount: Optional[Decimal] = Field(
        None,
        ge=0,
    )
    min_booking_amount: Optional[Decimal] = Field(
        None,
        ge=0,
    )
    min_stay_months: Optional[int] = Field(
        None,
        ge=1,
        le=24,
    )
    min_referrer_stay_months: Optional[int] = Field(
        None,
        ge=0,
        le=12,
    )
    max_referrals_per_user: Optional[int] = Field(
        None,
        ge=1,
        le=1000,
    )
    max_referrer_rewards_per_month: Optional[int] = Field(
        None,
        ge=1,
        le=100,
    )
    max_total_reward_amount: Optional[Decimal] = Field(
        None,
        ge=0,
    )
    allowed_user_roles: Optional[List[str]] = None
    terms_and_conditions: Optional[str] = Field(
        None,
        max_length=5000,
    )
    is_active: Optional[bool] = None
    valid_from: Optional[Date] = None
    valid_to: Optional[Date] = None
    auto_approve_rewards: Optional[bool] = None
    track_conversion: Optional[bool] = None

    @field_validator("referrer_reward_amount", "referee_reward_amount", "min_booking_amount", "max_total_reward_amount")
    @classmethod
    def validate_decimal_places(cls, v: Optional[Decimal]) -> Optional[Decimal]:
        """Ensure decimal values have at most 2 decimal places."""
        if v is None:
            return None
        return v.quantize(Decimal("0.01"))

    @model_validator(mode="after")
    def validate_at_least_one_field(self) -> "ProgramUpdate":
        """Ensure at least one field is being updated."""
        if not any([
            self.program_name,
            self.description,
            self.reward_type,
            self.referrer_reward_amount is not None,
            self.referee_reward_amount is not None,
            self.min_booking_amount is not None,
            self.min_stay_months,
            self.max_referrals_per_user,
            self.terms_and_conditions,
            self.is_active is not None,
            self.valid_from,
            self.valid_to,
        ]):
            raise ValueError("At least one field must be provided for update")
        return self
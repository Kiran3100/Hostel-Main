# --- File: app/schemas/referral/referral_requests.py ---
"""
Request schemas for referral operations.

This module provides request schemas for referral conversions,
cancellations, and payout processing.
"""

from decimal import Decimal
from typing import Dict, Any, Union
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "ReferralConversionRequest",
    "ReferralCancellationRequest",
    "PayoutProcessRequest",
]


class ReferralConversionRequest(BaseCreateSchema):
    """
    Request schema for converting a referral to a booking.
    
    Used when a referred person completes a qualifying booking.
    """
    
    booking_id: UUID = Field(
        ...,
        description="Unique identifier of the booking",
    )
    conversion_amount: Decimal = Field(
        ...,
        ge=0,
        description="Booking/conversion amount",
    )
    stay_duration_months: Union[int, None] = Field(
        None,
        ge=1,
        le=24,
        description="Stay duration in months (if applicable)",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional conversion metadata",
    )
    
    @field_validator("conversion_amount")
    @classmethod
    def validate_decimal_places(cls, v: Decimal) -> Decimal:
        """Ensure decimal values have at most 2 decimal places."""
        return v.quantize(Decimal("0.01"))


class ReferralCancellationRequest(BaseSchema):
    """
    Request schema for cancelling a referral.
    
    Used when a referral needs to be cancelled due to fraud,
    policy violation, or other reasons.
    """
    
    reason: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        description="Detailed reason for cancellation",
    )
    reverse_rewards: bool = Field(
        default=True,
        description="Whether to reverse any rewards already distributed",
    )
    notify_users: bool = Field(
        default=True,
        description="Whether to send notification to affected users",
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional cancellation metadata",
    )
    
    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate cancellation reason."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Cancellation reason must be at least 10 characters")
        return v


class PayoutProcessRequest(BaseSchema):
    """
    Request schema for processing a payout request (admin action).
    
    Used by admins to approve, reject, or complete payout requests.
    """
    
    action: str = Field(
        ...,
        pattern="^(approve|reject|complete)$",
        description="Action to perform on the payout request",
    )
    reason: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Reason for approval/rejection (required for rejection)",
    )
    payment_reference: Union[str, None] = Field(
        None,
        min_length=1,
        max_length=200,
        description="External payment reference/transaction ID (required for completion)",
    )
    notes: Union[str, None] = Field(
        None,
        max_length=2000,
        description="Additional admin notes",
    )
    
    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        """Validate and normalize action."""
        return v.lower()
    
    @field_validator("reason")
    @classmethod
    def validate_reason_not_empty(cls, v: Union[str, None]) -> Union[str, None]:
        """Ensure reason is not just whitespace."""
        if v is not None:
            v = v.strip()
            if not v:
                return None
        return v
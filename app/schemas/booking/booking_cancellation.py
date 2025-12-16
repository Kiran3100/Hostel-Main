"""
Booking cancellation schemas.

This module defines schemas for cancelling bookings, calculating refunds,
and managing cancellation policies.
"""

from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Union
from uuid import UUID

from pydantic import Field, field_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "CancellationRequest",
    "CancellationResponse",
    "RefundCalculation",
    "CancellationPolicy",
    "CancellationCharge",
    "BulkCancellation",
]


class CancellationRequest(BaseCreateSchema):
    """
    Request to cancel a booking.
    
    Contains cancellation details including who is cancelling,
    reason, and refund preferences.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking ID to cancel",
    )
    cancelled_by_role: str = Field(
        ...,
        pattern=r"^(visitor|admin|system)$",
        description="Role of person/system cancelling: visitor, admin, or system",
    )

    cancellation_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Detailed reason for cancellation",
    )

    # Refund Preference
    request_refund: bool = Field(
        True,
        description="Whether to request refund of advance payment",
    )

    # Additional Details
    additional_comments: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Additional comments or context",
    )

    @field_validator("cancellation_reason")
    @classmethod
    def validate_cancellation_reason(cls, v: str) -> str:
        """Validate cancellation reason is meaningful."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError(
                "Cancellation reason must be at least 10 characters"
            )
        return v

    @field_validator("cancelled_by_role")
    @classmethod
    def normalize_role(cls, v: str) -> str:
        """Normalize role value."""
        return v.lower()

    @field_validator("additional_comments")
    @classmethod
    def clean_comments(cls, v: Union[str, None]) -> Union[str, None]:
        """Clean additional comments."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class RefundCalculation(BaseSchema):
    """
    Refund calculation details.
    
    Provides transparent breakdown of refund amount calculation
    based on cancellation policy.
    """

    # Note: decimal_places removed - precision maintained via Decimal quantization
    advance_paid: Decimal = Field(
        ...,
        ge=0,
        description="Total advance amount paid (precision: 2 decimal places)",
    )
    cancellation_charge: Decimal = Field(
        ...,
        ge=0,
        description="Cancellation charge amount (precision: 2 decimal places)",
    )
    cancellation_charge_percentage: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Cancellation charge as percentage of advance (precision: 2 decimal places)",
    )

    refundable_amount: Decimal = Field(
        ...,
        ge=0,
        description="Final amount to be refunded (precision: 2 decimal places)",
    )
    refund_processing_time_days: int = Field(
        ...,
        ge=0,
        description="Expected number of days to process refund",
    )

    # Refund Method
    refund_method: str = Field(
        ...,
        description="Method of refund (bank transfer, original payment method, etc.)",
    )

    # Detailed Breakdown
    breakdown: Dict = Field(
        ...,
        description="Detailed refund calculation breakdown",
    )

    @field_validator("advance_paid", "cancellation_charge", "cancellation_charge_percentage", "refundable_amount")
    @classmethod
    def quantize_decimal_fields(cls, v: Decimal) -> Decimal:
        """Quantize decimal fields to 2 decimal places."""
        return v.quantize(Decimal("0.01"))

    @field_validator("refundable_amount")
    @classmethod
    def validate_refundable_amount(cls, v: Decimal, info) -> Decimal:
        """Validate refundable amount calculation."""
        advance_paid = info.data.get("advance_paid")
        cancellation_charge = info.data.get("cancellation_charge")
        
        if advance_paid is not None and cancellation_charge is not None:
            expected = advance_paid - cancellation_charge
            if expected < 0:
                expected = Decimal("0.00")
            
            # Allow small floating point differences
            if abs(v - expected) > Decimal("0.01"):
                raise ValueError(
                    f"Refundable amount (₹{v}) does not match calculation "
                    f"(₹{expected} = ₹{advance_paid} - ₹{cancellation_charge})"
                )
        
        return v


class CancellationResponse(BaseSchema):
    """
    Response after cancellation request.
    
    Confirms cancellation and provides refund details.
    """

    booking_id: UUID = Field(
        ...,
        description="Cancelled booking ID",
    )
    booking_reference: str = Field(
        ...,
        description="Booking reference number",
    )

    cancelled: bool = Field(
        ...,
        description="Whether cancellation was successful",
    )
    cancelled_at: datetime = Field(
        ...,
        description="Cancellation timestamp",
    )

    # Refund Information
    refund: RefundCalculation = Field(
        ...,
        description="Refund calculation details",
    )

    message: str = Field(
        ...,
        description="Cancellation confirmation message",
    )
    confirmation_sent: bool = Field(
        ...,
        description="Whether confirmation email/SMS was sent",
    )


class CancellationCharge(BaseSchema):
    """
    Cancellation charge tier based on timing.
    
    Defines cancellation charges based on how many days
    before check-in the cancellation occurs.
    """

    days_before_checkin: int = Field(
        ...,
        ge=0,
        description="Minimum days before check-in for this tier",
    )
    charge_percentage: Decimal = Field(
        ...,
        ge=0,
        le=100,
        description="Percentage of advance to charge as cancellation fee (precision: 2 decimal places)",
    )

    description: str = Field(
        ...,
        description="Human-readable description of this tier",
    )

    @field_validator("charge_percentage")
    @classmethod
    def quantize_decimal_field(cls, v: Decimal) -> Decimal:
        """Quantize decimal field to 2 decimal places."""
        return v.quantize(Decimal("0.01"))


class CancellationPolicy(BaseSchema):
    """
    Hostel cancellation policy configuration.
    
    Defines cancellation charges and refund policies for a hostel.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )

    # Tiered Cancellation Charges
    cancellation_before_days: List[CancellationCharge] = Field(
        ...,
        description="List of cancellation charge tiers based on timing",
    )

    # Special Conditions
    no_show_charge_percentage: Decimal = Field(
        Decimal("100.00"),
        ge=0,
        le=100,
        description="Charge if guest doesn't show up (typically 100%, precision: 2 decimal places)",
    )

    # Processing
    refund_processing_days: int = Field(
        7,
        ge=1,
        le=30,
        description="Number of business days to process refund",
    )

    # Policy Documentation
    policy_text: str = Field(
        ...,
        description="Full cancellation policy text for display to users",
    )

    @field_validator("no_show_charge_percentage")
    @classmethod
    def quantize_decimal_field(cls, v: Decimal) -> Decimal:
        """Quantize decimal field to 2 decimal places."""
        return v.quantize(Decimal("0.01"))

    @field_validator("cancellation_before_days")
    @classmethod
    def validate_cancellation_tiers(
        cls,
        v: List[CancellationCharge],
    ) -> List[CancellationCharge]:
        """Validate cancellation charge tiers are properly ordered."""
        if not v:
            raise ValueError("At least one cancellation tier is required")
        
        # Sort by days_before_checkin descending
        sorted_tiers = sorted(v, key=lambda x: x.days_before_checkin, reverse=True)
        
        # Validate charges increase as check-in approaches
        for i in range(len(sorted_tiers) - 1):
            current = sorted_tiers[i]
            next_tier = sorted_tiers[i + 1]
            
            if current.charge_percentage > next_tier.charge_percentage:
                raise ValueError(
                    f"Cancellation charges must increase as check-in approaches. "
                    f"Tier at {current.days_before_checkin} days ({current.charge_percentage}%) "
                    f"has higher charge than tier at {next_tier.days_before_checkin} days "
                    f"({next_tier.charge_percentage}%)"
                )
        
        return sorted_tiers


class BulkCancellation(BaseCreateSchema):
    """
    Cancel multiple bookings in one operation.
    
    Used for batch cancellation (e.g., event cancellation,
    hostel closure, etc.).
    """

    booking_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=100,
        description="List of booking IDs to cancel (max 100)",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Common cancellation reason for all bookings",
    )
    process_refunds: bool = Field(
        True,
        description="Whether to process refunds for all cancellations",
    )

    @field_validator("booking_ids")
    @classmethod
    def validate_booking_ids(cls, v: List[UUID]) -> List[UUID]:
        """Validate booking IDs list."""
        if len(v) == 0:
            raise ValueError("At least one booking ID is required")
        
        if len(v) > 100:
            raise ValueError("Maximum 100 bookings can be cancelled at once")
        
        # Remove duplicates
        unique_ids = list(dict.fromkeys(v))
        
        return unique_ids

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate cancellation reason."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Cancellation reason must be at least 10 characters")
        return v
"""
Booking modification schemas.

This module defines schemas for modifying existing bookings including
Date changes, duration changes, and room type changes.
"""

from datetime import date as Date
from decimal import Decimal
from typing import List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import RoomType

__all__ = [
    "ModificationRequest",
    "ModificationResponse",
    "DateChangeRequest",
    "DurationChangeRequest",
    "RoomTypeChangeRequest",
    "ModificationApproval",
]


class ModificationRequest(BaseCreateSchema):
    """
    General booking modification request.
    
    Allows modification of multiple aspects of a booking
    in a single request.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking ID to modify",
    )

    # Check-in Date Modification
    modify_check_in_date: bool = Field(
        False,
        description="Whether to modify check-in Date",
    )
    new_check_in_date: Union[Date, None] = Field(
        None,
        description="New check-in Date if modifying",
    )

    # Duration Modification
    modify_duration: bool = Field(
        False,
        description="Whether to modify stay duration",
    )
    new_duration_months: Union[int, None] = Field(
        None,
        ge=1,
        le=24,
        description="New duration in months if modifying",
    )

    # Room Type Modification
    modify_room_type: bool = Field(
        False,
        description="Whether to modify room type",
    )
    new_room_type: Union[RoomType, None] = Field(
        None,
        description="New room type if modifying",
    )

    # Justification
    modification_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for modification request",
    )

    # Acknowledgment
    accept_price_change: bool = Field(
        False,
        description="Acknowledge and accept if modification results in price change",
    )

    @model_validator(mode="after")
    def validate_at_least_one_modification(self) -> "ModificationRequest":
        """Ensure at least one modification is requested."""
        if not (
            self.modify_check_in_date
            or self.modify_duration
            or self.modify_room_type
        ):
            raise ValueError(
                "At least one modification type must be selected "
                "(check-in Date, duration, or room type)"
            )
        return self

    @model_validator(mode="after")
    def validate_modification_values(self) -> "ModificationRequest":
        """Validate that required values are provided for selected modifications."""
        if self.modify_check_in_date and self.new_check_in_date is None:
            raise ValueError(
                "new_check_in_date is required when modify_check_in_date is True"
            )
        
        if self.modify_duration and self.new_duration_months is None:
            raise ValueError(
                "new_duration_months is required when modify_duration is True"
            )
        
        if self.modify_room_type and self.new_room_type is None:
            raise ValueError(
                "new_room_type is required when modify_room_type is True"
            )
        
        return self

    @field_validator("new_check_in_date")
    @classmethod
    def validate_new_check_in_date(cls, v: Union[Date, None]) -> Union[Date, None]:
        """Validate new check-in Date."""
        if v is not None and v < Date.today():
            raise ValueError(
                f"New check-in Date ({v}) cannot be in the past"
            )
        return v

    @field_validator("modification_reason")
    @classmethod
    def validate_modification_reason(cls, v: str) -> str:
        """Validate modification reason."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError(
                "Modification reason must be at least 10 characters"
            )
        return v


class ModificationResponse(BaseSchema):
    """
    Response to modification request.
    
    Provides details about what was changed and pricing impact.
    """

    booking_id: UUID = Field(
        ...,
        description="Modified booking ID",
    )
    booking_reference: str = Field(
        ...,
        description="Booking reference",
    )

    # Modifications Applied
    modifications_applied: List[str] = Field(
        ...,
        description="List of modifications that were applied",
    )

    # Pricing Impact - decimal_places removed
    original_total: Decimal = Field(
        ...,
        ge=0,
        description="Original total amount (precision: 2 decimal places)",
    )
    new_total: Decimal = Field(
        ...,
        ge=0,
        description="New total amount after modifications (precision: 2 decimal places)",
    )
    price_difference: Decimal = Field(
        ...,
        description="Price difference (positive = increase, negative = decrease, precision: 2 decimal places)",
    )
    additional_payment_required: bool = Field(
        ...,
        description="Whether additional payment is required",
    )
    additional_amount: Decimal = Field(
        ...,
        ge=0,
        description="Additional amount to be paid if increased (precision: 2 decimal places)",
    )

    # Approval Status
    requires_admin_approval: bool = Field(
        ...,
        description="Whether modification requires admin approval",
    )
    auto_approved: bool = Field(
        ...,
        description="Whether modification was automatically approved",
    )

    message: str = Field(
        ...,
        description="Result message",
    )

    @field_validator("original_total", "new_total", "price_difference", "additional_amount")
    @classmethod
    def quantize_decimal_fields(cls, v: Decimal) -> Decimal:
        """Quantize decimal fields to 2 decimal places."""
        return v.quantize(Decimal("0.01"))


class DateChangeRequest(BaseCreateSchema):
    """
    Specific request to change check-in Date.
    
    Simplified schema for Date-only modifications.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking ID",
    )
    new_check_in_date: Date = Field(
        ...,
        description="New desired check-in Date",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for Date change",
    )

    @field_validator("new_check_in_date")
    @classmethod
    def validate_new_date(cls, v: Date) -> Date:
        """Validate new check-in Date."""
        if v < Date.today():
            raise ValueError(
                f"New check-in Date ({v.strftime('%Y-%m-%d')}) cannot be in the past"
            )
        return v

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate reason."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Reason must be at least 10 characters")
        return v


class DurationChangeRequest(BaseCreateSchema):
    """
    Specific request to change stay duration.
    
    Simplified schema for duration-only modifications.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking ID",
    )
    new_duration_months: int = Field(
        ...,
        ge=1,
        le=24,
        description="New stay duration in months (1-24)",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for duration change",
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate reason."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Reason must be at least 10 characters")
        return v


class RoomTypeChangeRequest(BaseCreateSchema):
    """
    Specific request to change room type.
    
    Simplified schema for room type-only modifications.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking ID",
    )
    new_room_type: RoomType = Field(
        ...,
        description="New desired room type",
    )
    reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Reason for room type change",
    )
    accept_price_difference: bool = Field(
        False,
        description="Accept price difference if room type has different pricing",
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate reason."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Reason must be at least 10 characters")
        return v


class ModificationApproval(BaseCreateSchema):
    """
    Admin approval/rejection of modification request.
    
    Used when modification requires manual admin review.
    """

    modification_request_id: UUID = Field(
        ...,
        description="Modification request ID",
    )
    approved: bool = Field(
        ...,
        description="Whether to approve (True) or reject (False) the modification",
    )

    # If Approved - decimal_places removed
    adjusted_price: Union[Decimal, None] = Field(
        None,
        ge=0,
        description="Adjusted price if admin wants to override calculated price (precision: 2 decimal places)",
    )

    # If Rejected
    rejection_reason: Union[str, None] = Field(
        None,
        max_length=500,
        description="Reason for rejection if not approved",
    )

    # Admin Notes
    admin_notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Internal admin notes about the decision",
    )

    @field_validator("adjusted_price")
    @classmethod
    def quantize_decimal_field(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Quantize decimal field to 2 decimal places."""
        if v is not None:
            return v.quantize(Decimal("0.01"))
        return v

    @model_validator(mode="after")
    def validate_approval_fields(self) -> "ModificationApproval":
        """Validate approval-specific fields."""
        if not self.approved and not self.rejection_reason:
            raise ValueError(
                "rejection_reason is required when modification is rejected"
            )
        
        return self

    @field_validator("rejection_reason")
    @classmethod
    def validate_rejection_reason(cls, v: Union[str, None]) -> Union[str, None]:
        """Validate rejection reason if provided."""
        if v is not None:
            v = v.strip()
            if len(v) < 10:
                raise ValueError(
                    "Rejection reason must be at least 10 characters if provided"
                )
        return v
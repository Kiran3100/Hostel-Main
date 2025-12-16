"""
Booking approval schemas for admin approval workflow.

This module defines schemas for approving, rejecting, and managing
booking approval workflows including bulk operations and settings.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import Dict, List, Union
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "BookingApprovalRequest",
    "ApprovalResponse",
    "RejectionRequest",
    "BulkApprovalRequest",
    "ApprovalSettings",
]


class BookingApprovalRequest(BaseCreateSchema):
    """
    Request to approve a pending booking.
    
    Contains all information needed to approve a booking including
    room assignment, pricing confirmation, and payment requirements.
    """

    booking_id: UUID = Field(
        ...,
        description="Unique identifier of the booking to approve",
    )

    # Room Assignment
    room_id: UUID = Field(
        ...,
        description="ID of the room to assign to this booking",
    )
    bed_id: UUID = Field(
        ...,
        description="ID of the specific bed to assign",
    )

    # Date Confirmation/Adjustment
    approved_check_in_date: Date = Field(
        ...,
        description="Confirmed or adjusted check-in Date",
    )

    # Pricing Confirmation/Adjustment
    # Note: decimal_places removed - Pydantic v2 doesn't support this constraint
    # Precision is maintained through Decimal type and validation
    final_rent_monthly: Decimal = Field(
        ...,
        ge=0,
        description="Final confirmed monthly rent amount (precision: 2 decimal places)",
    )
    final_security_deposit: Decimal = Field(
        ...,
        ge=0,
        description="Final confirmed security deposit amount (precision: 2 decimal places)",
    )

    # Additional Charges
    processing_fee: Decimal = Field(
        Decimal("0.00"),
        ge=0,
        description="One-time processing or booking fee (precision: 2 decimal places)",
    )

    # Notes and Communication
    admin_notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Internal notes visible only to admins",
    )
    message_to_guest: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Message to be sent to guest with approval",
    )

    # Payment Requirements
    advance_payment_required: bool = Field(
        True,
        description="Whether advance payment is required before check-in",
    )
    advance_payment_percentage: Decimal = Field(
        Decimal("20.00"),
        ge=0,
        le=100,
        description="Percentage of total amount required as advance (0-100, precision: 2 decimal places)",
    )

    @field_validator("approved_check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: Date) -> Date:
        """Validate approved check-in Date is not in the past."""
        if v < Date.today():
            raise ValueError(
                f"Approved check-in Date ({v.strftime('%Y-%m-%d')}) "
                "cannot be in the past"
            )
        return v

    @field_validator("final_rent_monthly")
    @classmethod
    def validate_rent_amount(cls, v: Decimal) -> Decimal:
        """Validate rent amount is reasonable and quantize to 2 decimal places."""
        # Quantize to 2 decimal places (replaces decimal_places constraint)
        v = v.quantize(Decimal("0.01"))
        
        if v <= 0:
            raise ValueError("Monthly rent must be greater than zero")
        
        # Sanity check
        min_rent = Decimal("500.00")
        max_rent = Decimal("100000.00")
        
        if v < min_rent:
            raise ValueError(f"Monthly rent (₹{v}) is below minimum (₹{min_rent})")
        if v > max_rent:
            raise ValueError(f"Monthly rent (₹{v}) exceeds maximum (₹{max_rent})")
        
        return v

    @field_validator("final_security_deposit", "processing_fee", "advance_payment_percentage")
    @classmethod
    def quantize_decimal_fields(cls, v: Decimal) -> Decimal:
        """Quantize decimal fields to 2 decimal places."""
        return v.quantize(Decimal("0.01"))

    @model_validator(mode="after")
    def validate_advance_payment(self) -> "BookingApprovalRequest":
        """Validate advance payment settings."""
        if self.advance_payment_required:
            if self.advance_payment_percentage <= 0:
                raise ValueError(
                    "Advance payment percentage must be greater than 0 when required"
                )
            if self.advance_payment_percentage > 100:
                raise ValueError(
                    "Advance payment percentage cannot exceed 100"
                )
        
        return self

    @field_validator("admin_notes", "message_to_guest")
    @classmethod
    def clean_text_fields(cls, v: Union[str, None]) -> Union[str, None]:
        """Clean optional text fields."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class ApprovalResponse(BaseSchema):
    """
    Response after booking approval.
    
    Contains approval confirmation and next steps for guest.
    """

    booking_id: UUID = Field(
        ...,
        description="Approved booking ID",
    )
    booking_reference: str = Field(
        ...,
        description="Booking reference number",
    )

    status: str = Field(
        "approved",
        description="New booking status after approval",
    )

    # Assignment Details
    room_number: str = Field(
        ...,
        description="Assigned room number",
    )
    bed_number: str = Field(
        ...,
        description="Assigned bed number",
    )

    # Financial Details
    monthly_rent: Decimal = Field(
        ...,
        ge=0,
        description="Confirmed monthly rent (precision: 2 decimal places)",
    )
    security_deposit: Decimal = Field(
        ...,
        ge=0,
        description="Security deposit amount (precision: 2 decimal places)",
    )
    advance_amount: Decimal = Field(
        ...,
        ge=0,
        description="Advance payment amount required (precision: 2 decimal places)",
    )
    total_amount: Decimal = Field(
        ...,
        ge=0,
        description="Total booking amount (precision: 2 decimal places)",
    )

    # Dates
    approved_at: datetime = Field(
        ...,
        description="Approval timestamp",
    )
    check_in_date: Date = Field(
        ...,
        description="Confirmed check-in Date",
    )

    # Next Steps
    payment_pending: bool = Field(
        ...,
        description="Whether payment is still pending",
    )
    payment_deadline: Union[datetime, None] = Field(
        None,
        description="Deadline for advance payment",
    )

    message: str = Field(
        ...,
        description="Confirmation message for guest",
    )

    @field_validator("monthly_rent", "security_deposit", "advance_amount", "total_amount")
    @classmethod
    def quantize_decimal_fields(cls, v: Decimal) -> Decimal:
        """Quantize decimal fields to 2 decimal places."""
        return v.quantize(Decimal("0.01"))


class RejectionRequest(BaseCreateSchema):
    """
    Request to reject a booking.
    
    Contains rejection reason and optional alternative suggestions.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking ID to reject",
    )
    rejection_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Detailed reason for rejection",
    )

    # Alternative Suggestions
    suggest_alternative_dates: bool = Field(
        False,
        description="Whether to suggest alternative check-in dates",
    )
    alternative_check_in_dates: Union[List[Date], None] = Field(
        None,
        max_length=3,
        description="Up to 3 alternative check-in dates",
    )

    suggest_alternative_room_types: bool = Field(
        False,
        description="Whether to suggest alternative room types",
    )
    alternative_room_types: Union[List[str], None] = Field(
        None,
        max_length=3,
        description="Alternative room types available",
    )

    # Communication
    message_to_guest: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Personalized message to guest explaining rejection",
    )

    @field_validator("rejection_reason")
    @classmethod
    def validate_rejection_reason(cls, v: str) -> str:
        """Validate rejection reason is meaningful."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError(
                "Rejection reason must be at least 10 characters to be meaningful"
            )
        return v

    @model_validator(mode="after")
    def validate_alternative_dates(self) -> "RejectionRequest":
        """Validate alternative dates if provided."""
        if self.suggest_alternative_dates:
            if not self.alternative_check_in_dates:
                raise ValueError(
                    "Alternative check-in dates must be provided when "
                    "suggest_alternative_dates is True"
                )
            
            # Validate all dates are in future
            for alt_date in self.alternative_check_in_dates:
                if alt_date < Date.today():
                    raise ValueError(
                        f"Alternative Date {alt_date} cannot be in the past"
                    )
        
        return self

    @model_validator(mode="after")
    def validate_alternative_room_types(self) -> "RejectionRequest":
        """Validate alternative room types if provided."""
        if self.suggest_alternative_room_types:
            if not self.alternative_room_types:
                raise ValueError(
                    "Alternative room types must be provided when "
                    "suggest_alternative_room_types is True"
                )
        
        return self


class BulkApprovalRequest(BaseCreateSchema):
    """
    Approve multiple bookings in one operation.
    
    Used for batch processing of pending bookings.
    """

    booking_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of booking IDs to approve (max 50)",
    )

    # Common Settings
    auto_assign_rooms: bool = Field(
        True,
        description="Automatically assign available rooms based on preferences",
    )
    send_notifications: bool = Field(
        True,
        description="Send approval notifications to all guests",
    )

    # Common admin note for all approvals
    admin_notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Common admin notes for all approvals",
    )

    @field_validator("booking_ids")
    @classmethod
    def validate_booking_ids(cls, v: List[UUID]) -> List[UUID]:
        """Validate booking IDs list."""
        if len(v) == 0:
            raise ValueError("At least one booking ID is required")
        
        if len(v) > 50:
            raise ValueError("Maximum 50 bookings can be approved at once")
        
        # Remove duplicates while preserving order
        seen = set()
        unique_ids = []
        for booking_id in v:
            if booking_id not in seen:
                seen.add(booking_id)
                unique_ids.append(booking_id)
        
        return unique_ids


class ApprovalSettings(BaseSchema):
    """
    Hostel-specific booking approval settings.
    
    Configures auto-approval rules and policies for a hostel.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )

    # Auto-Approval
    auto_approve_enabled: bool = Field(
        False,
        description="Enable automatic approval of bookings",
    )
    auto_approve_conditions: Dict = Field(
        default_factory=dict,
        description="Conditions that must be met for auto-approval (JSON)",
    )

    # Timing
    approval_expiry_hours: int = Field(
        48,
        ge=1,
        le=168,
        description="Hours to respond to booking before it expires (1-168)",
    )

    # Payment Settings
    require_advance_payment: bool = Field(
        True,
        description="Require advance payment after approval",
    )
    advance_payment_percentage: Decimal = Field(
        Decimal("20.00"),
        ge=0,
        le=100,
        description="Default advance payment percentage (0-100, precision: 2 decimal places)",
    )

    @field_validator("approval_expiry_hours")
    @classmethod
    def validate_expiry_hours(cls, v: int) -> int:
        """Validate approval expiry hours."""
        if v < 1:
            raise ValueError("Approval expiry must be at least 1 hour")
        if v > 168:  # 1 week
            raise ValueError("Approval expiry cannot exceed 168 hours (1 week)")
        return v

    @field_validator("auto_approve_conditions")
    @classmethod
    def validate_auto_approve_conditions(cls, v: Dict) -> Dict:
        """Validate auto-approve conditions structure."""
        # Could add validation for expected keys/structure
        # For now, just ensure it's a dict
        if not isinstance(v, dict):
            raise ValueError("Auto-approve conditions must be a dictionary")
        return v

    @field_validator("advance_payment_percentage")
    @classmethod
    def quantize_decimal_field(cls, v: Decimal) -> Decimal:
        """Quantize decimal field to 2 decimal places."""
        return v.quantize(Decimal("0.01"))
# --- File: app/schemas/booking/booking_conversion.py ---
"""
Booking to student conversion schemas.

This module defines schemas for converting confirmed bookings
into active student profiles after check-in.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from decimal import Decimal
from typing import List, Optional
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema

__all__ = [
    "ConvertToStudentRequest",
    "ConversionResponse",
    "ConversionChecklist",
    "ChecklistItem",
    "BulkConversion",
    "ConversionRollback",
]


class ConvertToStudentRequest(BaseCreateSchema):
    """
    Request to convert confirmed booking to student profile.
    
    Used after guest checks in to convert booking into
    active student residence.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking ID to convert",
    )

    # Check-in Confirmation
    actual_check_in_date: Date = Field(
        ...,
        description="Actual check-in Date (may differ from preferred)",
    )

    # Financial Confirmation
    security_deposit_paid: bool = Field(
        ...,
        description="Confirm security deposit has been paid",
    )
    first_month_rent_paid: bool = Field(
        ...,
        description="Confirm first month's rent has been paid",
    )

    # Additional Student Details (if not already in booking)
    student_id_number: Optional[str] = Field(
        None,
        max_length=50,
        description="Student ID or enrollment number",
    )
    guardian_address: Optional[str] = Field(
        None,
        max_length=500,
        description="Guardian's address",
    )

    # Document Verification
    id_proof_uploaded: bool = Field(
        False,
        description="ID proof document has been uploaded",
    )
    photo_uploaded: bool = Field(
        False,
        description="Student photo has been uploaded",
    )

    # Notes
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Conversion notes for internal reference",
    )

    @field_validator("actual_check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: Date) -> Date:
        """Validate check-in Date is not in the future."""
        if v > Date.today():
            raise ValueError(
                f"Actual check-in Date ({v.strftime('%Y-%m-%d')}) "
                "cannot be in the future"
            )
        
        # Warn if check-in is too far in the past (> 30 days)
        days_ago = (Date.today() - v).days
        if days_ago > 30:
            # Log warning - might be data entry error
            pass
        
        return v

    @model_validator(mode="after")
    def validate_payments(self) -> "ConvertToStudentRequest":
        """Validate required payments are confirmed."""
        if not self.security_deposit_paid:
            raise ValueError(
                "Security deposit must be paid before conversion to student"
            )
        
        if not self.first_month_rent_paid:
            raise ValueError(
                "First month's rent must be paid before conversion to student"
            )
        
        return self

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, v: Optional[str]) -> Optional[str]:
        """Clean notes field."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class ConversionResponse(BaseSchema):
    """
    Response after successful conversion to student.
    
    Provides confirmation and next steps for student onboarding.
    """

    booking_id: UUID = Field(
        ...,
        description="Original booking ID",
    )
    student_profile_id: UUID = Field(
        ...,
        description="Newly created student profile ID",
    )

    converted: bool = Field(
        ...,
        description="Whether conversion was successful",
    )
    conversion_date: Date = Field(
        ...,
        description="Date of conversion",
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

    # Financial Setup - decimal_places removed
    monthly_rent: Decimal = Field(
        ...,
        ge=0,
        description="Monthly rent amount (precision: 2 decimal places)",
    )
    security_deposit: Decimal = Field(
        ...,
        ge=0,
        description="Security deposit amount (precision: 2 decimal places)",
    )
    next_payment_due_date: Date = Field(
        ...,
        description="Next rent payment due Date",
    )

    message: str = Field(
        ...,
        description="Conversion confirmation message",
    )
    next_steps: List[str] = Field(
        ...,
        description="List of next steps for student/admin",
    )

    @field_validator("monthly_rent", "security_deposit")
    @classmethod
    def quantize_decimal_fields(cls, v: Decimal) -> Decimal:
        """Quantize decimal fields to 2 decimal places."""
        return v.quantize(Decimal("0.01"))


class ChecklistItem(BaseSchema):
    """
    Individual checklist item for conversion validation.
    
    Represents a single requirement that must be met
    before conversion can proceed.
    """

    item_name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Name of checklist item",
    )
    description: str = Field(
        ...,
        description="Detailed description of requirement",
    )
    is_completed: bool = Field(
        ...,
        description="Whether this item is completed",
    )
    is_required: bool = Field(
        ...,
        description="Whether this item is mandatory for conversion",
    )
    completed_at: Optional[datetime] = Field(
        None,
        description="When this item was completed",
    )
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional notes about this item",
    )


class ConversionChecklist(BaseSchema):
    """
    Pre-conversion checklist validation.
    
    Checks all requirements before allowing conversion
    to student profile.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking ID being checked",
    )
    booking_reference: str = Field(
        ...,
        description="Booking reference",
    )

    # Checklist Items
    checks: List[ChecklistItem] = Field(
        ...,
        description="List of checklist items",
    )

    # Summary
    all_checks_passed: bool = Field(
        ...,
        description="Whether all required checks are completed",
    )
    can_convert: bool = Field(
        ...,
        description="Whether conversion can proceed",
    )

    missing_items: List[str] = Field(
        default_factory=list,
        description="List of missing/incomplete required items",
    )

    @field_validator("checks")
    @classmethod
    def validate_checks(cls, v: List[ChecklistItem]) -> List[ChecklistItem]:
        """Validate checklist has items."""
        if not v:
            raise ValueError("Checklist must have at least one item")
        return v


class BulkConversion(BaseCreateSchema):
    """
    Convert multiple bookings to students in bulk.
    
    Used for batch processing of check-ins.
    """

    booking_ids: List[UUID] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of booking IDs to convert (max 50)",
    )
    conversion_date: Date = Field(
        ...,
        description="Common check-in/conversion Date for all",
    )

    # Common Financial Confirmation
    all_deposits_paid: bool = Field(
        ...,
        description="Confirm all security deposits are paid",
    )
    all_first_rents_paid: bool = Field(
        ...,
        description="Confirm all first month rents are paid",
    )

    @field_validator("booking_ids")
    @classmethod
    def validate_booking_ids(cls, v: List[UUID]) -> List[UUID]:
        """Validate booking IDs list."""
        if len(v) == 0:
            raise ValueError("At least one booking ID is required")
        
        if len(v) > 50:
            raise ValueError("Maximum 50 bookings can be converted at once")
        
        # Remove duplicates
        unique_ids = list(dict.fromkeys(v))
        
        return unique_ids

    @field_validator("conversion_date")
    @classmethod
    def validate_conversion_date(cls, v: Date) -> Date:
        """Validate conversion Date."""
        if v > Date.today():
            raise ValueError("Conversion Date cannot be in the future")
        
        # Warn if too old
        days_ago = (Date.today() - v).days
        if days_ago > 7:
            # Log warning
            pass
        
        return v

    @model_validator(mode="after")
    def validate_financial_confirmation(self) -> "BulkConversion":
        """Validate financial confirmations."""
        if not self.all_deposits_paid:
            raise ValueError(
                "All security deposits must be confirmed paid for bulk conversion"
            )
        
        if not self.all_first_rents_paid:
            raise ValueError(
                "All first month rents must be confirmed paid for bulk conversion"
            )
        
        return self


class ConversionRollback(BaseCreateSchema):
    """
    Rollback a student conversion (emergency only).
    
    Used in cases where conversion was done in error
    or needs to be reversed.
    """

    student_profile_id: UUID = Field(
        ...,
        description="Student profile ID to rollback",
    )
    reason: str = Field(
        ...,
        min_length=20,
        max_length=500,
        description="Detailed reason for rollback (must be substantial)",
    )

    # Rollback Options
    delete_student_profile: bool = Field(
        False,
        description="Whether to delete the student profile",
    )
    restore_booking: bool = Field(
        True,
        description="Whether to restore original booking",
    )

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate rollback reason is substantial."""
        v = v.strip()
        if len(v) < 20:
            raise ValueError(
                "Rollback reason must be at least 20 characters "
                "and provide detailed justification"
            )
        return v
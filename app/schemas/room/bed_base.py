# --- File: app/schemas/room/bed_base.py ---
"""
Bed base schemas with enhanced validation and assignment management.

Provides schemas for individual bed management, bulk operations,
assignments, and releases.

Pydantic v2 Migration Notes:
- field_validator and model_validator already use v2 syntax
- All validators properly typed with @classmethod decorator
- mode="after" for model validators (v2 pattern)
- Date type works identically in v1 and v2
"""

from __future__ import annotations

from datetime import date as Date, timedelta
from typing import List, Optional

from pydantic import Field, field_validator, model_validator

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import BedStatus

__all__ = [
    "BedBase",
    "BedCreate",
    "BedUpdate",
    "BulkBedCreate",
    "BedAssignmentRequest",
    "BedReleaseRequest",
    "BedSwapRequest",
    "BulkBedStatusUpdate",
]


class BedBase(BaseSchema):
    """
    Base bed schema with core bed attributes.
    
    Represents an individual bed/berth within a room.
    """

    room_id: str = Field(
        ...,
        description="Room ID this bed belongs to",
    )
    bed_number: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Bed identifier within room (A1, B2, Bed-1, etc.)",
        examples=["A1", "B2", "Bed-1", "Upper-1"],
    )
    status: BedStatus = Field(
        default=BedStatus.AVAILABLE,
        description="Current bed status",
    )

    @field_validator("bed_number")
    @classmethod
    def validate_bed_number(cls, v: str) -> str:
        """
        Validate and normalize bed number.
        
        Ensures consistent bed number format.
        """
        v = v.strip().upper()
        if not v:
            raise ValueError("Bed number cannot be empty")
        # Remove excessive whitespace
        v = " ".join(v.split())
        return v


class BedCreate(BedBase, BaseCreateSchema):
    """
    Schema for creating a single bed.
    
    Used when manually adding beds to a room.
    """

    # Override to ensure required fields
    room_id: str = Field(
        ...,
        description="Room ID (required)",
    )
    bed_number: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Bed number (required)",
    )


class BedUpdate(BaseUpdateSchema):
    """
    Schema for updating bed information.
    
    Allows partial updates to bed attributes.
    """

    bed_number: Optional[str] = Field(
        default=None,
        min_length=1,
        max_length=10,
        description="Bed identifier",
    )
    status: Optional[BedStatus] = Field(
        default=None,
        description="Bed status",
    )
    is_occupied: Optional[bool] = Field(
        default=None,
        description="Occupancy status (legacy, prefer using status)",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Additional notes about the bed",
    )

    @field_validator("bed_number")
    @classmethod
    def validate_bed_number(cls, v: Optional[str]) -> Optional[str]:
        """Validate bed number format."""
        if v is not None:
            v = v.strip().upper()
            if not v:
                raise ValueError("Bed number cannot be empty")
            v = " ".join(v.split())
        return v

    @model_validator(mode="after")
    def sync_status_with_occupancy(self) -> "BedUpdate":
        """
        Sync legacy is_occupied with status field.
        
        Maintains backward compatibility.
        Pydantic v2: mode="after" validators receive the model instance.
        """
        if self.is_occupied is not None:
            if self.is_occupied:
                self.status = BedStatus.OCCUPIED
            else:
                # Only set to available if not in maintenance/reserved
                if self.status in [BedStatus.OCCUPIED, None]:
                    self.status = BedStatus.AVAILABLE
        return self


class BulkBedCreate(BaseCreateSchema):
    """
    Schema for bulk bed creation.
    
    Automatically creates multiple beds for a room with sequential numbering.
    Useful for initial room setup.
    """

    room_id: str = Field(
        ...,
        description="Room ID to create beds for",
    )
    bed_count: int = Field(
        ...,
        ge=1,
        le=20,
        description="Number of beds to create (1-20)",
    )
    bed_prefix: str = Field(
        default="B",
        min_length=1,
        max_length=5,
        description="Prefix for bed numbers (e.g., 'B', 'BED', 'A')",
        examples=["B", "BED", "A", "BERTH"],
    )
    start_number: int = Field(
        default=1,
        ge=1,
        le=100,
        description="Starting number for bed sequence",
    )
    number_format: str = Field(
        default="{prefix}{number}",
        description="Format string for bed numbers (use {prefix} and {number})",
        examples=["{prefix}{number}", "{prefix}-{number}", "Bed-{number}"],
    )

    @field_validator("bed_prefix")
    @classmethod
    def validate_bed_prefix(cls, v: str) -> str:
        """Validate and normalize bed prefix."""
        v = v.strip().upper()
        if not v:
            raise ValueError("Bed prefix cannot be empty")
        # Only alphanumeric characters
        if not v.replace("-", "").replace("_", "").isalnum():
            raise ValueError(
                "Bed prefix can only contain alphanumeric characters, hyphens, and underscores"
            )
        return v

    @field_validator("number_format")
    @classmethod
    def validate_number_format(cls, v: str) -> str:
        """Validate number format string."""
        if "{number}" not in v:
            raise ValueError("Number format must contain {number} placeholder")
        # Validate format string can be used
        try:
            test = v.format(prefix="TEST", number=1)
        except KeyError as e:
            raise ValueError(f"Invalid placeholder in format string: {e}")
        return v

    def generate_bed_numbers(self) -> List[str]:
        """
        Generate bed numbers based on configuration.
        
        Returns:
            List of bed numbers to create
        """
        bed_numbers = []
        for i in range(self.bed_count):
            bed_num = self.number_format.format(
                prefix=self.bed_prefix,
                number=self.start_number + i
            )
            bed_numbers.append(bed_num)
        return bed_numbers


class BedAssignmentRequest(BaseCreateSchema):
    """
    Schema for assigning a bed to a student.
    
    Creates a bed assignment with proper date tracking.
    """

    bed_id: str = Field(
        ...,
        description="Bed ID to assign",
    )
    student_id: str = Field(
        ...,
        description="Student ID to assign bed to",
    )
    occupied_from: Date = Field(
        ...,
        description="Occupancy start date",
    )
    expected_vacate_date: Optional[Date] = Field(
        default=None,
        description="Expected vacate/checkout date (optional)",
    )
    booking_id: Optional[str] = Field(
        default=None,
        description="Related booking ID (if applicable)",
    )
    notes: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Assignment notes",
    )

    @field_validator("occupied_from")
    @classmethod
    def validate_occupied_from(cls, v: Date) -> Date:
        """
        Validate occupancy start date.
        
        Allows past dates for historical assignments.
        """
        # Allow past dates for historical data entry
        # Could add warning logic here if needed
        return v

    @model_validator(mode="after")
    def validate_date_range(self) -> "BedAssignmentRequest":
        """
        Validate expected vacate date is after occupied_from.
        
        Pydantic v2: mode="after" validators receive the model instance.
        """
        if self.expected_vacate_date:
            if self.expected_vacate_date <= self.occupied_from:
                raise ValueError(
                    "Expected vacate date must be after occupancy start date"
                )
        return self


class BedReleaseRequest(BaseCreateSchema):
    """
    Schema for releasing a bed from a student.
    
    Handles bed checkout/vacating with proper documentation.
    """

    bed_id: str = Field(
        ...,
        description="Bed ID to release",
    )
    student_id: Optional[str] = Field(
        default=None,
        description="Student ID (optional, for validation)",
    )
    release_date: Date = Field(
        ...,
        description="Actual release/checkout date",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for release",
        examples=[
            "Completed stay",
            "Early checkout",
            "Transferred to another room",
            "Hostel exit",
        ],
    )
    condition_notes: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Bed/room condition notes at checkout",
    )
    damages_reported: bool = Field(
        default=False,
        description="Whether any damages were reported",
    )

    @field_validator("release_date")
    @classmethod
    def validate_release_date(cls, v: Date) -> Date:
        """
        Validate release date.
        
        Allows past dates for historical entries.
        Future dates might be allowed for scheduled releases.
        """
        # Allow past dates for data entry
        # Future dates might be allowed for scheduled releases
        return v


class BedSwapRequest(BaseCreateSchema):
    """
    Schema for swapping beds between students.
    
    Handles bed exchanges with proper tracking.
    """

    student_1_id: str = Field(
        ...,
        description="First student ID",
    )
    bed_1_id: str = Field(
        ...,
        description="First student's current bed ID",
    )
    student_2_id: str = Field(
        ...,
        description="Second student ID",
    )
    bed_2_id: str = Field(
        ...,
        description="Second student's current bed ID",
    )
    swap_date: Date = Field(
        ...,
        description="Date of bed swap",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for swap",
        examples=[
            "Student request",
            "Compatibility issues",
            "Room preference",
            "Administrative decision",
        ],
    )
    approved_by: Optional[str] = Field(
        default=None,
        description="Admin/supervisor who approved the swap",
    )

    @field_validator("swap_date")
    @classmethod
    def validate_swap_date(cls, v: Date) -> Date:
        """Validate swap date is not too far in the past."""
        # Warn if swap date is more than 30 days in the past
        if v < Date.today() - timedelta(days=30):
            # Could log a warning here
            pass
        
        return v

    @model_validator(mode="after")
    def validate_different_students_and_beds(self) -> "BedSwapRequest":
        """
        Ensure students and beds are different.
        
        Pydantic v2: mode="after" validators receive the model instance.
        """
        if self.student_1_id == self.student_2_id:
            raise ValueError("Cannot swap beds for the same student")
        
        if self.bed_1_id == self.bed_2_id:
            raise ValueError("Cannot swap the same bed")
        
        return self


class BulkBedStatusUpdate(BaseCreateSchema):
    """
    Schema for bulk bed status updates.
    
    Allows updating status of multiple beds simultaneously.
    Useful for maintenance or availability updates.
    """

    bed_ids: List[str] = Field(
        ...,
        min_length=1,
        max_length=50,
        description="List of bed IDs to update (max 50)",
    )
    status: BedStatus = Field(
        ...,
        description="New status for all beds",
    )
    reason: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Reason for bulk status change",
    )
    effective_date: Optional[Date] = Field(
        default=None,
        description="Effective date for status change",
    )

    @field_validator("bed_ids")
    @classmethod
    def validate_unique_bed_ids(cls, v: List[str]) -> List[str]:
        """Ensure bed IDs are unique."""
        if len(v) != len(set(v)):
            raise ValueError("Bed IDs must be unique")
        return v

    @model_validator(mode="after")
    def validate_status_change(self) -> "BulkBedStatusUpdate":
        """
        Validate status change requirements.
        
        Pydantic v2: mode="after" validators receive the model instance.
        """
        # If setting to maintenance, require reason
        if self.status == BedStatus.MAINTENANCE and not self.reason:
            raise ValueError(
                "Reason is required when setting beds to maintenance status"
            )
        return self
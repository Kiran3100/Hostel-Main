# --- File: app/schemas/attendance/attendance_base.py ---
"""
Base attendance schemas with comprehensive validation and type safety.

This module provides foundational schemas for attendance tracking including
single and bulk operations with enhanced validation logic.
"""

from datetime import date as Date, time
from decimal import Decimal
from typing import List, Union

from pydantic import Field, field_validator, model_validator
from pydantic.types import UUID4 as UUID

from app.schemas.common.base import BaseCreateSchema, BaseSchema, BaseUpdateSchema
from app.schemas.common.enums import AttendanceMode, AttendanceStatus

__all__ = [
    "AttendanceBase",
    "AttendanceCreate",
    "AttendanceUpdate",
    "BulkAttendanceCreate",
    "SingleAttendanceRecord",
]


class AttendanceBase(BaseSchema):
    """
    Base attendance schema with core fields.
    
    Provides common attendance attributes used across create/update operations.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    attendance_date: Date = Field(
        ...,
        description="Date of attendance record",
    )
    check_in_time: Union[time, None] = Field(
        None,
        description="Student check-in time",
    )
    check_out_time: Union[time, None] = Field(
        None,
        description="Student check-out time",
    )
    status: AttendanceStatus = Field(
        AttendanceStatus.PRESENT,
        description="Attendance status",
    )
    is_late: bool = Field(
        False,
        description="Whether student arrived late",
    )
    late_minutes: Union[int, None] = Field(
        None,
        ge=0,
        le=1440,  # Max 24 hours
        description="Minutes late (if applicable)",
    )
    attendance_mode: AttendanceMode = Field(
        AttendanceMode.MANUAL,
        description="Method used to record attendance",
    )
    marked_by: UUID = Field(
        ...,
        description="User ID who marked the attendance",
    )
    supervisor_id: Union[UUID, None] = Field(
        None,
        description="Supervisor ID who verified/marked attendance",
    )
    notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Additional notes or comments",
    )

    @field_validator("attendance_date")
    @classmethod
    def validate_attendance_date(cls, v: Date) -> Date:
        """
        Validate attendance Date is not in future.
        
        Attendance should only be marked for current or past dates.
        """
        if v > Date.today():
            raise ValueError("Attendance cannot be marked for future dates")
        return v

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize notes by stripping whitespace."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_check_times(self) -> "AttendanceBase":
        """
        Validate check-in and check-out time consistency.
        
        Ensures:
        - Check-out time is after check-in time (if both provided)
        - Late status is consistent with late_minutes
        - Absent students don't have check-in times
        """
        # Validate check-out is after check-in
        if self.check_in_time and self.check_out_time:
            if self.check_out_time <= self.check_in_time:
                raise ValueError(
                    "Check-out time must be after check-in time"
                )

        # Validate late status consistency
        if self.is_late and self.late_minutes is None:
            raise ValueError(
                "late_minutes must be provided when is_late is True"
            )

        if not self.is_late and self.late_minutes is not None:
            if self.late_minutes > 0:
                raise ValueError(
                    "is_late must be True when late_minutes is provided"
                )

        # Absent students shouldn't have check-in times
        if self.status == AttendanceStatus.ABSENT:
            if self.check_in_time or self.check_out_time:
                raise ValueError(
                    "Absent students cannot have check-in or check-out times"
                )
            if self.is_late or self.late_minutes:
                raise ValueError(
                    "Absent students cannot be marked as late"
                )

        return self


class AttendanceCreate(AttendanceBase, BaseCreateSchema):
    """
    Create attendance record with location and device tracking.
    
    Extends base schema with mobile app specific fields for geo-location
    and device information tracking.
    """

    location_lat: Union[Decimal, None] = Field(
        None,
        ge=Decimal("-90"),
        le=Decimal("90"),
        description="Latitude coordinate for mobile check-in",
    )
    location_lng: Union[Decimal, None] = Field(
        None,
        ge=Decimal("-180"),
        le=Decimal("180"),
        description="Longitude coordinate for mobile check-in",
    )
    device_info: Union[dict, None] = Field(
        None,
        description="Device information for mobile app check-ins",
    )

    @model_validator(mode="after")
    def validate_location_completeness(self) -> "AttendanceCreate":
        """
        Validate location coordinates are provided together.
        
        Both latitude and longitude must be provided or both must be None.
        """
        has_lat = self.location_lat is not None
        has_lng = self.location_lng is not None

        if has_lat != has_lng:
            raise ValueError(
                "Both latitude and longitude must be provided together"
            )

        return self


class AttendanceUpdate(BaseUpdateSchema):
    """
    Update attendance record with partial field updates.
    
    All fields are optional for flexible partial updates.
    """

    check_in_time: Union[time, None] = Field(
        None,
        description="Updated check-in time",
    )
    check_out_time: Union[time, None] = Field(
        None,
        description="Updated check-out time",
    )
    status: Union[AttendanceStatus, None] = Field(
        None,
        description="Updated attendance status",
    )
    is_late: Union[bool, None] = Field(
        None,
        description="Updated late status",
    )
    late_minutes: Union[int, None] = Field(
        None,
        ge=0,
        le=1440,
        description="Updated late minutes",
    )
    notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Updated notes",
    )

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize notes by stripping whitespace."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_update_consistency(self) -> "AttendanceUpdate":
        """
        Validate consistency of update fields.
        
        Ensures late status and minutes are consistent when both are updated.
        """
        if self.is_late is not None and self.late_minutes is not None:
            if self.is_late and self.late_minutes == 0:
                raise ValueError(
                    "late_minutes must be greater than 0 when is_late is True"
                )
            if not self.is_late and self.late_minutes > 0:
                raise ValueError(
                    "is_late must be True when late_minutes is greater than 0"
                )

        return self


class SingleAttendanceRecord(BaseSchema):
    """
    Single attendance record for bulk operations.
    
    Lightweight schema used within bulk attendance creation.
    """

    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    status: AttendanceStatus = Field(
        AttendanceStatus.PRESENT,
        description="Attendance status",
    )
    check_in_time: Union[time, None] = Field(
        None,
        description="Check-in time",
    )
    is_late: bool = Field(
        False,
        description="Late arrival flag",
    )
    late_minutes: Union[int, None] = Field(
        None,
        ge=0,
        le=1440,
        description="Minutes late",
    )
    notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Additional notes",
    )

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize notes by stripping whitespace."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_late_consistency(self) -> "SingleAttendanceRecord":
        """Validate late status and minutes consistency."""
        if self.is_late and self.late_minutes is None:
            raise ValueError(
                "late_minutes must be provided when is_late is True"
            )

        if not self.is_late and self.late_minutes is not None and self.late_minutes > 0:
            raise ValueError(
                "is_late must be True when late_minutes is provided"
            )

        # Absent students shouldn't be late
        if self.status == AttendanceStatus.ABSENT:
            if self.is_late or self.late_minutes:
                raise ValueError(
                    "Absent students cannot be marked as late"
                )

        return self


class BulkAttendanceCreate(BaseCreateSchema):
    """
    Bulk create multiple attendance records efficiently.
    
    Allows marking attendance for multiple students in a single operation
    with validation to prevent duplicate entries.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    attendance_date: Date = Field(
        ...,
        description="Date for all attendance records",
    )
    records: List[SingleAttendanceRecord] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="List of student attendance records",
    )
    marked_by: UUID = Field(
        ...,
        description="User ID who marked attendance",
    )
    supervisor_id: Union[UUID, None] = Field(
        None,
        description="Supervisor ID who verified attendance",
    )

    @field_validator("attendance_date")
    @classmethod
    def validate_attendance_date(cls, v: Date) -> Date:
        """Validate attendance Date is not in future."""
        if v > Date.today():
            raise ValueError("Attendance cannot be marked for future dates")
        return v

    @model_validator(mode="after")
    def validate_unique_students(self) -> "BulkAttendanceCreate":
        """
        Ensure no duplicate student IDs in bulk operation.
        
        Prevents multiple attendance records for same student on same Date.
        """
        student_ids = [record.student_id for record in self.records]
        unique_ids = set(student_ids)

        if len(student_ids) != len(unique_ids):
            # Find duplicates
            seen = set()
            duplicates = []
            for student_id in student_ids:
                if student_id in seen:
                    duplicates.append(str(student_id))
                seen.add(student_id)

            raise ValueError(
                f"Duplicate student IDs found in bulk operation: {', '.join(duplicates)}"
            )

        return self
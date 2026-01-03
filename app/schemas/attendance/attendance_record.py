# --- File: app/schemas/attendance/attendance_record.py ---
"""
Attendance recording schemas with validation for various marking methods.

Provides schemas for single, bulk, correction, and quick attendance marking
operations with comprehensive validation logic.
"""

from datetime import date as Date, time, datetime
from typing import List, Union, Optional

from pydantic import Field, field_validator, model_validator
from pydantic.types import UUID4 as UUID

from app.schemas.common.base import BaseCreateSchema, BaseSchema
from app.schemas.common.enums import AttendanceStatus, AttendanceMode

__all__ = [
    "AttendanceRecordRequest",
    "BulkAttendanceRequest",
    "StudentAttendanceRecord",
    "AttendanceCorrection",
    "QuickAttendanceMarkAll",
    "AttendanceRecord",
    "AttendanceResponse",
]


class AttendanceRecord(BaseSchema):
    """
    Attendance record response schema.
    
    Represents a complete attendance record with all metadata
    for API responses.
    """
    
    id: UUID = Field(
        ...,
        description="Attendance record unique identifier",
    )
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
        description="Date of attendance",
    )
    status: AttendanceStatus = Field(
        ...,
        description="Attendance status",
    )
    check_in_time: Union[time, None] = Field(
        None,
        description="Check-in time",
    )
    check_out_time: Union[time, None] = Field(
        None,
        description="Check-out time",
    )
    is_late: bool = Field(
        False,
        description="Late arrival indicator",
    )
    late_minutes: Union[int, None] = Field(
        None,
        description="Minutes late",
    )
    notes: Union[str, None] = Field(
        None,
        description="Additional notes or remarks",
    )
    marking_mode: AttendanceMode = Field(
        ...,
        description="Method used to record attendance",
    )
    marked_by: UUID = Field(
        ...,
        description="User ID who marked the attendance",
    )
    supervisor_id: Union[UUID, None] = Field(
        None,
        description="Supervisor ID who verified attendance",
    )
    created_at: datetime = Field(
        ...,
        description="Record creation timestamp",
    )
    updated_at: Union[datetime, None] = Field(
        None,
        description="Record last update timestamp",
    )
    is_corrected: bool = Field(
        False,
        description="Indicates if record has been corrected",
    )
    correction_count: int = Field(
        0,
        description="Number of times record has been corrected",
    )

    class Config:
        from_attributes = True


class AttendanceResponse(BaseSchema):
    """
    Response schema for attendance queries.
    
    Contains list of attendance records with metadata.
    """
    
    records: List[AttendanceRecord] = Field(
        ...,
        description="List of attendance records",
    )
    total_count: int = Field(
        ...,
        description="Total number of records",
    )
    present_count: int = Field(
        ...,
        description="Number of present records",
    )
    absent_count: int = Field(
        ...,
        description="Number of absent records",
    )
    late_count: int = Field(
        ...,
        description="Number of late records",
    )
    attendance_percentage: float = Field(
        ...,
        description="Attendance percentage",
    )
    date_range: Optional[dict] = Field(
        None,
        description="Date range of the records",
    )

    class Config:
        from_attributes = True


class AttendanceRecordRequest(BaseCreateSchema):
    """
    Record attendance for single student with validation.
    
    Used for individual attendance marking with comprehensive validation.
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
        description="Date of attendance",
    )
    status: AttendanceStatus = Field(
        AttendanceStatus.PRESENT,
        description="Attendance status",
    )
    check_in_time: Union[time, None] = Field(
        None,
        description="Check-in time (required for PRESENT status)",
    )
    check_out_time: Union[time, None] = Field(
        None,
        description="Check-out time",
    )
    is_late: bool = Field(
        False,
        description="Late arrival indicator",
    )
    late_minutes: Union[int, None] = Field(
        None,
        ge=0,
        le=1440,
        description="Minutes late (if applicable)",
    )
    notes: Union[str, None] = Field(
        None,
        max_length=500,
        description="Additional notes or remarks",
    )

    @field_validator("attendance_date")
    @classmethod
    def validate_date(cls, v: Date) -> Date:
        """Ensure attendance Date is not in future."""
        if v > Date.today():
            raise ValueError("Attendance Date cannot be in the future")
        return v

    @field_validator("notes")
    @classmethod
    def validate_notes(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize and validate notes."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_attendance_logic(self) -> "AttendanceRecordRequest":
        """
        Validate attendance record consistency.
        
        Ensures:
        - Present students have check-in time
        - Absent students don't have check-in/out times
        - Late status matches late_minutes
        - Check-out is after check-in
        """
        # Present students should have check-in time
        if self.status == AttendanceStatus.PRESENT:
            if self.check_in_time is None:
                raise ValueError(
                    "check_in_time is required for PRESENT status"
                )

        # Absent students shouldn't have times
        if self.status == AttendanceStatus.ABSENT:
            if self.check_in_time or self.check_out_time:
                raise ValueError(
                    "Absent students cannot have check-in or check-out times"
                )
            if self.is_late or self.late_minutes:
                raise ValueError(
                    "Absent students cannot be marked as late"
                )

        # Validate check-out time
        if self.check_in_time and self.check_out_time:
            if self.check_out_time <= self.check_in_time:
                raise ValueError(
                    "check_out_time must be after check_in_time"
                )

        # Validate late status
        if self.is_late and self.late_minutes is None:
            raise ValueError(
                "late_minutes is required when is_late is True"
            )

        if not self.is_late and self.late_minutes is not None and self.late_minutes > 0:
            raise ValueError(
                "is_late must be True when late_minutes is greater than 0"
            )

        return self


class StudentAttendanceRecord(BaseSchema):
    """
    Individual student attendance record for bulk operations.
    
    Lightweight schema optimized for bulk processing with optional
    field overrides.
    """

    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    status: Union[AttendanceStatus, None] = Field(
        None,
        description="Attendance status (uses default_status if None)",
    )
    check_in_time: Union[time, None] = Field(
        None,
        description="Check-in time",
    )
    check_out_time: Union[time, None] = Field(
        None,
        description="Check-out time",
    )
    is_late: Union[bool, None] = Field(
        None,
        description="Late arrival indicator",
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
        """Normalize notes."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_consistency(self) -> "StudentAttendanceRecord":
        """Validate consistency of provided fields."""
        # Validate check times
        if self.check_in_time and self.check_out_time:
            if self.check_out_time <= self.check_in_time:
                raise ValueError(
                    "check_out_time must be after check_in_time"
                )

        # Validate late status
        if self.is_late is not None and self.late_minutes is not None:
            if self.is_late and self.late_minutes == 0:
                raise ValueError(
                    "late_minutes must be greater than 0 when is_late is True"
                )

        # Absent students validation
        if self.status == AttendanceStatus.ABSENT:
            if self.check_in_time or self.check_out_time:
                raise ValueError(
                    "Absent students cannot have check-in or check-out times"
                )

        return self


class BulkAttendanceRequest(BaseCreateSchema):
    """
    Mark attendance for multiple students efficiently.
    
    Supports default status for all students with per-student overrides
    and duplicate prevention.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    attendance_date: Date = Field(
        ...,
        description="Date for all attendance records",
    )
    default_status: AttendanceStatus = Field(
        AttendanceStatus.PRESENT,
        description="Default status applied to all students unless overridden",
    )
    student_records: List[StudentAttendanceRecord] = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Individual student attendance records",
    )
    marked_by: UUID = Field(
        ...,
        description="User ID who marked the attendance",
    )
    supervisor_id: Union[UUID, None] = Field(
        None,
        description="Supervisor ID who verified the attendance",
    )
    marking_mode: AttendanceMode = Field(
        AttendanceMode.MANUAL,
        description="Method used to record attendance",
    )

    @field_validator("attendance_date")
    @classmethod
    def validate_date(cls, v: Date) -> Date:
        """Validate attendance Date is not in future."""
        if v > Date.today():
            raise ValueError("Attendance Date cannot be in the future")
        return v

    @model_validator(mode="after")
    def validate_unique_students(self) -> "BulkAttendanceRequest":
        """
        Ensure no duplicate student IDs in the request.
        
        Prevents multiple records for same student on same Date.
        """
        student_ids = [record.student_id for record in self.student_records]
        unique_ids = set(student_ids)

        if len(student_ids) != len(unique_ids):
            # Identify duplicates for error message
            seen = set()
            duplicates = set()
            for student_id in student_ids:
                if student_id in seen:
                    duplicates.add(str(student_id))
                seen.add(student_id)

            raise ValueError(
                f"Duplicate student IDs not allowed: {', '.join(duplicates)}"
            )

        return self


class AttendanceCorrection(BaseCreateSchema):
    """
    Correct previously marked attendance with audit trail.
    
    Allows authorized users to correct attendance errors with
    mandatory reason documentation.
    """

    attendance_id: UUID = Field(
        ...,
        description="Attendance record ID to correct",
    )
    corrected_status: AttendanceStatus = Field(
        ...,
        description="Corrected attendance status",
    )
    corrected_check_in_time: Union[time, None] = Field(
        None,
        description="Corrected check-in time",
    )
    corrected_check_out_time: Union[time, None] = Field(
        None,
        description="Corrected check-out time",
    )
    corrected_is_late: Union[bool, None] = Field(
        None,
        description="Corrected late status",
    )
    corrected_late_minutes: Union[int, None] = Field(
        None,
        ge=0,
        le=1440,
        description="Corrected late minutes",
    )
    correction_reason: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Detailed reason for correction (mandatory for audit)",
    )
    corrected_by: UUID = Field(
        ...,
        description="User ID who made the correction",
    )

    @field_validator("correction_reason")
    @classmethod
    def validate_reason(cls, v: str) -> str:
        """Validate correction reason is meaningful."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError(
                "Correction reason must be at least 10 characters"
            )
        return v

    @model_validator(mode="after")
    def validate_corrections(self) -> "AttendanceCorrection":
        """
        Validate corrected values consistency.
        
        Ensures corrected times and late status are logically consistent.
        """
        # Validate check times
        if self.corrected_check_in_time and self.corrected_check_out_time:
            if self.corrected_check_out_time <= self.corrected_check_in_time:
                raise ValueError(
                    "Corrected check-out time must be after check-in time"
                )

        # Validate late status
        if self.corrected_is_late is not None and self.corrected_late_minutes is not None:
            if self.corrected_is_late and self.corrected_late_minutes == 0:
                raise ValueError(
                    "Corrected late_minutes must be greater than 0 when is_late is True"
                )

        # Absent students shouldn't have times
        if self.corrected_status == AttendanceStatus.ABSENT:
            if self.corrected_check_in_time or self.corrected_check_out_time:
                raise ValueError(
                    "Absent students cannot have check-in or check-out times"
                )
            if self.corrected_is_late or self.corrected_late_minutes:
                raise ValueError(
                    "Absent students cannot be marked as late"
                )

        return self


class QuickAttendanceMarkAll(BaseCreateSchema):
    """
    Quick mark all students with exception handling.
    
    Efficiently marks all students as present with ability to specify
    exceptions (absent, on leave) for streamlined daily attendance.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    attendance_date: Date = Field(
        ...,
        description="Date for attendance marking",
    )
    default_check_in_time: Union[time, None] = Field(
        None,
        description="Default check-in time for all present students",
    )
    absent_student_ids: List[UUID] = Field(
        default_factory=list,
        max_length=500,
        description="Student IDs to mark as absent",
    )
    on_leave_student_ids: List[UUID] = Field(
        default_factory=list,
        max_length=500,
        description="Student IDs to mark as on leave",
    )
    late_student_ids: List[UUID] = Field(
        default_factory=list,
        max_length=500,
        description="Student IDs to mark as late",
    )
    marked_by: UUID = Field(
        ...,
        description="User ID who marked the attendance",
    )
    supervisor_id: Union[UUID, None] = Field(
        None,
        description="Supervisor ID who verified attendance",
    )

    @field_validator("attendance_date")
    @classmethod
    def validate_date(cls, v: Date) -> Date:
        """Validate attendance Date is not in future."""
        if v > Date.today():
            raise ValueError("Attendance Date cannot be in the future")
        return v

    @model_validator(mode="after")
    def validate_no_overlapping_exceptions(self) -> "QuickAttendanceMarkAll":
        """
        Ensure students aren't in multiple exception lists.
        
        A student can only be in one exception category.
        """
        absent_set = set(self.absent_student_ids)
        leave_set = set(self.on_leave_student_ids)
        late_set = set(self.late_student_ids)

        # Check for overlaps
        overlap_absent_leave = absent_set & leave_set
        overlap_absent_late = absent_set & late_set
        overlap_leave_late = leave_set & late_set

        errors = []
        if overlap_absent_leave:
            errors.append(
                f"Students in both absent and leave lists: {', '.join(str(id) for id in overlap_absent_leave)}"
            )
        if overlap_absent_late:
            errors.append(
                f"Students in both absent and late lists: {', '.join(str(id) for id in overlap_absent_late)}"
            )
        if overlap_leave_late:
            errors.append(
                f"Students in both leave and late lists: {', '.join(str(id) for id in overlap_leave_late)}"
            )

        if errors:
            raise ValueError("; ".join(errors))

        return self
# --- File: app/schemas/attendance/attendance_response.py ---
"""
Attendance response schemas optimized for API responses.

Provides various response formats for attendance data including
detailed, summary, and list views with computed fields.
"""

from __future__ import annotations

from datetime import date as Date, datetime, time
from decimal import Decimal
from typing import Optional

from pydantic import Field, computed_field
from pydantic.types import UUID4 as UUID

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import AttendanceMode, AttendanceStatus

__all__ = [
    "AttendanceResponse",
    "AttendanceDetail",
    "AttendanceListItem",
    "DailyAttendanceSummary",
]


class AttendanceResponse(BaseResponseSchema):
    """
    Standard attendance response with essential information.
    
    Lightweight response schema for list views and basic queries.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    student_name: str = Field(
        ...,
        description="Student full name",
    )
    room_number: Optional[str] = Field(
        None,
        description="Student room number",
    )
    attendance_date: Date = Field(
        ...,
        description="Date of attendance",
    )
    check_in_time: Optional[time] = Field(
        None,
        description="Check-in time",
    )
    check_out_time: Optional[time] = Field(
        None,
        description="Check-out time",
    )
    status: AttendanceStatus = Field(
        ...,
        description="Attendance status",
    )
    is_late: bool = Field(
        ...,
        description="Late arrival indicator",
    )
    late_minutes: Optional[int] = Field(
        None,
        description="Minutes late (if applicable)",
    )
    marked_by: UUID = Field(
        ...,
        description="User ID who marked attendance",
    )
    marked_by_name: str = Field(
        ...,
        description="Name of user who marked attendance",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_display(self) -> str:
        """Human-readable status display."""
        status_map = {
            AttendanceStatus.PRESENT: "Present",
            AttendanceStatus.ABSENT: "Absent",
            AttendanceStatus.LATE: "Late",
            AttendanceStatus.ON_LEAVE: "On Leave",
            AttendanceStatus.HALF_DAY: "Half Day",
        }
        return status_map.get(self.status, self.status.value)


class AttendanceDetail(BaseResponseSchema):
    """
    Detailed attendance information with complete metadata.
    
    Comprehensive response including location data, device info,
    and audit trail for detailed views.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    student_name: str = Field(
        ...,
        description="Student full name",
    )
    student_email: str = Field(
        ...,
        description="Student email address",
    )
    student_phone: str = Field(
        ...,
        description="Student phone number",
    )
    room_number: Optional[str] = Field(
        None,
        description="Student room number",
    )
    attendance_date: Date = Field(
        ...,
        description="Date of attendance",
    )
    check_in_time: Optional[time] = Field(
        None,
        description="Check-in time",
    )
    check_out_time: Optional[time] = Field(
        None,
        description="Check-out time",
    )
    status: AttendanceStatus = Field(
        ...,
        description="Attendance status",
    )
    is_late: bool = Field(
        ...,
        description="Late arrival indicator",
    )
    late_minutes: Optional[int] = Field(
        None,
        description="Minutes late",
    )
    attendance_mode: AttendanceMode = Field(
        ...,
        description="Method of attendance recording",
    )
    marked_by: UUID = Field(
        ...,
        description="User ID who marked attendance",
    )
    marked_by_name: str = Field(
        ...,
        description="Name of user who marked attendance",
    )
    supervisor_id: Optional[UUID] = Field(
        None,
        description="Supervisor ID who verified",
    )
    supervisor_name: Optional[str] = Field(
        None,
        description="Supervisor name",
    )
    notes: Optional[str] = Field(
        None,
        description="Additional notes",
    )
    location_lat: Optional[Decimal] = Field(
        None,
        description="Latitude (for mobile check-in)",
    )
    location_lng: Optional[Decimal] = Field(
        None,
        description="Longitude (for mobile check-in)",
    )
    device_info: Optional[dict] = Field(
        None,
        description="Device information (for mobile check-in)",
    )
    created_at: datetime = Field(
        ...,
        description="Record creation timestamp",
    )
    updated_at: datetime = Field(
        ...,
        description="Last update timestamp",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def has_location_data(self) -> bool:
        """Check if location data is available."""
        return self.location_lat is not None and self.location_lng is not None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def marking_method(self) -> str:
        """Human-readable marking method."""
        method_map = {
            AttendanceMode.MANUAL: "Manual Entry",
            AttendanceMode.BIOMETRIC: "Biometric System",
            AttendanceMode.QR_CODE: "QR Code Scan",
            AttendanceMode.MOBILE_APP: "Mobile App",
        }
        return method_map.get(self.attendance_mode, self.attendance_mode.value)


class AttendanceListItem(BaseSchema):
    """
    Minimal attendance list item for efficient list rendering.
    
    Optimized for pagination and list views with minimal data transfer.
    """

    id: UUID = Field(
        ...,
        description="Attendance record unique identifier",
    )
    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    student_name: str = Field(
        ...,
        description="Student name",
    )
    room_number: Optional[str] = Field(
        None,
        description="Room number",
    )
    attendance_date: Date = Field(
        ...,
        description="Attendance Date",
    )
    status: AttendanceStatus = Field(
        ...,
        description="Attendance status",
    )
    check_in_time: Optional[time] = Field(
        None,
        description="Check-in time",
    )
    is_late: bool = Field(
        ...,
        description="Late indicator",
    )
    marked_by_name: str = Field(
        ...,
        description="Marked by user name",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_badge_color(self) -> str:
        """
        Get color code for status badge (for UI rendering).
        
        Returns color name/code for frontend styling.
        """
        color_map = {
            AttendanceStatus.PRESENT: "green",
            AttendanceStatus.ABSENT: "red",
            AttendanceStatus.LATE: "orange",
            AttendanceStatus.ON_LEAVE: "blue",
            AttendanceStatus.HALF_DAY: "yellow",
        }
        return color_map.get(self.status, "gray")


class DailyAttendanceSummary(BaseSchema):
    """
    Daily attendance summary with statistics.
    
    Provides aggregated view of daily attendance for a hostel
    with percentage calculations.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    date: Date = Field(
        ...,
        description="Attendance Date",
    )
    total_students: int = Field(
        ...,
        ge=0,
        description="Total number of students",
    )
    total_present: int = Field(
        ...,
        ge=0,
        description="Number of present students",
    )
    total_absent: int = Field(
        ...,
        ge=0,
        description="Number of absent students",
    )
    total_late: int = Field(
        ...,
        ge=0,
        description="Number of late students",
    )
    total_on_leave: int = Field(
        ...,
        ge=0,
        description="Number of students on leave",
    )
    total_half_day: int = Field(
        default=0,
        ge=0,
        description="Number of half-day attendances",
    )
    attendance_percentage: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Overall attendance percentage",
    )
    marked_by: UUID = Field(
        ...,
        description="User ID who marked attendance",
    )
    marked_by_name: str = Field(
        ...,
        description="Name of user who marked attendance",
    )
    marking_completed: bool = Field(
        ...,
        description="Whether attendance marking is complete",
    )
    marked_at: Optional[datetime] = Field(
        None,
        description="Timestamp when marking was completed",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def pending_students(self) -> int:
        """Calculate number of students with pending attendance."""
        marked = (
            self.total_present
            + self.total_absent
            + self.total_late
            + self.total_on_leave
            + self.total_half_day
        )
        return max(0, self.total_students - marked)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def attendance_status(self) -> str:
        """
        Get attendance quality status based on percentage.
        
        Returns status: excellent, good, average, poor, critical
        """
        percentage = float(self.attendance_percentage)
        if percentage >= 95:
            return "excellent"
        elif percentage >= 85:
            return "good"
        elif percentage >= 75:
            return "average"
        elif percentage >= 60:
            return "poor"
        else:
            return "critical"
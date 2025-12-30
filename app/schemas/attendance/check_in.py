"""
Check-in/check-out schemas for real-time attendance tracking.

Provides schemas for check-in operations, status tracking, and session management
with comprehensive validation and computed fields.
"""

from datetime import date as Date, datetime, time
from decimal import Decimal
from typing import Dict, List, Union, Any

from pydantic import Field, computed_field, field_validator
from pydantic.types import UUID4 as UUID

from app.schemas.common.base import BaseResponseSchema, BaseSchema
from app.schemas.common.enums import AttendanceStatus

__all__ = [
    "CheckInResponse",
    "CheckInStatus", 
    "CheckInSession",
    "CheckInHistory",
]


class CheckInResponse(BaseResponseSchema):
    """
    Check-in/check-out operation response.
    
    Returned after successful check-in or check-out operations
    with session details and status information.
    """

    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    student_name: str = Field(
        ...,
        description="Student full name",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    room_number: Union[str, None] = Field(
        None,
        description="Student room number",
    )

    # Operation details
    operation_type: str = Field(
        ...,
        pattern=r"^(check_in|check_out|emergency_checkout)$",
        description="Type of operation performed",
    )
    check_in_time: Union[datetime, None] = Field(
        None,
        description="Check-in timestamp",
    )
    check_out_time: Union[datetime, None] = Field(
        None,
        description="Check-out timestamp", 
    )
    attendance_date: Date = Field(
        ...,
        description="Date of attendance record",
    )

    # Session information
    session_duration: Union[int, None] = Field(
        None,
        ge=0,
        description="Session duration in minutes (for check-out)",
    )
    is_active_session: bool = Field(
        ...,
        description="Whether student has an active session",
    )

    # Location and device
    device_id: Union[str, None] = Field(
        None,
        description="Device identifier used for operation",
    )
    location: Union[str, None] = Field(
        None,
        description="Location identifier where operation occurred",
    )

    # Status and validation
    status: AttendanceStatus = Field(
        ...,
        description="Current attendance status",
    )
    is_late: bool = Field(
        default=False,
        description="Whether check-in was late",
    )
    late_minutes: Union[int, None] = Field(
        None,
        ge=0,
        description="Minutes late (if applicable)",
    )

    # Operation metadata
    processed_at: datetime = Field(
        ...,
        description="Server processing timestamp",
    )
    success: bool = Field(
        default=True,
        description="Whether operation was successful",
    )
    message: str = Field(
        default="Operation completed successfully",
        description="Human-readable operation result message",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def operation_display(self) -> str:
        """Human-readable operation type."""
        operation_map = {
            "check_in": "Check In",
            "check_out": "Check Out", 
            "emergency_checkout": "Emergency Check Out",
        }
        return operation_map.get(self.operation_type, self.operation_type)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def session_duration_display(self) -> Union[str, None]:
        """Human-readable session duration."""
        if self.session_duration is None:
            return None
        
        hours = self.session_duration // 60
        minutes = self.session_duration % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"


class CheckInSession(BaseSchema):
    """
    Active check-in session details.
    
    Provides information about current active session including
    duration, compliance, and expected check-out.
    """

    session_id: UUID = Field(
        ...,
        description="Session unique identifier",
    )
    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    check_in_time: datetime = Field(
        ...,
        description="Session start timestamp",
    )
    attendance_date: Date = Field(
        ...,
        description="Date of attendance",
    )

    # Duration tracking
    current_duration_minutes: int = Field(
        ...,
        ge=0,
        description="Current session duration in minutes",
    )
    expected_checkout_time: Union[datetime, None] = Field(
        None,
        description="Expected/recommended checkout time",
    )

    # Session metadata
    device_id: Union[str, None] = Field(
        None,
        description="Device used for check-in",
    )
    location: Union[str, None] = Field(
        None,
        description="Check-in location",
    )
    is_late: bool = Field(
        ...,
        description="Whether check-in was late",
    )
    late_minutes: Union[int, None] = Field(
        None,
        ge=0,
        description="Minutes late for check-in",
    )

    # Compliance tracking
    meets_minimum_duration: bool = Field(
        ...,
        description="Whether session meets minimum duration requirement",
    )
    minimum_duration_minutes: Union[int, None] = Field(
        None,
        ge=0,
        description="Minimum required session duration",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def duration_display(self) -> str:
        """Human-readable current duration."""
        hours = self.current_duration_minutes // 60
        minutes = self.current_duration_minutes % 60
        return f"{hours}h {minutes}m"

    @computed_field  # type: ignore[prop-decorator]
    @property
    def session_status(self) -> str:
        """Get session compliance status."""
        if self.minimum_duration_minutes is None:
            return "active"
        
        if self.current_duration_minutes >= self.minimum_duration_minutes:
            return "compliant"
        else:
            return "below_minimum"


class CheckInHistory(BaseSchema):
    """
    Historical check-in record.
    
    Represents a completed check-in/check-out session for history views.
    """

    session_date: Date = Field(
        ...,
        description="Session date",
    )
    check_in_time: Union[datetime, None] = Field(
        None,
        description="Check-in timestamp",
    )
    check_out_time: Union[datetime, None] = Field(
        None,
        description="Check-out timestamp",
    )
    session_duration_minutes: Union[int, None] = Field(
        None,
        ge=0,
        description="Total session duration in minutes",
    )
    was_late: bool = Field(
        ...,
        description="Whether check-in was late",
    )
    late_minutes: Union[int, None] = Field(
        None,
        ge=0,
        description="Minutes late for check-in",
    )
    status: AttendanceStatus = Field(
        ...,
        description="Final attendance status",
    )
    device_id: Union[str, None] = Field(
        None,
        description="Device used for check-in",
    )
    location: Union[str, None] = Field(
        None,
        description="Check-in location",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def duration_display(self) -> Union[str, None]:
        """Human-readable session duration."""
        if self.session_duration_minutes is None:
            return None
            
        hours = self.session_duration_minutes // 60
        minutes = self.session_duration_minutes % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"


class CheckInStatus(BaseResponseSchema):
    """
    Comprehensive check-in status with session and history information.
    
    Provides current status, active session details, and optional
    historical data for student dashboard and status queries.
    """

    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    student_name: str = Field(
        ...,
        description="Student full name",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    room_number: Union[str, None] = Field(
        None,
        description="Student room number",
    )

    # Current status
    is_checked_in: bool = Field(
        ...,
        description="Whether student is currently checked in",
    )
    current_status: str = Field(
        ...,
        pattern=r"^(checked_in|checked_out|not_started)$",
        description="Current check-in status",
    )
    last_activity: Union[datetime, None] = Field(
        None,
        description="Timestamp of last check-in/out activity",
    )
    last_activity_type: Union[str, None] = Field(
        None,
        pattern=r"^(check_in|check_out|emergency_checkout)$",
        description="Type of last activity",
    )

    # Active session (if checked in)
    active_session: Union[CheckInSession, None] = Field(
        None,
        description="Current active session details",
    )

    # Today's status
    todays_date: Date = Field(
        ...,
        description="Current date for today's status",
    )
    todays_attendance_marked: bool = Field(
        ...,
        description="Whether attendance is marked for today",
    )
    todays_attendance_status: Union[AttendanceStatus, None] = Field(
        None,
        description="Today's attendance status (if marked)",
    )

    # Recent history (optional)
    recent_history: Union[List[CheckInHistory], None] = Field(
        None,
        description="Recent check-in history (if requested)",
    )

    # Analytics (optional)
    monthly_stats: Union[Dict[str, Any], None] = Field(
        None,
        description="Monthly statistics (if requested)",
    )

    # Compliance and policy
    meets_daily_requirement: bool = Field(
        ...,
        description="Whether daily attendance requirement is met",
    )
    policy_violations: List[str] = Field(
        default_factory=list,
        description="List of current policy violations",
    )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def status_display(self) -> str:
        """Human-readable status display."""
        status_map = {
            "checked_in": "Checked In",
            "checked_out": "Checked Out",
            "not_started": "Not Started",
        }
        return status_map.get(self.current_status, self.current_status)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def compliance_status(self) -> str:
        """Get overall compliance status."""
        if self.policy_violations:
            return "non_compliant"
        elif self.meets_daily_requirement:
            return "compliant"
        else:
            return "pending"

    @field_validator("recent_history")
    @classmethod
    def validate_history_limit(cls, v: Union[List[CheckInHistory], None]) -> Union[List[CheckInHistory], None]:
        """Limit history to reasonable size."""
        if v is not None and len(v) > 30:
            return v[:30]  # Limit to last 30 records
        return v
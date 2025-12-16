# --- File: app/schemas/attendance/attendance_policy.py ---
"""
Attendance policy configuration schemas.

Defines policy rules, thresholds, and violation tracking for
attendance management with comprehensive validation.
"""

from datetime import date as Date, datetime, time
from decimal import Decimal
from typing import List, Union

from pydantic import Field, field_validator, model_validator
from pydantic.types import UUID4 as UUID

from app.schemas.common.base import BaseResponseSchema, BaseSchema, BaseUpdateSchema

__all__ = [
    "AttendancePolicy",
    "PolicyConfig",
    "PolicyUpdate",
    "PolicyViolation",
]


class AttendancePolicy(BaseResponseSchema):
    """
    Attendance policy configuration for a hostel.
    
    Defines rules, thresholds, and automated behaviors for
    attendance tracking and enforcement.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )

    # Minimum requirements
    minimum_attendance_percentage: Decimal = Field(
        ...,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Minimum required attendance percentage",
    )

    # Late entry configuration
    late_entry_threshold_minutes: int = Field(
        ...,
        ge=0,
        le=240,
        description="Minutes after expected time to mark as late",
    )
    grace_period_minutes: int = Field(
        default=5,
        ge=0,
        le=30,
        description="Grace period before marking late",
    )
    grace_days_per_month: int = Field(
        ...,
        ge=0,
        le=31,
        description="Allowed late entries per month without penalty",
    )

    # Absence alerts
    consecutive_absence_alert_days: int = Field(
        ...,
        ge=1,
        le=30,
        description="Alert after N consecutive absences",
    )
    total_absence_alert_threshold: int = Field(
        default=10,
        ge=1,
        description="Alert after N total absences in period",
    )

    # Notification settings
    notify_guardian_on_absence: bool = Field(
        True,
        description="Send guardian notification on absence",
    )
    notify_admin_on_low_attendance: bool = Field(
        True,
        description="Send admin notification for low attendance",
    )
    notify_student_on_low_attendance: bool = Field(
        default=True,
        description="Send student notification for low attendance",
    )
    low_attendance_threshold: Decimal = Field(
        Decimal("75.00"),
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Threshold for low attendance notifications",
    )

    # Auto-marking configuration
    auto_mark_absent_enabled: bool = Field(
        default=False,
        description="Enable automatic absent marking",
    )
    auto_mark_absent_after_time: Union[time, None] = Field(
        None,
        description="Auto mark absent if not checked in by this time",
    )

    # Weekend and holiday handling
    track_weekend_attendance: bool = Field(
        default=False,
        description="Track attendance on weekends",
    )
    track_holiday_attendance: bool = Field(
        default=False,
        description="Track attendance on holidays",
    )

    # Policy status
    is_active: bool = Field(
        True,
        description="Whether policy is currently active",
    )
    effective_from: Union[Date, None] = Field(
        None,
        description="Date from which policy is effective",
    )
    effective_until: Union[Date, None] = Field(
        None,
        description="Date until which policy is effective",
    )

    @field_validator("minimum_attendance_percentage", "low_attendance_threshold")
    @classmethod
    def round_percentage(cls, v: Decimal) -> Decimal:
        """Round percentage to 2 decimal places."""
        return round(v, 2)

    @model_validator(mode="after")
    def validate_policy_consistency(self) -> "AttendancePolicy":
        """
        Validate policy configuration consistency.
        
        Ensures:
        - Low attendance threshold is below minimum requirement
        - Effective dates are logical
        - Auto-mark time is set if enabled
        """
        # Low attendance threshold should be less than minimum
        if self.low_attendance_threshold > self.minimum_attendance_percentage:
            raise ValueError(
                "low_attendance_threshold should be less than minimum_attendance_percentage"
            )

        # Validate effective dates
        if self.effective_from and self.effective_until:
            if self.effective_until < self.effective_from:
                raise ValueError(
                    "effective_until must be after effective_from"
                )

        # Auto-mark validation
        if self.auto_mark_absent_enabled and self.auto_mark_absent_after_time is None:
            raise ValueError(
                "auto_mark_absent_after_time is required when auto_mark_absent_enabled is True"
            )

        return self


class PolicyConfig(BaseSchema):
    """
    Extended policy configuration with calculation rules.
    
    Defines how attendance is calculated and what factors are
    considered in the calculation.
    """

    # Calculation settings
    calculation_period: str = Field(
        "monthly",
        pattern=r"^(weekly|monthly|semester|yearly|custom)$",
        description="Period for attendance calculation",
    )
    custom_period_days: Union[int, None] = Field(
        None,
        ge=1,
        le=365,
        description="Custom period length in days (if calculation_period is 'custom')",
    )

    # Leave handling
    count_leave_as_absent: bool = Field(
        False,
        description="Whether to count approved leaves as absent",
    )
    count_leave_as_present: bool = Field(
        True,
        description="Whether to count approved leaves as present",
    )
    max_leaves_per_month: int = Field(
        3,
        ge=0,
        le=31,
        description="Maximum allowed leaves per month",
    )
    max_leaves_per_semester: Union[int, None] = Field(
        None,
        ge=0,
        description="Maximum allowed leaves per semester",
    )

    # Weekend configuration
    include_weekends: bool = Field(
        False,
        description="Include weekends in attendance tracking",
    )
    weekend_days: List[str] = Field(
        default_factory=lambda: ["Saturday", "Sunday"],
        description="Days considered as weekends",
    )

    # Holiday configuration
    exclude_holidays: bool = Field(
        True,
        description="Exclude holidays from attendance calculation",
    )
    auto_import_holidays: bool = Field(
        default=True,
        description="Automatically import regional holidays",
    )

    # Half-day handling
    half_day_weight: Decimal = Field(
        Decimal("0.5"),
        ge=Decimal("0"),
        le=Decimal("1"),
        description="Weight for half-day attendance (0.5 = half, 1.0 = full)",
    )

    # Late entry penalties
    apply_late_penalty: bool = Field(
        default=False,
        description="Apply penalty for late entries",
    )
    late_penalty_after_count: int = Field(
        default=5,
        ge=1,
        description="Apply penalty after N late entries in month",
    )
    late_penalty_type: str = Field(
        default="warning",
        pattern=r"^(warning|deduction|fine)$",
        description="Type of penalty for excessive late entries",
    )
    late_penalty_deduction_percentage: Union[Decimal, None] = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Percentage to deduct for late penalty",
    )

    # Rounding rules
    round_percentage_to: int = Field(
        2,
        ge=0,
        le=4,
        description="Decimal places for percentage rounding",
    )
    rounding_mode: str = Field(
        "standard",
        pattern=r"^(up|down|standard)$",
        description="Rounding mode for attendance percentage",
    )

    @field_validator("weekend_days")
    @classmethod
    def validate_weekend_days(cls, v: List[str]) -> List[str]:
        """Validate weekend days are valid day names."""
        valid_days = {
            "Monday",
            "Tuesday",
            "Wednesday",
            "Thursday",
            "Friday",
            "Saturday",
            "Sunday",
        }
        for day in v:
            if day not in valid_days:
                raise ValueError(f"Invalid day name: {day}")
        return v

    @model_validator(mode="after")
    def validate_config_consistency(self) -> "PolicyConfig":
        """Validate configuration consistency."""
        # Can't count leave as both absent and present
        if self.count_leave_as_absent and self.count_leave_as_present:
            raise ValueError(
                "Leave cannot be counted as both absent and present"
            )

        # Custom period validation
        if self.calculation_period == "custom" and self.custom_period_days is None:
            raise ValueError(
                "custom_period_days is required when calculation_period is 'custom'"
            )

        # Late penalty validation
        if self.apply_late_penalty:
            if self.late_penalty_type == "deduction":
                if self.late_penalty_deduction_percentage is None:
                    raise ValueError(
                        "late_penalty_deduction_percentage is required for 'deduction' penalty type"
                    )

        return self


class PolicyUpdate(BaseUpdateSchema):
    """
    Update attendance policy with partial fields.
    
    All fields are optional for flexible policy updates.
    """

    minimum_attendance_percentage: Union[Decimal, None] = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Updated minimum attendance percentage",
    )
    late_entry_threshold_minutes: Union[int, None] = Field(
        None,
        ge=0,
        le=240,
        description="Updated late entry threshold",
    )
    grace_period_minutes: Union[int, None] = Field(
        None,
        ge=0,
        le=30,
        description="Updated grace period",
    )
    grace_days_per_month: Union[int, None] = Field(
        None,
        ge=0,
        le=31,
        description="Updated grace days per month",
    )
    consecutive_absence_alert_days: Union[int, None] = Field(
        None,
        ge=1,
        le=30,
        description="Updated consecutive absence alert threshold",
    )
    notify_guardian_on_absence: Union[bool, None] = None
    notify_admin_on_low_attendance: Union[bool, None] = None
    notify_student_on_low_attendance: Union[bool, None] = None
    low_attendance_threshold: Union[Decimal, None] = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Updated low attendance threshold",
    )
    auto_mark_absent_enabled: Union[bool, None] = None
    auto_mark_absent_after_time: Union[time, None] = None
    track_weekend_attendance: Union[bool, None] = None
    track_holiday_attendance: Union[bool, None] = None
    is_active: Union[bool, None] = None
    effective_from: Union[Date, None] = None
    effective_until: Union[Date, None] = None

    @field_validator(
        "minimum_attendance_percentage",
        "low_attendance_threshold",
    )
    @classmethod
    def round_percentage(cls, v: Union[Decimal, None]) -> Union[Decimal, None]:
        """Round percentage to 2 decimal places."""
        return round(v, 2) if v is not None else None

    @model_validator(mode="after")
    def validate_update_consistency(self) -> "PolicyUpdate":
        """Validate update consistency when related fields are both provided."""
        # Validate thresholds if both are provided
        if (
            self.low_attendance_threshold is not None
            and self.minimum_attendance_percentage is not None
        ):
            if self.low_attendance_threshold > self.minimum_attendance_percentage:
                raise ValueError(
                    "low_attendance_threshold should be less than minimum_attendance_percentage"
                )

        # Validate effective dates if both provided
        if self.effective_from and self.effective_until:
            if self.effective_until < self.effective_from:
                raise ValueError(
                    "effective_until must be after effective_from"
                )

        return self


class PolicyViolation(BaseSchema):
    """
    Attendance policy violation record.
    
    Tracks instances where students violate attendance policies
    with details for corrective action.
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

    # Violation details
    violation_type: str = Field(
        ...,
        pattern=r"^(low_attendance|consecutive_absences|excessive_late_entries|unauthorized_absence)$",
        description="Type of policy violation",
    )
    severity: str = Field(
        ...,
        pattern=r"^(low|medium|high|critical)$",
        description="Violation severity level",
    )

    # Metrics
    current_attendance_percentage: Union[Decimal, None] = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Current attendance percentage",
    )
    required_attendance_percentage: Union[Decimal, None] = Field(
        None,
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Required attendance percentage",
    )
    consecutive_absences: Union[int, None] = Field(
        None,
        ge=0,
        description="Number of consecutive absences",
    )
    late_entries_this_month: Union[int, None] = Field(
        None,
        ge=0,
        description="Late entries in current month",
    )
    total_absences_this_month: Union[int, None] = Field(
        None,
        ge=0,
        description="Total absences in current month",
    )

    # Violation tracking
    violation_date: Date = Field(
        ...,
        description="Date when violation was detected",
    )
    first_violation_date: Union[Date, None] = Field(
        None,
        description="Date of first related violation",
    )

    # Actions taken
    guardian_notified: bool = Field(
        ...,
        description="Guardian notification sent",
    )
    guardian_notified_at: Union[datetime, None] = Field(
        None,
        description="Guardian notification timestamp",
    )
    admin_notified: bool = Field(
        ...,
        description="Admin notification sent",
    )
    admin_notified_at: Union[datetime, None] = Field(
        None,
        description="Admin notification timestamp",
    )
    student_notified: bool = Field(
        default=False,
        description="Student notification sent",
    )
    warning_issued: bool = Field(
        ...,
        description="Formal warning issued",
    )
    warning_issued_at: Union[datetime, None] = Field(
        None,
        description="Warning issue timestamp",
    )

    # Resolution
    resolved: bool = Field(
        default=False,
        description="Whether violation has been resolved",
    )
    resolved_at: Union[datetime, None] = Field(
        None,
        description="Resolution timestamp",
    )
    resolution_notes: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Notes about how violation was resolved",
    )

    # Additional context
    notes: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Additional notes about violation",
    )
    action_plan: Union[str, None] = Field(
        None,
        max_length=1000,
        description="Planned corrective actions",
    )

    @field_validator("resolution_notes", "notes", "action_plan")
    @classmethod
    def validate_text_fields(cls, v: Union[str, None]) -> Union[str, None]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_violation_data(self) -> "PolicyViolation":
        """
        Validate violation data consistency.
        
        Ensures violation-specific metrics are provided based on type.
        """
        # Validate violation-specific requirements
        if self.violation_type == "low_attendance":
            if self.current_attendance_percentage is None:
                raise ValueError(
                    "current_attendance_percentage is required for low_attendance violation"
                )
            if self.required_attendance_percentage is None:
                raise ValueError(
                    "required_attendance_percentage is required for low_attendance violation"
                )

        if self.violation_type == "consecutive_absences":
            if self.consecutive_absences is None:
                raise ValueError(
                    "consecutive_absences is required for consecutive_absences violation"
                )

        if self.violation_type == "excessive_late_entries":
            if self.late_entries_this_month is None:
                raise ValueError(
                    "late_entries_this_month is required for excessive_late_entries violation"
                )

        # Resolution validation
        if self.resolved and self.resolved_at is None:
            raise ValueError(
                "resolved_at timestamp is required when violation is resolved"
            )

        # Notification timestamps
        if self.guardian_notified and self.guardian_notified_at is None:
            raise ValueError(
                "guardian_notified_at is required when guardian_notified is True"
            )

        if self.warning_issued and self.warning_issued_at is None:
            raise ValueError(
                "warning_issued_at is required when warning_issued is True"
            )

        return self
# --- File: app/schemas/attendance/attendance_alert.py ---
"""
Attendance alert schemas for proactive monitoring.

Provides alert generation, configuration, and management schemas
for identifying and responding to attendance issues.
"""

from __future__ import annotations

from datetime import date as Date, datetime, time
from decimal import Decimal
from typing import Dict, List, Optional, Any

from pydantic import Field, field_validator, model_validator
from pydantic.types import UUID4 as UUID

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema

__all__ = [
    "AttendanceAlert",
    "AlertConfig",
    "AlertTrigger",
    "AlertAcknowledgment",
    "AlertList",
    "AlertSummary",
]


class AttendanceAlert(BaseResponseSchema):
    """
    Attendance alert record with tracking and resolution.
    
    Represents an automatically or manually triggered alert
    for attendance-related issues.
    """

    alert_id: UUID = Field(
        ...,
        description="Alert unique identifier",
    )
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

    # Alert classification
    alert_type: str = Field(
        ...,
        pattern=r"^(low_attendance|consecutive_absences|late_entry|irregular_pattern|policy_violation)$",
        description="Type of alert",
    )
    severity: str = Field(
        ...,
        pattern=r"^(low|medium|high|critical)$",
        description="Alert severity level",
    )
    category: str = Field(
        default="attendance",
        pattern=r"^(attendance|behavior|policy|system)$",
        description="Alert category",
    )

    # Alert content
    message: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Alert message for display",
    )
    details: Dict[str, Any] = Field(
        ...,
        description="Alert-specific details (JSON)",
    )
    recommendation: Optional[str] = Field(
        None,
        max_length=500,
        description="Recommended action to resolve alert",
    )

    # Trigger information
    triggered_at: datetime = Field(
        ...,
        description="Alert trigger timestamp",
    )
    triggered_by_rule: Optional[str] = Field(
        None,
        description="Name of rule that triggered alert",
    )
    auto_generated: bool = Field(
        default=True,
        description="Whether alert was auto-generated",
    )
    manual_trigger_by: Optional[UUID] = Field(
        None,
        description="User ID if manually triggered",
    )

    # Acknowledgment
    acknowledged: bool = Field(
        False,
        description="Whether alert has been acknowledged",
    )
    acknowledged_by: Optional[UUID] = Field(
        None,
        description="User ID who acknowledged",
    )
    acknowledged_by_name: Optional[str] = Field(
        None,
        description="Name of user who acknowledged",
    )
    acknowledged_at: Optional[datetime] = Field(
        None,
        description="Acknowledgment timestamp",
    )
    acknowledgment_notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Notes added during acknowledgment",
    )

    # Actions and resolution
    actions_taken: List[str] = Field(
        default_factory=list,
        description="List of actions taken in response",
    )
    assigned_to: Optional[UUID] = Field(
        None,
        description="User ID assigned to handle alert",
    )
    assigned_to_name: Optional[str] = Field(
        None,
        description="Name of assigned user",
    )
    resolved: bool = Field(
        False,
        description="Whether alert has been resolved",
    )
    resolved_at: Optional[datetime] = Field(
        None,
        description="Resolution timestamp",
    )
    resolved_by: Optional[UUID] = Field(
        None,
        description="User ID who resolved",
    )
    resolution_notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Resolution details",
    )

    # Escalation
    escalated: bool = Field(
        default=False,
        description="Whether alert has been escalated",
    )
    escalated_at: Optional[datetime] = Field(
        None,
        description="Escalation timestamp",
    )
    escalation_level: int = Field(
        default=0,
        ge=0,
        le=5,
        description="Current escalation level",
    )

    # Notification tracking
    notifications_sent: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Record of notifications sent",
    )

    @field_validator("message", "recommendation", "acknowledgment_notes", "resolution_notes")
    @classmethod
    def validate_text_fields(cls, v: Optional[str]) -> Optional[str]:
        """Normalize text fields."""
        if v is not None:
            v = v.strip()
            return v if v else None
        return None

    @model_validator(mode="after")
    def validate_alert_status(self) -> "AttendanceAlert":
        """
        Validate alert status consistency.
        
        Ensures timestamps and user IDs are provided when status flags are set.
        """
        if self.acknowledged:
            if self.acknowledged_by is None:
                raise ValueError(
                    "acknowledged_by is required when alert is acknowledged"
                )
            if self.acknowledged_at is None:
                raise ValueError(
                    "acknowledged_at is required when alert is acknowledged"
                )

        if self.resolved:
            if self.resolved_at is None:
                raise ValueError(
                    "resolved_at is required when alert is resolved"
                )
            # Resolved alerts should be acknowledged first
            if not self.acknowledged:
                raise ValueError(
                    "Alert must be acknowledged before being resolved"
                )

        if self.escalated and self.escalated_at is None:
            raise ValueError(
                "escalated_at is required when alert is escalated"
            )

        if not self.auto_generated and self.manual_trigger_by is None:
            raise ValueError(
                "manual_trigger_by is required for manually triggered alerts"
            )

        return self


class AlertConfig(BaseSchema):
    """
    Alert configuration for attendance monitoring.
    
    Defines rules and thresholds for automatic alert generation
    and notification preferences.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )

    # Low attendance alerts
    enable_low_attendance_alerts: bool = Field(
        True,
        description="Enable low attendance alerts",
    )
    low_attendance_threshold: Decimal = Field(
        Decimal("75.00"),
        ge=Decimal("0"),
        le=Decimal("100"),
        description="Attendance percentage threshold for alerts",
    )
    low_attendance_check_period: str = Field(
        "monthly",
        pattern=r"^(weekly|monthly|semester)$",
        description="Period for low attendance calculation",
    )

    # Consecutive absence alerts
    enable_consecutive_absence_alerts: bool = Field(
        True,
        description="Enable consecutive absence alerts",
    )
    consecutive_absence_threshold: int = Field(
        3,
        ge=1,
        le=30,
        description="Alert after N consecutive absences",
    )

    # Late entry alerts
    enable_late_entry_alerts: bool = Field(
        True,
        description="Enable late entry alerts",
    )
    late_entry_count_threshold: int = Field(
        5,
        ge=1,
        le=31,
        description="Alert after N late entries in evaluation period",
    )
    late_entry_evaluation_period: str = Field(
        "monthly",
        pattern=r"^(weekly|monthly)$",
        description="Period for late entry counting",
    )

    # Pattern detection
    enable_pattern_detection: bool = Field(
        False,
        description="Enable irregular pattern detection (AI/ML based)",
    )
    pattern_sensitivity: str = Field(
        "medium",
        pattern=r"^(low|medium|high)$",
        description="Sensitivity for pattern detection",
    )

    # Absence spike detection
    enable_absence_spike_alerts: bool = Field(
        default=True,
        description="Alert on sudden increase in absences",
    )
    absence_spike_threshold: int = Field(
        default=3,
        ge=2,
        description="Alert when absences increase by N in short period",
    )

    # Notification preferences
    notify_supervisor: bool = Field(
        True,
        description="Send alerts to supervisor",
    )
    notify_admin: bool = Field(
        True,
        description="Send alerts to admin",
    )
    notify_guardian: bool = Field(
        True,
        description="Send alerts to guardian",
    )
    notify_student: bool = Field(
        True,
        description="Send alerts to student",
    )

    # Notification channels
    notification_channels: List[str] = Field(
        default_factory=lambda: ["email", "push"],
        description="Notification delivery channels",
    )

    # Escalation settings
    auto_escalate_enabled: bool = Field(
        default=True,
        description="Enable automatic alert escalation",
    )
    auto_escalate_after_days: int = Field(
        7,
        ge=1,
        le=30,
        description="Auto-escalate unacknowledged alerts after N days",
    )
    max_escalation_level: int = Field(
        default=3,
        ge=1,
        le=5,
        description="Maximum escalation level",
    )

    # Alert suppression
    suppress_duplicate_alerts: bool = Field(
        default=True,
        description="Suppress duplicate alerts within time window",
    )
    duplicate_suppression_hours: int = Field(
        default=24,
        ge=1,
        le=168,
        description="Hours to suppress duplicate alerts",
    )

    # Working hours
    alert_only_during_hours: bool = Field(
        default=False,
        description="Only send alerts during specified hours",
    )
    alert_start_time: Optional[time] = Field(
        None,
        description="Start time for alert notifications",
    )
    alert_end_time: Optional[time] = Field(
        None,
        description="End time for alert notifications",
    )

    @field_validator("notification_channels")
    @classmethod
    def validate_channels(cls, v: List[str]) -> List[str]:
        """Validate notification channels are supported."""
        valid_channels = {"email", "sms", "push", "whatsapp"}
        for channel in v:
            if channel not in valid_channels:
                raise ValueError(f"Invalid notification channel: {channel}")
        return v

    @model_validator(mode="after")
    def validate_config_consistency(self) -> "AlertConfig":
        """Validate configuration consistency."""
        # Validate alert hours if enabled
        if self.alert_only_during_hours:
            if self.alert_start_time is None or self.alert_end_time is None:
                raise ValueError(
                    "alert_start_time and alert_end_time are required when alert_only_during_hours is True"
                )

        # At least one notification recipient should be enabled
        if not any([
            self.notify_supervisor,
            self.notify_admin,
            self.notify_guardian,
            self.notify_student,
        ]):
            raise ValueError(
                "At least one notification recipient must be enabled"
            )

        return self


class AlertTrigger(BaseCreateSchema):
    """
    Manual alert trigger request.
    
    Allows authorized users to manually create alerts for
    specific attendance concerns.
    """

    student_id: UUID = Field(
        ...,
        description="Student unique identifier",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    alert_type: str = Field(
        ...,
        pattern=r"^(low_attendance|consecutive_absences|late_entry|irregular_pattern|custom)$",
        description="Type of alert to trigger",
    )
    severity: str = Field(
        "medium",
        pattern=r"^(low|medium|high|critical)$",
        description="Alert severity level",
    )
    custom_message: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Custom alert message",
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional alert details",
    )
    assign_to: Optional[UUID] = Field(
        None,
        description="User ID to assign alert to",
    )
    notify_immediately: bool = Field(
        default=True,
        description="Send notifications immediately",
    )
    triggered_by: UUID = Field(
        ...,
        description="User ID triggering the alert",
    )

    @field_validator("custom_message")
    @classmethod
    def validate_message(cls, v: str) -> str:
        """Validate and normalize message."""
        v = v.strip()
        if len(v) < 10:
            raise ValueError("Message must be at least 10 characters")
        return v


class AlertAcknowledgment(BaseCreateSchema):
    """
    Acknowledge attendance alert.
    
    Records acknowledgment of an alert with action details.
    """

    alert_id: UUID = Field(
        ...,
        description="Alert unique identifier",
    )
    acknowledged_by: UUID = Field(
        ...,
        description="User ID acknowledging the alert",
    )
    action_taken: str = Field(
        ...,
        min_length=10,
        max_length=500,
        description="Description of action taken",
    )
    assign_to: Optional[UUID] = Field(
        None,
        description="User ID to assign for follow-up",
    )
    mark_resolved: bool = Field(
        default=False,
        description="Mark alert as resolved",
    )
    additional_notes: Optional[str] = Field(
        None,
        max_length=1000,
        description="Additional notes",
    )

    @field_validator("action_taken", "additional_notes")
    @classmethod
    def validate_text_fields(cls, v: Optional[str], info) -> Optional[str]:
        """Normalize and validate text fields."""
        if v is None:
            return None
        v = v.strip() or None
        if v and info.field_name == "action_taken" and len(v) < 10:
            raise ValueError("action_taken must be at least 10 characters")
        return v


class AlertList(BaseSchema):
    """
    List of alerts with summary statistics.
    
    Provides paginated alert list with aggregate metrics.
    """

    hostel_id: Optional[UUID] = Field(
        None,
        description="Hostel filter (if applicable)",
    )
    student_id: Optional[UUID] = Field(
        None,
        description="Student filter (if applicable)",
    )
    date_from: Optional[Date] = Field(
        None,
        description="Filter alerts from this Date",
    )
    date_to: Optional[Date] = Field(
        None,
        description="Filter alerts to this Date",
    )

    # Summary statistics
    total_alerts: int = Field(
        ...,
        ge=0,
        description="Total number of alerts",
    )
    unacknowledged_alerts: int = Field(
        ...,
        ge=0,
        description="Number of unacknowledged alerts",
    )
    unresolved_alerts: int = Field(
        ...,
        ge=0,
        description="Number of unresolved alerts",
    )
    critical_alerts: int = Field(
        ...,
        ge=0,
        description="Number of critical severity alerts",
    )
    escalated_alerts: int = Field(
        default=0,
        ge=0,
        description="Number of escalated alerts",
    )

    # Alert breakdown by type
    alerts_by_type: Dict[str, int] = Field(
        default_factory=dict,
        description="Alert counts by type",
    )

    # Alert breakdown by severity
    alerts_by_severity: Dict[str, int] = Field(
        default_factory=dict,
        description="Alert counts by severity",
    )

    # Alert list
    alerts: List[AttendanceAlert] = Field(
        ...,
        description="List of alert records",
    )


class AlertSummary(BaseSchema):
    """
    Alert summary for dashboard display.
    
    Provides high-level overview of alerts for monitoring dashboards.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel unique identifier",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    period_start: Date = Field(
        ...,
        description="Summary period start Date",
    )
    period_end: Date = Field(
        ...,
        description="Summary period end Date",
    )

    # Overall counts
    total_alerts: int = Field(
        ...,
        ge=0,
        description="Total alerts in period",
    )
    new_alerts_today: int = Field(
        default=0,
        ge=0,
        description="Alerts triggered today",
    )

    # By type
    low_attendance_alerts: int = Field(
        ...,
        ge=0,
        description="Low attendance alerts",
    )
    consecutive_absence_alerts: int = Field(
        ...,
        ge=0,
        description="Consecutive absence alerts",
    )
    late_entry_alerts: int = Field(
        ...,
        ge=0,
        description="Late entry alerts",
    )
    pattern_alerts: int = Field(
        ...,
        ge=0,
        description="Irregular pattern alerts",
    )
    policy_violation_alerts: int = Field(
        default=0,
        ge=0,
        description="Policy violation alerts",
    )

    # By severity
    critical_count: int = Field(
        ...,
        ge=0,
        description="Critical alerts",
    )
    high_count: int = Field(
        ...,
        ge=0,
        description="High severity alerts",
    )
    medium_count: int = Field(
        ...,
        ge=0,
        description="Medium severity alerts",
    )
    low_count: int = Field(
        ...,
        ge=0,
        description="Low severity alerts",
    )

    # Status breakdown
    acknowledged_count: int = Field(
        ...,
        ge=0,
        description="Acknowledged alerts",
    )
    resolved_count: int = Field(
        ...,
        ge=0,
        description="Resolved alerts",
    )
    pending_count: int = Field(
        ...,
        ge=0,
        description="Pending/unacknowledged alerts",
    )
    escalated_count: int = Field(
        default=0,
        ge=0,
        description="Escalated alerts",
    )

    # Performance metrics
    average_resolution_time_hours: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Average time to resolve alerts (hours)",
    )
    average_acknowledgment_time_hours: Optional[Decimal] = Field(
        None,
        ge=Decimal("0"),
        description="Average time to acknowledge alerts (hours)",
    )

    # Student impact
    students_with_alerts: int = Field(
        default=0,
        ge=0,
        description="Number of students with active alerts",
    )
    students_with_critical_alerts: int = Field(
        default=0,
        ge=0,
        description="Students with critical alerts",
    )

    # Trend indicator
    alert_trend: str = Field(
        default="stable",
        pattern=r"^(increasing|decreasing|stable)$",
        description="Alert volume trend",
    )

    @field_validator("period_end")
    @classmethod
    def validate_period(cls, v: Date, info) -> Date:
        """Validate period dates."""
        # In Pydantic v2, we access data through info.data
        if info.data.get("period_start"):
            if v < info.data["period_start"]:
                raise ValueError("period_end must be after period_start")
        return v
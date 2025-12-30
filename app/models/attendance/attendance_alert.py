# --- File: app/models/attendance/attendance_alert.py ---
"""
Attendance alert models for proactive monitoring.

Provides alert generation, configuration, and management for
identifying and responding to attendance issues with escalation support.
"""

from datetime import date, datetime, time
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel

__all__ = [
    "AttendanceAlert",
    "AlertConfiguration",
    "AlertNotification",
]


class AttendanceAlert(TimestampModel, BaseModel):
    """
    Attendance alert with tracking and resolution.
    
    Represents automatically or manually triggered alerts for
    attendance-related issues with complete lifecycle management.
    """

    __tablename__ = "attendance_alerts"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )

    # Foreign keys
    hostel_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    manual_trigger_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Alert classification
    alert_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="attendance",
    )

    # Alert content
    message: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    details: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    recommendation: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
    )

    # Trigger information
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
    )
    triggered_by_rule: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
    )
    auto_generated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Acknowledgment
    acknowledged: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    acknowledged_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    acknowledgment_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Actions and resolution
    actions_taken: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )
    assigned_to: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resolved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    resolved_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Escalation
    escalated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    escalated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    escalation_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Notification tracking
    notifications_sent: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="attendance_alerts",
        lazy="joined",
    )
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="attendance_alerts",
        lazy="joined",
    )
    manual_trigger_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[manual_trigger_by],
        lazy="select",
    )
    acknowledged_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[acknowledged_by],
        lazy="select",
    )
    assigned_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[assigned_to],
        lazy="select",
    )
    resolved_by_user: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[resolved_by],
        lazy="select",
    )
    alert_notifications: Mapped[list["AlertNotification"]] = relationship(
        "AlertNotification",
        back_populates="alert",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "escalation_level >= 0 AND escalation_level <= 5",
            name="ck_alert_escalation_level_range",
        ),
        Index(
            "idx_alert_hostel_student",
            "hostel_id",
            "student_id",
        ),
        Index(
            "idx_alert_status",
            "acknowledged",
            "resolved",
        ),
        Index(
            "idx_alert_type_severity",
            "alert_type",
            "severity",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AttendanceAlert(id={self.id}, student_id={self.student_id}, "
            f"type={self.alert_type}, severity={self.severity})>"
        )


class AlertConfiguration(TimestampModel, BaseModel):
    """
    Alert configuration for attendance monitoring.
    
    Defines rules and thresholds for automatic alert generation
    and notification preferences per hostel.
    """

    __tablename__ = "alert_configurations"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )

    # Foreign key
    hostel_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )

    # Low attendance alerts
    enable_low_attendance_alerts: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    low_attendance_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=75,
    )
    low_attendance_check_period: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="monthly",
    )

    # Consecutive absence alerts
    enable_consecutive_absence_alerts: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    consecutive_absence_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )

    # Late entry alerts
    enable_late_entry_alerts: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    late_entry_count_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
    )
    late_entry_evaluation_period: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="monthly",
    )

    # Pattern detection
    enable_pattern_detection: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    pattern_sensitivity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="medium",
    )

    # Absence spike detection
    enable_absence_spike_alerts: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    absence_spike_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )

    # Notification preferences
    notify_supervisor: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    notify_admin: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    notify_guardian: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    notify_student: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Notification channels
    notification_channels: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=lambda: ["email", "push"],
    )

    # Escalation settings
    auto_escalate_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    auto_escalate_after_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=7,
    )
    max_escalation_level: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )

    # Alert suppression
    suppress_duplicate_alerts: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    duplicate_suppression_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=24,
    )

    # Working hours
    alert_only_during_hours: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    alert_start_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )
    alert_end_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="alert_configuration",
        lazy="joined",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "low_attendance_threshold >= 0 AND low_attendance_threshold <= 100",
            name="ck_alert_config_low_threshold",
        ),
        CheckConstraint(
            "consecutive_absence_threshold >= 1 AND consecutive_absence_threshold <= 30",
            name="ck_alert_config_consecutive_threshold",
        ),
        CheckConstraint(
            "late_entry_count_threshold >= 1 AND late_entry_count_threshold <= 31",
            name="ck_alert_config_late_threshold",
        ),
        CheckConstraint(
            "auto_escalate_after_days >= 1 AND auto_escalate_after_days <= 30",
            name="ck_alert_config_escalate_days",
        ),
        CheckConstraint(
            "max_escalation_level >= 1 AND max_escalation_level <= 5",
            name="ck_alert_config_max_escalation",
        ),
        CheckConstraint(
            "duplicate_suppression_hours >= 1 AND duplicate_suppression_hours <= 168",
            name="ck_alert_config_suppression_hours",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AlertConfiguration(id={self.id}, hostel_id={self.hostel_id})>"
        )


class AlertNotification(TimestampModel, BaseModel):
    """
    Alert notification delivery tracking.
    
    Tracks individual notification deliveries for alerts across
    multiple channels with delivery status and response tracking.
    """

    __tablename__ = "alert_notifications"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )

    # Foreign keys
    alert_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attendance_alerts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Notification details
    channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    recipient_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )

    # Delivery tracking
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
    )
    delivered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    delivered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    read: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    read_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Failure tracking
    failed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # Relationships
    alert: Mapped["AttendanceAlert"] = relationship(
        "AttendanceAlert",
        back_populates="alert_notifications",
        lazy="joined",
    )
    recipient: Mapped["User"] = relationship(
        "User",
        lazy="select",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "retry_count >= 0",
            name="ck_alert_notification_retry_count",
        ),
        Index(
            "idx_alert_notification_delivery",
            "alert_id",
            "delivered",
            "read",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AlertNotification(id={self.id}, alert_id={self.alert_id}, "
            f"channel={self.channel}, delivered={self.delivered})>"
        )
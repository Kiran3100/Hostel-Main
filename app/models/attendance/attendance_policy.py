# --- File: app/models/attendance/attendance_policy.py ---
"""
Attendance policy configuration models.

Defines policy rules, thresholds, and violation tracking for
attendance management with comprehensive validation and enforcement.
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    Time,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import BaseModel, TimestampModel

__all__ = [
    "AttendancePolicy",
    "PolicyViolation",
    "PolicyException",
]


class AttendancePolicy(TimestampModel, BaseModel):
    """
    Hostel-specific attendance policy configuration.
    
    Defines rules, thresholds, and automated behaviors for
    attendance tracking and enforcement including notifications
    and escalation settings.
    """

    __tablename__ = "attendance_policies"

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

    # Minimum requirements
    minimum_attendance_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("75.00"),
    )

    # Late entry configuration
    late_entry_threshold_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=15,
    )
    grace_period_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=5,
    )
    grace_days_per_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )

    # Absence alerts
    consecutive_absence_alert_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )
    total_absence_alert_threshold: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=10,
    )

    # Notification settings
    notify_guardian_on_absence: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    notify_admin_on_low_attendance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    notify_student_on_low_attendance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    low_attendance_threshold: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("75.00"),
    )

    # Auto-marking configuration
    auto_mark_absent_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    auto_mark_absent_after_time: Mapped[Optional[time]] = mapped_column(
        Time,
        nullable=True,
    )

    # Weekend and holiday handling
    track_weekend_attendance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    track_holiday_attendance: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    # Calculation settings
    calculation_period: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="monthly",
    )
    include_weekends: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    exclude_holidays: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    # Leave handling
    count_leave_as_absent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    count_leave_as_present: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    max_leaves_per_month: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=3,
    )

    # Policy status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    effective_from: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )
    effective_until: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    # Additional configuration (stored as JSON for flexibility)
    extended_config: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="attendance_policy",
        lazy="joined",
    )
    violations: Mapped[list["PolicyViolation"]] = relationship(
        "PolicyViolation",
        back_populates="policy",
        cascade="all, delete-orphan",
        lazy="select",
    )
    exceptions: Mapped[list["PolicyException"]] = relationship(
        "PolicyException",
        back_populates="policy",
        cascade="all, delete-orphan",
        lazy="select",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "minimum_attendance_percentage >= 0 AND minimum_attendance_percentage <= 100",
            name="ck_policy_minimum_attendance_range",
        ),
        CheckConstraint(
            "low_attendance_threshold >= 0 AND low_attendance_threshold <= 100",
            name="ck_policy_low_threshold_range",
        ),
        CheckConstraint(
            "late_entry_threshold_minutes >= 0 AND late_entry_threshold_minutes <= 240",
            name="ck_policy_late_threshold_range",
        ),
        CheckConstraint(
            "grace_period_minutes >= 0 AND grace_period_minutes <= 30",
            name="ck_policy_grace_period_range",
        ),
        CheckConstraint(
            "grace_days_per_month >= 0 AND grace_days_per_month <= 31",
            name="ck_policy_grace_days_range",
        ),
        CheckConstraint(
            "consecutive_absence_alert_days >= 1 AND consecutive_absence_alert_days <= 30",
            name="ck_policy_consecutive_absence_range",
        ),
        CheckConstraint(
            "max_leaves_per_month >= 0 AND max_leaves_per_month <= 31",
            name="ck_policy_max_leaves_range",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<AttendancePolicy(id={self.id}, hostel_id={self.hostel_id}, "
            f"min_percentage={self.minimum_attendance_percentage})>"
        )


class PolicyViolation(TimestampModel, BaseModel):
    """
    Attendance policy violation tracking.
    
    Records instances where students violate attendance policies
    with details for corrective action and notification management.
    """

    __tablename__ = "policy_violations"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )

    # Foreign keys
    policy_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attendance_policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Violation details
    violation_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        index=True,
    )

    # Metrics
    current_attendance_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    required_attendance_percentage: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(5, 2),
        nullable=True,
    )
    consecutive_absences: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    late_entries_this_month: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )
    total_absences_this_month: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
    )

    # Violation tracking
    violation_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    first_violation_date: Mapped[Optional[date]] = mapped_column(
        Date,
        nullable=True,
    )

    # Notification status
    guardian_notified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    guardian_notified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    admin_notified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    admin_notified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    student_notified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    warning_issued: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    warning_issued_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Resolution
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
    resolution_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Additional context
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )
    action_plan: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    policy: Mapped["AttendancePolicy"] = relationship(
        "AttendancePolicy",
        back_populates="violations",
        lazy="joined",
    )
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="policy_violations",
        lazy="joined",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "current_attendance_percentage >= 0 AND current_attendance_percentage <= 100",
            name="ck_violation_current_percentage_range",
        ),
        CheckConstraint(
            "required_attendance_percentage >= 0 AND required_attendance_percentage <= 100",
            name="ck_violation_required_percentage_range",
        ),
        CheckConstraint(
            "consecutive_absences >= 0",
            name="ck_violation_consecutive_absences",
        ),
        Index(
            "idx_violation_student_date",
            "student_id",
            "violation_date",
        ),
        Index(
            "idx_violation_type_severity",
            "violation_type",
            "severity",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PolicyViolation(id={self.id}, student_id={self.student_id}, "
            f"type={self.violation_type}, date={self.violation_date})>"
        )


class PolicyException(TimestampModel, BaseModel):
    """
    Temporary attendance policy exceptions.
    
    Allows temporary exemptions from attendance policies for
    specific students with approval workflow and expiration.
    """

    __tablename__ = "policy_exceptions"

    # Primary key
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
        index=True,
    )

    # Foreign keys
    policy_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("attendance_policies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=False,
    )
    approved_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Exception details
    exception_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Validity period
    valid_from: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )
    valid_until: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        index=True,
    )

    # Approval status
    is_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
    )
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    approval_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Exception status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )
    revoked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    revoked_by: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    revocation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
    )

    # Relationships
    policy: Mapped["AttendancePolicy"] = relationship(
        "AttendancePolicy",
        back_populates="exceptions",
        lazy="joined",
    )
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="policy_exceptions",
        lazy="joined",
    )
    creator: Mapped["User"] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="select",
    )
    approver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="select",
    )
    revoker: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[revoked_by],
        lazy="select",
    )

    # Constraints
    __table_args__ = (
        CheckConstraint(
            "valid_until >= valid_from",
            name="ck_exception_valid_dates",
        ),
        Index(
            "idx_exception_student_validity",
            "student_id",
            "valid_from",
            "valid_until",
        ),
        Index(
            "idx_exception_active_approved",
            "is_active",
            "is_approved",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<PolicyException(id={self.id}, student_id={self.student_id}, "
            f"type={self.exception_type}, valid={self.valid_from} to {self.valid_until})>"
        )
# --- File: C:\Hostel-Main\app\models\leave\leave_balance.py ---
"""
Leave balance and quota management database models.

Provides SQLAlchemy models for tracking leave entitlements,
usage, and remaining balance with validation.
"""

from datetime import date as Date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date as SQLDate,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from app.models.base.base_model import BaseModel, TimestampModel
from app.models.base.mixins import UUIDMixin
from app.models.common.enums import LeaveType

if TYPE_CHECKING:
    from app.models.student.student import Student
    from app.models.hostel.hostel import Hostel
    from app.models.leave.leave_type import LeaveTypeConfig

__all__ = [
    "LeaveBalance",
    "LeaveQuota",
    "LeaveUsage",
    "LeaveCarryForward",
    "LeaveAdjustment",
]


class LeaveBalance(BaseModel, TimestampModel, UUIDMixin):
    """
    Current leave balance for students.
    
    Tracks allocated, used, pending, and remaining leave days
    for each leave type per student.
    """
    
    __tablename__ = "leave_balances"
    __table_args__ = (
        # Ensure unique balance record per student, leave type, and period
        UniqueConstraint(
            "student_id",
            "leave_type",
            "academic_year_start",
            name="uq_leave_balance_student_type_year"
        ),
        # Ensure balance calculations are non-negative
        CheckConstraint(
            "allocated_days >= 0",
            name="ck_leave_balance_allocated_non_negative"
        ),
        CheckConstraint(
            "used_days >= 0",
            name="ck_leave_balance_used_non_negative"
        ),
        CheckConstraint(
            "pending_days >= 0",
            name="ck_leave_balance_pending_non_negative"
        ),
        CheckConstraint(
            "remaining_days >= 0",
            name="ck_leave_balance_remaining_non_negative"
        ),
        # Ensure balance equation: remaining = allocated + carry_forward - used - pending
        CheckConstraint(
            "remaining_days = allocated_days + carry_forward_days - used_days - pending_days",
            name="ck_leave_balance_equation"
        ),
        # Indexes
        Index("ix_leave_balance_student_id", "student_id"),
        Index("ix_leave_balance_leave_type", "leave_type"),
        Index("ix_leave_balance_academic_year", "academic_year_start"),
        Index(
            "ix_leave_balance_student_type",
            "student_id",
            "leave_type"
        ),
        {"comment": "Leave balance tracking per student and leave type"}
    )

    # Student and leave type
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        comment="Student"
    )
    
    leave_type: Mapped[LeaveType] = mapped_column(
        Enum(LeaveType, name="leave_type_enum", create_type=True),
        nullable=False,
        comment="Type of leave"
    )

    # Academic period
    academic_year_start: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Academic year start date"
    )
    
    academic_year_end: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Academic year end date"
    )
    
    semester: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
        comment="Semester (if applicable)"
    )

    # Balance details
    allocated_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Days allocated for this period"
    )
    
    used_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Days already used/approved"
    )
    
    pending_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Days in pending applications"
    )
    
    remaining_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Days remaining available"
    )
    
    carry_forward_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Days carried forward from previous period"
    )

    # Usage tracking
    total_applications: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of leave applications"
    )
    
    approved_applications: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of approved applications"
    )
    
    rejected_applications: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of rejected applications"
    )

    # Limits
    max_consecutive_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum consecutive days allowed"
    )
    
    min_notice_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Minimum advance notice required (days)"
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether balance is active"
    )
    
    is_locked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether balance is locked (no new applications)"
    )
    
    locked_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for locking balance"
    )

    # Last calculation
    last_calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Last balance calculation timestamp"
    )
    
    next_reset_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Next balance reset date"
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="leave_balances",
        lazy="select"
    )
    
    usage_records: Mapped[list["LeaveUsage"]] = relationship(
        "LeaveUsage",
        back_populates="leave_balance",
        cascade="all, delete-orphan",
        lazy="select"
    )
    
    adjustments: Mapped[list["LeaveAdjustment"]] = relationship(
        "LeaveAdjustment",
        back_populates="leave_balance",
        cascade="all, delete-orphan",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveBalance(id={self.id}, student_id={self.student_id}, "
            f"type={self.leave_type.value}, remaining={self.remaining_days})>"
        )

    @property
    def usage_percentage(self) -> float:
        """Calculate usage percentage."""
        total_available = self.allocated_days + self.carry_forward_days
        if total_available == 0:
            return 0.0
        return round((self.used_days / total_available) * 100, 2)

    @property
    def is_exhausted(self) -> bool:
        """Check if balance is exhausted."""
        return self.remaining_days <= 0

    @property
    def utilization_status(self) -> str:
        """Get utilization status indicator."""
        usage_pct = self.usage_percentage
        
        if usage_pct >= 90:
            return "critical"
        elif usage_pct >= 75:
            return "high"
        elif usage_pct >= 50:
            return "moderate"
        elif usage_pct >= 25:
            return "low"
        else:
            return "minimal"


class LeaveQuota(BaseModel, TimestampModel, UUIDMixin):
    """
    Leave quota configuration per hostel.
    
    Defines leave entitlements and rules for different
    leave types within a hostel.
    """
    
    __tablename__ = "leave_quotas"
    __table_args__ = (
        UniqueConstraint(
            "hostel_id",
            "leave_type",
            "effective_from",
            name="uq_leave_quota_hostel_type_date"
        ),
        CheckConstraint(
            "annual_quota >= 0",
            name="ck_leave_quota_annual_non_negative"
        ),
        CheckConstraint(
            "max_consecutive_days > 0",
            name="ck_leave_quota_consecutive_positive"
        ),
        Index("ix_leave_quota_hostel_id", "hostel_id"),
        Index("ix_leave_quota_leave_type", "leave_type"),
        Index("ix_leave_quota_is_active", "is_active"),
        {"comment": "Leave quota configurations per hostel"}
    )

    # Hostel and leave type
    hostel_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        comment="Hostel"
    )
    
    leave_type: Mapped[LeaveType] = mapped_column(
        Enum(LeaveType, name="leave_type_enum", create_type=False),
        nullable=False,
        comment="Leave type"
    )

    # Quota details
    annual_quota: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Annual leave quota in days"
    )
    
    semester_quota: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Semester quota (if applicable)"
    )
    
    monthly_quota: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Monthly quota (if applicable)"
    )

    # Restrictions
    max_consecutive_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=30,
        comment="Maximum consecutive days allowed"
    )
    
    min_notice_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Minimum advance notice required (days)"
    )
    
    requires_document_after_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Requires supporting document after N days"
    )

    # Carry forward rules
    allow_carry_forward: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Allow unused quota to carry forward"
    )
    
    carry_forward_max_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Maximum days that can be carried forward"
    )
    
    carry_forward_expiry_months: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Months after which carried forward days expire"
    )

    # Approval requirements
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether leave type requires approval"
    )
    
    auto_approve_upto_days: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Auto-approve leaves up to N days"
    )

    # Validity period
    effective_from: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Effective start date"
    )
    
    effective_to: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Effective end date (NULL=indefinite)"
    )

    # Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether quota is currently active"
    )

    # Description
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Quota description and notes"
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="leave_quotas",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveQuota(id={self.id}, hostel_id={self.hostel_id}, "
            f"type={self.leave_type.value}, quota={self.annual_quota})>"
        )


class LeaveUsage(BaseModel, TimestampModel, UUIDMixin):
    """
    Detailed leave usage records.
    
    Tracks individual leave consumption events for
    analytics and reporting.
    """
    
    __tablename__ = "leave_usage"
    __table_args__ = (
        Index("ix_leave_usage_balance_id", "balance_id"),
        Index("ix_leave_usage_leave_id", "leave_id"),
        Index("ix_leave_usage_usage_date", "usage_date"),
        Index(
            "ix_leave_usage_balance_dates",
            "balance_id",
            "usage_date"
        ),
        {"comment": "Detailed leave usage tracking"}
    )

    # References
    balance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leave_balances.id", ondelete="CASCADE"),
        nullable=False,
        comment="Leave balance"
    )
    
    leave_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leave_applications.id", ondelete="CASCADE"),
        nullable=False,
        comment="Leave application"
    )

    # Usage details
    usage_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Date of leave usage"
    )
    
    days_used: Mapped[Numeric] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=1.0,
        comment="Number of days used (can be partial)"
    )
    
    usage_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="approved",
        comment="Type of usage (approved, adjusted, carried_forward)"
    )

    # Tracking
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="When leave was applied"
    )
    
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When leave was approved"
    )
    
    days_notice: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Days of advance notice given"
    )

    # Flags
    was_backdated: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether application was backdated"
    )
    
    had_supporting_document: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether supporting document was provided"
    )

    # Relationships
    leave_balance: Mapped["LeaveBalance"] = relationship(
        "LeaveBalance",
        back_populates="usage_records",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveUsage(id={self.id}, balance_id={self.balance_id}, "
            f"date={self.usage_date}, days={self.days_used})>"
        )


class LeaveCarryForward(BaseModel, TimestampModel, UUIDMixin):
    """
    Leave carry forward tracking.
    
    Records leave days carried forward from one period to another
    with expiry tracking.
    """
    
    __tablename__ = "leave_carry_forwards"
    __table_args__ = (
        UniqueConstraint(
            "student_id",
            "leave_type",
            "from_year_start",
            "to_year_start",
            name="uq_leave_carry_forward_student_type_years"
        ),
        CheckConstraint(
            "days_carried_forward >= 0",
            name="ck_leave_carry_forward_days_non_negative"
        ),
        Index("ix_leave_carry_forward_student_id", "student_id"),
        Index("ix_leave_carry_forward_leave_type", "leave_type"),
        Index("ix_leave_carry_forward_expiry_date", "expiry_date"),
        {"comment": "Leave carry forward tracking"}
    )

    # Student and leave type
    student_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        comment="Student"
    )
    
    leave_type: Mapped[LeaveType] = mapped_column(
        Enum(LeaveType, name="leave_type_enum", create_type=False),
        nullable=False,
        comment="Leave type"
    )

    # Period information
    from_year_start: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Source academic year start"
    )
    
    from_year_end: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Source academic year end"
    )
    
    to_year_start: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Target academic year start"
    )
    
    to_year_end: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        comment="Target academic year end"
    )

    # Carry forward details
    original_balance: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Original balance in source year"
    )
    
    used_in_source_year: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Days used in source year"
    )
    
    eligible_for_carry_forward: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Days eligible for carry forward"
    )
    
    days_carried_forward: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Actual days carried forward (may be capped)"
    )
    
    days_used_from_carry_forward: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Days used from carry forward"
    )
    
    days_expired: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Days that expired unused"
    )

    # Expiry
    expiry_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Expiry date for carried forward days"
    )
    
    is_expired: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether carried forward days have expired"
    )

    # Processing
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When carry forward was processed"
    )
    
    processed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who processed carry forward"
    )

    # Relationships
    student: Mapped["Student"] = relationship(
        "Student",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveCarryForward(id={self.id}, student_id={self.student_id}, "
            f"type={self.leave_type.value}, days={self.days_carried_forward})>"
        )


class LeaveAdjustment(BaseModel, TimestampModel, UUIDMixin):
    """
    Manual leave balance adjustments.
    
    Records manual adjustments to leave balances with
    audit trail and justification.
    """
    
    __tablename__ = "leave_adjustments"
    __table_args__ = (
        Index("ix_leave_adjustment_balance_id", "balance_id"),
        Index("ix_leave_adjustment_adjusted_by", "adjusted_by"),
        Index("ix_leave_adjustment_adjustment_date", "adjustment_date"),
        {"comment": "Manual leave balance adjustments"}
    )

    # Reference to balance
    balance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("leave_balances.id", ondelete="CASCADE"),
        nullable=False,
        comment="Leave balance being adjusted"
    )

    # Adjustment details
    adjustment_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Type of adjustment (credit, debit, correction)"
    )
    
    adjustment_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of days adjusted (positive=credit, negative=debit)"
    )
    
    adjustment_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Reason for adjustment"
    )
    
    adjustment_category: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Category of adjustment"
    )

    # Before/after state
    balance_before: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Balance before adjustment"
    )
    
    balance_after: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Balance after adjustment"
    )

    # Tracking
    adjustment_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="Adjustment timestamp"
    )
    
    adjusted_by: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who made adjustment"
    )

    # Approval if required
    requires_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether adjustment requires approval"
    )
    
    is_approved: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="Approval status"
    )
    
    approved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who approved adjustment"
    )
    
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Approval timestamp"
    )

    # Reference
    reference_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Reference number for adjustment"
    )
    
    supporting_document_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Supporting document URL"
    )

    # Relationships
    leave_balance: Mapped["LeaveBalance"] = relationship(
        "LeaveBalance",
        back_populates="adjustments",
        lazy="select"
    )

    def __repr__(self) -> str:
        return (
            f"<LeaveAdjustment(id={self.id}, balance_id={self.balance_id}, "
            f"days={self.adjustment_days}, type={self.adjustment_type})>"
        )
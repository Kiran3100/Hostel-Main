"""
Payment schedule model.

Manages recurring payment schedules for students.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from enum import Enum as PyEnum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date as SQLDate,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    func,  # Added this import
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import AuditMixin, SoftDeleteMixin, UUIDMixin
from app.schemas.common.enums import FeeType

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel
    from app.models.payment.payment import Payment
    from app.models.student.student import Student
    from app.models.user.user import User


class ScheduleStatus(str, PyEnum):
    """Payment schedule status enum."""
    
    ACTIVE = "active"
    PAUSED = "paused"
    SUSPENDED = "suspended"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class PaymentSchedule(TimestampModel, UUIDMixin, SoftDeleteMixin, AuditMixin):
    """
    Payment schedule model for recurring payments.
    
    Manages recurring payment schedules for students including
    monthly rent, mess fees, and other periodic charges.
    """

    __tablename__ = "payment_schedules"

    # ==================== Foreign Keys ====================
    student_id: Mapped[UUID] = mapped_column(
        ForeignKey("students.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # ==================== Schedule Configuration ====================
    schedule_reference: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique schedule reference number",
    )
    
    fee_type: Mapped[FeeType] = mapped_column(
        Enum(FeeType),
        nullable=False,
        index=True,
        comment="Type of fee (monthly, quarterly, etc.)",
    )
    
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Amount to charge per period",
    )
    
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        comment="Currency code",
    )

    # ==================== Schedule Period ====================
    start_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Schedule start date",
    )
    
    end_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
        comment="Schedule end date (null for indefinite)",
    )
    
    next_due_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Next payment due date",
    )
    
    last_generated_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Last date payment was generated",
    )

    # ==================== Frequency Configuration ====================
    frequency_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Number of days between payments (30 for monthly, 90 for quarterly)",
    )
    
    day_of_month: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        comment="Specific day of month for payment (1-31)",
    )

    # ==================== Generation Settings ====================
    auto_generate_invoice: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Automatically generate payment invoices",
    )
    
    auto_send_reminders: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Automatically send payment reminders",
    )
    
    days_before_due_reminder: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=7,
        comment="Days before due date to send reminder",
    )

    # ==================== Status ====================
    schedule_status: Mapped[ScheduleStatus] = mapped_column(
        Enum(ScheduleStatus),
        nullable=False,
        default=ScheduleStatus.ACTIVE,
        index=True,
    )
    
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether schedule is currently active",
    )

    # ==================== Generation Statistics ====================
    total_payments_generated: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of payments generated",
    )
    
    total_payments_completed: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of completed payments",
    )
    
    total_amount_collected: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total amount collected from this schedule",
    )

    # ==================== Suspension Details ====================
    suspended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When schedule was suspended",
    )
    
    suspension_reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for suspension",
    )
    
    suspension_start_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Suspension period start date",
    )
    
    suspension_end_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Suspension period end date",
    )
    
    skip_during_suspension: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Skip payment generation during suspension",
    )

    # ==================== Completion Details ====================
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When schedule was completed",
    )
    
    completion_reason: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Reason for completion",
    )

    # ==================== Additional Information ====================
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes about schedule",
    )
    
    # Changed 'metadata' to 'extra_data' to avoid SQLAlchemy reserved word conflict
    extra_data: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata",
    )

    # ==================== Relationships ====================
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="payment_schedules",
        lazy="selectin",
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="payment_schedules",
        lazy="selectin",
    )
    
    generated_payments: Mapped[list["Payment"]] = relationship(
        "Payment",
        back_populates="payment_schedule",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # ==================== Indexes ====================
    __table_args__ = (
        Index("idx_schedule_student_status", "student_id", "schedule_status"),
        Index("idx_schedule_hostel_status", "hostel_id", "schedule_status"),
        Index("idx_schedule_next_due", "next_due_date", "is_active"),
        Index("idx_schedule_fee_type", "fee_type"),
        Index("idx_schedule_active", "is_active", "schedule_status"),
        # Fixed: Use func.lower() for case-insensitive index
        Index("idx_schedule_reference_lower", func.lower(schedule_reference)),
        {"comment": "Recurring payment schedules for students"},
    )

    # ==================== Properties ====================
    @property
    def is_indefinite(self) -> bool:
        """Check if schedule has no end date."""
        return self.end_date is None

    @property
    def is_suspended(self) -> bool:
        """Check if schedule is currently suspended."""
        return self.schedule_status == ScheduleStatus.SUSPENDED

    @property
    def is_completed(self) -> bool:
        """Check if schedule is completed."""
        return self.schedule_status == ScheduleStatus.COMPLETED

    @property
    def days_until_next_payment(self) -> int:
        """Calculate days until next payment."""
        return (self.next_due_date - Date.today()).days

    @property
    def is_overdue(self) -> bool:
        """Check if next payment is overdue."""
        return self.next_due_date < Date.today() and self.is_active

    @property
    def collection_rate(self) -> float:
        """Calculate collection rate percentage."""
        if self.total_payments_generated == 0:
            return 0.0
        return (self.total_payments_completed / self.total_payments_generated) * 100

    # ==================== Methods ====================
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<PaymentSchedule("
            f"id={self.id}, "
            f"reference={self.schedule_reference}, "
            f"fee_type={self.fee_type.value}, "
            f"status={self.schedule_status.value}"
            f")>"
        )

    def calculate_next_due_date(self) -> Date:
        """Calculate next due date based on frequency."""
        from datetime import timedelta
        from calendar import monthrange
        
        next_date = self.next_due_date + timedelta(days=self.frequency_days)
        
        # Handle day_of_month preference
        if self.day_of_month:
            try:
                # Adjust to preferred day of month
                days_in_month = monthrange(next_date.year, next_date.month)[1]
                target_day = min(self.day_of_month, days_in_month)
                next_date = next_date.replace(day=target_day)
            except ValueError:
                # Fall back to calculated date if replacement fails
                pass
        
        return next_date

    def is_in_suspension_period(self, check_date: Date | None = None) -> bool:
        """Check if given date falls in suspension period."""
        if not self.suspension_start_date or not self.suspension_end_date:
            return False
        
        date_to_check = check_date or Date.today()
        return self.suspension_start_date <= date_to_check <= self.suspension_end_date

    def validate_schedule_dates(self) -> bool:
        """Validate schedule date consistency."""
        if self.end_date and self.start_date >= self.end_date:
            raise ValueError("End date must be after start date")
        
        if self.next_due_date < self.start_date:
            raise ValueError("Next due date cannot be before start date")
        
        return True

    def reactivate_from_suspension(self, reason: str = None) -> None:
        """Reactivate schedule from suspension."""
        if self.schedule_status == ScheduleStatus.SUSPENDED:
            self.schedule_status = ScheduleStatus.ACTIVE
            self.suspended_at = None
            self.suspension_reason = None
            # Update audit fields would be handled by AuditMixin
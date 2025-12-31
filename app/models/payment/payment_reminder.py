"""
Payment reminder model.

Manages payment reminder configuration and delivery tracking.
"""

from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel
    from app.models.payment.payment import Payment
    from app.models.student.student import Student


class ReminderType(str, Enum):
    """Reminder type enum."""
    
    BEFORE_DUE = "before_due"
    ON_DUE = "on_due"
    AFTER_DUE = "after_due"
    OVERDUE = "overdue"
    ESCALATION = "escalation"
    MANUAL = "manual"


class ReminderStatus(str, Enum):
    """Reminder status enum."""
    
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PaymentReminder(TimestampModel, UUIDMixin, SoftDeleteMixin):
    """
    Payment reminder model for tracking reminder delivery.
    
    Records individual reminder attempts and their outcomes.
    """

    __tablename__ = "payment_reminders"

    # ==================== Foreign Keys ====================
    payment_id: Mapped[UUID] = mapped_column(
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
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

    # ==================== Reminder Details ====================
    reminder_reference: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique reminder reference",
    )
    
    reminder_type: Mapped[ReminderType] = mapped_column(
        SQLEnum(ReminderType, name="reminder_type_enum", create_type=True),
        nullable=False,
        index=True,
        comment="Type of reminder",
    )
    
    reminder_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Sequence number of reminder for this payment",
    )

    # ==================== Recipient Information ====================
    recipient_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Recipient full name",
    )
    
    recipient_email: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Recipient email",
    )
    
    recipient_phone: Mapped[str | None] = mapped_column(
        String(15),
        nullable=True,
        comment="Recipient phone number",
    )

    # ==================== Delivery Channels ====================
    sent_via_email: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether sent via email",
    )
    
    sent_via_sms: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether sent via SMS",
    )
    
    sent_via_push: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether sent via push notification",
    )

    # ==================== Status ====================
    reminder_status: Mapped[ReminderStatus] = mapped_column(
        SQLEnum(ReminderStatus, name="reminder_status_enum", create_type=True),
        nullable=False,
        default=ReminderStatus.PENDING,
        index=True,
    )

    # ==================== Scheduling ====================
    scheduled_for: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When reminder was scheduled to be sent",
    )
    
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When reminder was actually sent",
    )

    # ==================== Email Tracking ====================
    email_message_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Email message ID for tracking",
    )
    
    email_opened: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether email was opened",
    )
    
    email_clicked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether email link was clicked",
    )
    
    opened_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When email was opened",
    )
    
    clicked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When email link was clicked",
    )

    # ==================== SMS Tracking ====================
    sms_message_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="SMS message ID for tracking",
    )
    
    sms_delivered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether SMS was delivered",
    )
    
    sms_delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When SMS was delivered",
    )

    # ==================== Push Notification Tracking ====================
    push_notification_id: Mapped[str | None] = mapped_column(
        String(200),
        nullable=True,
        comment="Push notification ID",
    )
    
    push_delivered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether push was delivered",
    )
    
    push_clicked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether push was clicked",
    )

    # ==================== Template Information ====================
    template_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Template ID used for reminder",
    )
    
    template_variables: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Variables used in template",
    )

    # ==================== Error Handling ====================
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Error message if delivery failed",
    )
    
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of retry attempts",
    )
    
    last_retry_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When last retry was attempted",
    )

    # ==================== Additional Data ====================
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes",
    )
    
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata",
    )

    # ==================== Relationships ====================
    payment: Mapped["Payment"] = relationship(
        "Payment",
        back_populates="reminders",
        lazy="selectin",
    )
    
    student: Mapped["Student"] = relationship(
        "Student",
        back_populates="payment_reminders",
        lazy="selectin",
    )
    
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="payment_reminders",
        lazy="selectin",
    )

    # ==================== Indexes ====================
    __table_args__ = (
        Index("idx_reminder_payment_type", "payment_id", "reminder_type"),
        Index("idx_reminder_student_status", "student_id", "reminder_status"),
        Index("idx_reminder_scheduled_for", "scheduled_for"),
        Index("idx_reminder_sent_at", "sent_at"),
        Index("idx_reminder_status", "reminder_status"),
        Index("idx_reminder_reference_lower", func.lower(reminder_reference)),
        {"comment": "Payment reminder delivery tracking"},
    )

    # ==================== Properties ====================
    @property
    def is_sent(self) -> bool:
        """Check if reminder was sent."""
        return self.reminder_status in [
            ReminderStatus.SENT,
            ReminderStatus.DELIVERED,
        ]

    @property
    def is_delivered(self) -> bool:
        """Check if reminder was delivered."""
        return self.reminder_status == ReminderStatus.DELIVERED

    @property
    def is_failed(self) -> bool:
        """Check if reminder failed."""
        return self.reminder_status == ReminderStatus.FAILED

    @property
    def channels_used(self) -> list[str]:
        """Get list of channels used."""
        channels = []
        if self.sent_via_email:
            channels.append("email")
        if self.sent_via_sms:
            channels.append("sms")
        if self.sent_via_push:
            channels.append("push")
        return channels

    @property
    def engagement_score(self) -> int:
        """Calculate engagement score (0-100)."""
        score = 0
        if self.email_opened:
            score += 40
        if self.email_clicked:
            score += 60
        if self.sms_delivered:
            score += 50
        if self.push_clicked:
            score += 70
        # Cap at 100
        return min(score, 100)

    # ==================== Methods ====================
    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<PaymentReminder("
            f"id={self.id}, "
            f"reference={self.reminder_reference}, "
            f"type={self.reminder_type.value}, "
            f"status={self.reminder_status.value}"
            f")>"
        )
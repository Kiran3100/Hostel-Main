"""
Payment model.

Core payment entity for all payment transactions in the hostel management system.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Date as SQLDate,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base.base_model import TimestampModel
from app.models.base.mixins import AuditMixin, SoftDeleteMixin, UUIDMixin
from app.schemas.common.enums import PaymentMethod, PaymentStatus, PaymentType

if TYPE_CHECKING:
    from app.models.hostel.hostel import Hostel
    from app.models.payment.gateway_transaction import GatewayTransaction
    from app.models.payment.payment_ledger import PaymentLedger
    from app.models.payment.payment_refund import PaymentRefund
    from app.models.payment.payment_reminder import PaymentReminder
    from app.models.payment.payment_schedule import PaymentSchedule
    from app.models.student.student import Student
    from app.models.user.user import User


class Payment(TimestampModel, UUIDMixin, SoftDeleteMixin, AuditMixin):
    """
    Payment model for tracking all payment transactions.
    
    This model handles various payment types including rent, mess fees,
    security deposits, and other charges.
    """

    __tablename__ = "payments"

    # ==================== Foreign Keys ====================
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    student_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("students.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    booking_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    payer_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payment_schedule_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("payment_schedules.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    # ==================== Core Payment Details ====================
    payment_reference: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique payment reference number (e.g., PAY-2024-001234)",
    )
    
    payment_type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType, name="payment_type_enum", create_type=True),
        nullable=False,
        index=True,
    )
    
    amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        comment="Payment amount",
    )
    
    currency: Mapped[str] = mapped_column(
        String(3),
        nullable=False,
        default="INR",
        comment="Currency code (ISO 4217)",
    )

    # ==================== Payment Method ====================
    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(PaymentMethod, name="payment_method_enum", create_type=True),
        nullable=False,
        index=True,
    )
    
    payment_gateway: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Payment gateway identifier (razorpay, stripe, etc.)",
    )

    # ==================== Transaction Details ====================
    transaction_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        unique=True,
        index=True,
        comment="External transaction ID from gateway",
    )
    
    gateway_order_id: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="Gateway order/payment ID",
    )
    
    gateway_response: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Raw gateway response data",
    )

    # ==================== Payment Status ====================
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus, name="payment_status_enum", create_type=True),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
    )

    # ==================== Payment Period (for recurring fees) ====================
    payment_period_start: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
        comment="Start date of payment period",
    )
    
    payment_period_end: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
        comment="End date of payment period",
    )

    # ==================== Due Date ====================
    due_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        index=True,
        comment="Payment due date",
    )
    
    is_overdue: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Computed field: True if past due date and unpaid",
    )

    # ==================== Payment Timestamps ====================
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When payment was successfully completed",
    )
    
    failed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When payment failed",
    )
    
    failure_reason: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="Reason for payment failure",
    )

    # ==================== Receipt Information ====================
    receipt_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        unique=True,
        index=True,
        comment="Unique receipt number",
    )
    
    receipt_generated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When receipt was generated",
    )
    
    receipt_url: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        comment="URL to download receipt",
    )

    # ==================== Refund Information ====================
    refund_amount: Mapped[Decimal] = mapped_column(
        Numeric(precision=10, scale=2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total refunded amount",
    )
    
    is_refunded: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether payment has been fully or partially refunded",
    )

    # ==================== Collection Details (for offline payments) ====================
    collected_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Staff member who collected payment (for offline payments)",
    )
    
    collected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When offline payment was collected",
    )

    # ==================== Cheque Details ====================
    cheque_number: Mapped[str | None] = mapped_column(
        String(50),
        nullable=True,
        comment="Cheque number (if payment method is cheque)",
    )
    
    cheque_date: Mapped[Date | None] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Cheque date",
    )
    
    bank_name: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        comment="Bank name (for cheque/bank transfer)",
    )

    # ==================== Reminder Tracking ====================
    reminder_sent_count: Mapped[int] = mapped_column(
        nullable=False,
        default=0,
        comment="Number of payment reminders sent",
    )
    
    last_reminder_sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When last reminder was sent",
    )

    # ==================== Additional Information ====================
    notes: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes about the payment",
    )
    
    extra_metadata: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        comment="Additional metadata in JSON format",
    )

    # ==================== Relationships ====================
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="payments",
        lazy="selectin",
    )
    
    student: Mapped["Student | None"] = relationship(
        "Student",
        back_populates="payments",
        foreign_keys=[student_id],
        lazy="selectin",
    )
    
    payer: Mapped["User"] = relationship(
        "User",
        foreign_keys=[payer_id],
        lazy="selectin",
    )
    
    collector: Mapped["User | None"] = relationship(
        "User",
        foreign_keys=[collected_by],
        lazy="selectin",
    )
    
    payment_schedule: Mapped["PaymentSchedule | None"] = relationship(
        "PaymentSchedule",
        back_populates="generated_payments",
        lazy="selectin",
    )
    
    gateway_transactions: Mapped[list["GatewayTransaction"]] = relationship(
        "GatewayTransaction",
        back_populates="payment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    refunds: Mapped[list["PaymentRefund"]] = relationship(
        "PaymentRefund",
        back_populates="payment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    reminders: Mapped[list["PaymentReminder"]] = relationship(
        "PaymentReminder",
        back_populates="payment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    
    ledger_entries: Mapped[list["PaymentLedger"]] = relationship(
        "PaymentLedger",
        back_populates="payment",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # ==================== Indexes ====================
    __table_args__ = (
        Index("idx_payment_hostel_status", "hostel_id", "payment_status"),
        Index("idx_payment_student_status", "student_id", "payment_status"),
        Index("idx_payment_due_date_status", "due_date", "payment_status"),
        Index("idx_payment_type_status", "payment_type", "payment_status"),
        Index("idx_payment_created_at", "created_at"),
        Index("idx_payment_paid_at", "paid_at"),
        Index("idx_payment_reference_lower", func.lower(payment_reference)),  # Fixed: Use func.lower()
        Index("idx_payment_overdue", "is_overdue", "payment_status"),
        {"comment": "Payment transactions for hostel management system"},
    )

    # ==================== Properties ====================
    @property
    def net_amount(self) -> Decimal:
        """Calculate net amount after refunds."""
        return self.amount - self.refund_amount

    @property
    def is_completed(self) -> bool:
        """Check if payment is completed."""
        return self.payment_status == PaymentStatus.COMPLETED

    @property
    def is_pending(self) -> bool:
        """Check if payment is pending."""
        return self.payment_status == PaymentStatus.PENDING

    @property
    def is_failed(self) -> bool:
        """Check if payment failed."""
        return self.payment_status == PaymentStatus.FAILED

    @property
    def is_partially_refunded(self) -> bool:
        """Check if payment is partially refunded."""
        return (
            self.refund_amount > Decimal("0")
            and self.refund_amount < self.amount
        )

    @property
    def is_fully_refunded(self) -> bool:
        """Check if payment is fully refunded."""
        return self.refund_amount >= self.amount

    # ==================== Methods ====================
    def __repr__(self) -> str:
        """String representation of Payment."""
        return (
            f"<Payment("
            f"id={self.id}, "
            f"reference={self.payment_reference}, "
            f"amount={self.amount}, "
            f"status={self.payment_status.value}"
            f")>"
        )

    def to_dict(self) -> dict:
        """Convert payment to dictionary."""
        return {
            "id": str(self.id),
            "payment_reference": self.payment_reference,
            "hostel_id": str(self.hostel_id),
            "student_id": str(self.student_id) if self.student_id else None,
            "payer_id": str(self.payer_id),
            "payment_type": self.payment_type.value,
            "amount": float(self.amount),
            "currency": self.currency,
            "payment_method": self.payment_method.value,
            "payment_status": self.payment_status.value,
            "paid_at": self.paid_at.isoformat() if self.paid_at else None,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "is_overdue": self.is_overdue,
            "receipt_number": self.receipt_number,
            "extra_metadata": self.extra_metadata,
            "created_at": self.created_at.isoformat(),
        }
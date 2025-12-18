"""
Booking cancellation models.

This module defines cancellation records, refund calculations,
and cancellation policies for bookings.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base.base_model import TimestampModel
from app.models.base.enums import PaymentStatus
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.booking.booking import Booking
    from app.models.hostel.hostel import Hostel
    from app.models.payment.payment import Payment
    from app.models.user.user import User

__all__ = [
    "BookingCancellation",
    "CancellationPolicy",
    "RefundTransaction",
]


class BookingCancellation(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Booking cancellation record and refund calculation.
    
    Stores detailed information about booking cancellations including
    who cancelled, why, refund calculations, and processing status.
    
    Attributes:
        booking_id: Reference to the booking (one-to-one)
        cancelled_by: Who cancelled (visitor or admin)
        cancelled_by_role: Role of canceller (visitor, admin, system)
        cancelled_at: When booking was cancelled
        cancellation_reason: Detailed reason for cancellation
        additional_comments: Additional context or notes
        request_refund: Whether refund was requested
        advance_paid: Total advance amount paid
        cancellation_charge: Cancellation charge amount
        cancellation_charge_percentage: Charge as percentage
        refundable_amount: Final amount to be refunded
        refund_processing_time_days: Expected refund processing time
        refund_method: Method of refund
        refund_status: Current refund status
        refund_initiated_at: When refund was initiated
        refund_completed_at: When refund was completed
        refund_transaction_id: Reference to refund transaction
        cancellation_notification_sent: Whether notification was sent
    """

    __tablename__ = "booking_cancellations"

    # Foreign Key (One-to-One with Booking)
    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to booking (one-to-one)",
    )

    # Cancellation Metadata
    cancelled_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Who cancelled the booking",
    )

    cancelled_by_role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Role of person cancelling (visitor, admin, system)",
    )

    cancelled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When booking was cancelled",
    )

    # Cancellation Details
    cancellation_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed reason for cancellation",
    )

    additional_comments: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional comments or context",
    )

    # Refund Request
    request_refund: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether refund was requested",
    )

    # Refund Calculation
    advance_paid: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Total advance amount paid",
    )

    cancellation_charge: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Cancellation charge amount",
    )

    cancellation_charge_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Cancellation charge as percentage of advance",
    )

    refundable_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Final amount to be refunded",
    )

    # Refund Processing
    refund_processing_time_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=7,
        comment="Expected number of days to process refund",
    )

    refund_method: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Method of refund (bank_transfer, original_payment_method, etc.)",
    )

    refund_status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
        comment="Current refund status",
    )

    refund_initiated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When refund was initiated",
    )

    refund_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When refund was completed",
    )

    refund_transaction_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to refund transaction",
    )

    # Detailed Breakdown
    refund_breakdown: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Detailed refund calculation breakdown (JSON)",
    )

    # Notification
    cancellation_notification_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether cancellation notification was sent",
    )

    cancellation_notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When cancellation notification was sent",
    )

    # Relationships
    booking: Mapped["Booking"] = relationship(
        "Booking",
        back_populates="cancellation",
    )

    canceller: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[cancelled_by],
        lazy="select",
    )

    refund_transaction: Mapped[Optional["Payment"]] = relationship(
        "Payment",
        foreign_keys=[refund_transaction_id],
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        CheckConstraint(
            "advance_paid >= 0",
            name="ck_cancellation_advance_positive",
        ),
        CheckConstraint(
            "cancellation_charge >= 0",
            name="ck_cancellation_charge_positive",
        ),
        CheckConstraint(
            "refundable_amount >= 0",
            name="ck_cancellation_refund_positive",
        ),
        CheckConstraint(
            "cancellation_charge_percentage >= 0 AND cancellation_charge_percentage <= 100",
            name="ck_cancellation_percentage_range",
        ),
        CheckConstraint(
            "refund_processing_time_days >= 0",
            name="ck_cancellation_processing_positive",
        ),
        Index("ix_cancellation_booking", "booking_id"),
        Index("ix_cancellation_cancelled_at", "cancelled_at"),
        Index("ix_cancellation_refund_status", "refund_status"),
        UniqueConstraint("booking_id", name="uq_cancellation_booking"),
        {"comment": "Booking cancellation records and refund calculations"},
    )

    # Validators
    @validates("cancelled_by_role")
    def validate_canceller_role(self, key: str, value: str) -> str:
        """Validate canceller role."""
        valid_roles = {"visitor", "admin", "system"}
        if value.lower() not in valid_roles:
            raise ValueError(f"Invalid canceller role. Must be one of {valid_roles}")
        return value.lower()

    @validates("cancellation_reason")
    def validate_reason(self, key: str, value: str) -> str:
        """Validate cancellation reason is meaningful."""
        if len(value.strip()) < 10:
            raise ValueError("Cancellation reason must be at least 10 characters")
        return value.strip()

    @validates("advance_paid", "cancellation_charge", "refundable_amount")
    def validate_amounts(self, key: str, value: Decimal) -> Decimal:
        """Validate monetary amounts are non-negative."""
        if value < 0:
            raise ValueError(f"{key} cannot be negative")
        return value

    # Properties
    @property
    def is_refund_pending(self) -> bool:
        """Check if refund is pending."""
        return self.refund_status == PaymentStatus.PENDING

    @property
    def is_refund_completed(self) -> bool:
        """Check if refund is completed."""
        return self.refund_status == PaymentStatus.COMPLETED

    @property
    def days_since_cancellation(self) -> int:
        """Calculate days since cancellation."""
        return (datetime.utcnow() - self.cancelled_at).days

    @property
    def expected_refund_date(self) -> Optional[datetime]:
        """Calculate expected refund completion date."""
        if not self.refund_initiated_at:
            return None
        from datetime import timedelta
        return self.refund_initiated_at + timedelta(days=self.refund_processing_time_days)

    # Methods
    def initiate_refund(self) -> None:
        """Mark refund as initiated."""
        if self.refund_status != PaymentStatus.PENDING:
            raise ValueError("Can only initiate pending refunds")
        
        self.refund_status = PaymentStatus.PROCESSING
        self.refund_initiated_at = datetime.utcnow()

    def complete_refund(self, transaction_id: UUID) -> None:
        """
        Mark refund as completed.
        
        Args:
            transaction_id: ID of the refund transaction
        """
        if self.refund_status != PaymentStatus.PROCESSING:
            raise ValueError("Can only complete refunds that are processing")
        
        self.refund_status = PaymentStatus.COMPLETED
        self.refund_completed_at = datetime.utcnow()
        self.refund_transaction_id = transaction_id

    def fail_refund(self, reason: str) -> None:
        """
        Mark refund as failed.
        
        Args:
            reason: Reason for refund failure
        """
        self.refund_status = PaymentStatus.FAILED
        if self.refund_breakdown:
            self.refund_breakdown["failure_reason"] = reason
        else:
            self.refund_breakdown = {"failure_reason": reason}

    def send_cancellation_notification(self) -> None:
        """Mark cancellation notification as sent."""
        self.cancellation_notification_sent = True
        self.cancellation_notification_sent_at = datetime.utcnow()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<BookingCancellation(booking_id={self.booking_id}, "
            f"refund_status={self.refund_status}, "
            f"refundable={self.refundable_amount})>"
        )


class CancellationPolicy(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Hostel-specific cancellation policy configuration.
    
    Defines cancellation charges based on timing, refund policies,
    and special conditions for a hostel.
    
    Attributes:
        hostel_id: Hostel identifier
        policy_name: Name of the policy
        cancellation_tiers: Tiered cancellation charges (JSON)
        no_show_charge_percentage: Charge for no-show
        refund_processing_days: Days to process refund
        policy_text: Full policy text for display
        is_active: Whether policy is currently active
        effective_from: When policy becomes effective
        effective_until: When policy expires
    """

    __tablename__ = "cancellation_policies"

    # Foreign Key
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel identifier",
    )

    # Policy Details
    policy_name: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        comment="Name of the cancellation policy",
    )

    # Tiered Cancellation Charges (JSON structure)
    # Format: [{"days_before_checkin": 30, "charge_percentage": 10}, ...]
    cancellation_tiers: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        comment="Tiered cancellation charges based on timing (JSON array)",
    )

    # Special Conditions
    no_show_charge_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("100.00"),
        comment="Charge percentage for no-show (typically 100%)",
    )

    # Processing
    refund_processing_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=7,
        comment="Number of business days to process refund",
    )

    # Policy Documentation
    policy_text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Full cancellation policy text for display to users",
    )

    # Policy Status
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether policy is currently active",
    )

    effective_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When policy becomes effective",
    )

    effective_until: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When policy expires (NULL for indefinite)",
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="cancellation_policies",
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        CheckConstraint(
            "no_show_charge_percentage >= 0 AND no_show_charge_percentage <= 100",
            name="ck_policy_no_show_range",
        ),
        CheckConstraint(
            "refund_processing_days >= 1 AND refund_processing_days <= 30",
            name="ck_policy_refund_days_range",
        ),
        Index("ix_policy_hostel", "hostel_id"),
        Index("ix_policy_active", "is_active"),
        Index("ix_policy_effective", "effective_from", "effective_until"),
        {"comment": "Hostel cancellation policy configuration"},
    )

    # Validators
    @validates("cancellation_tiers")
    def validate_tiers(self, key: str, value: list) -> list:
        """Validate cancellation tiers structure."""
        if not value:
            raise ValueError("At least one cancellation tier is required")
        
        for tier in value:
            if not isinstance(tier, dict):
                raise ValueError("Each tier must be a dictionary")
            if "days_before_checkin" not in tier or "charge_percentage" not in tier:
                raise ValueError("Each tier must have days_before_checkin and charge_percentage")
            
            days = tier["days_before_checkin"]
            percentage = tier["charge_percentage"]
            
            if not isinstance(days, (int, float)) or days < 0:
                raise ValueError("days_before_checkin must be non-negative number")
            if not isinstance(percentage, (int, float)) or percentage < 0 or percentage > 100:
                raise ValueError("charge_percentage must be between 0 and 100")
        
        # Sort by days_before_checkin descending
        return sorted(value, key=lambda x: x["days_before_checkin"], reverse=True)

    # Methods
    def calculate_cancellation_charge(self, days_before_checkin: int, advance_amount: Decimal) -> Decimal:
        """
        Calculate cancellation charge based on days before check-in.
        
        Args:
            days_before_checkin: Number of days before check-in
            advance_amount: Advance payment amount
            
        Returns:
            Calculated cancellation charge
        """
        # Find applicable tier
        applicable_percentage = Decimal("100.00")  # Default to full charge
        
        for tier in self.cancellation_tiers:
            if days_before_checkin >= tier["days_before_checkin"]:
                applicable_percentage = Decimal(str(tier["charge_percentage"]))
                break
        
        charge = (advance_amount * applicable_percentage / 100).quantize(Decimal("0.01"))
        return charge

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<CancellationPolicy(id={self.id}, hostel_id={self.hostel_id}, "
            f"name={self.policy_name}, active={self.is_active})>"
        )


class RefundTransaction(UUIDMixin, TimestampModel):
    """
    Refund transaction tracking.
    
    Tracks individual refund transactions separately from payments
    for better accounting and reconciliation.
    
    Attributes:
        cancellation_id: Reference to cancellation record
        booking_id: Reference to original booking
        refund_amount: Amount being refunded
        refund_method: Method of refund
        refund_status: Current status
        initiated_at: When refund was initiated
        processed_at: When refund was processed
        completed_at: When refund was completed
        gateway_transaction_id: External gateway transaction ID
        gateway_response: Gateway response data (JSON)
        failure_reason: Reason if refund failed
    """

    __tablename__ = "refund_transactions"

    # Foreign Keys
    cancellation_id: Mapped[UUID] = mapped_column(
        ForeignKey("booking_cancellations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to cancellation record",
    )

    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to original booking",
    )

    # Refund Details
    refund_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Amount being refunded",
    )

    refund_method: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Method of refund",
    )

    refund_status: Mapped[PaymentStatus] = mapped_column(
        SQLEnum(PaymentStatus),
        nullable=False,
        default=PaymentStatus.PENDING,
        index=True,
        comment="Current refund status",
    )

    # Timestamps
    initiated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When refund was initiated",
    )

    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When refund was processed",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When refund was completed",
    )

    # Gateway Information
    gateway_transaction_id: Mapped[Optional[str]] = mapped_column(
        String(100),
        nullable=True,
        index=True,
        comment="External payment gateway transaction ID",
    )

    gateway_response: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Gateway response data (JSON)",
    )

    # Failure Handling
    failure_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason if refund failed",
    )

    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of retry attempts",
    )

    # Table Configuration
    __table_args__ = (
        CheckConstraint(
            "refund_amount >= 0",
            name="ck_refund_amount_positive",
        ),
        Index("ix_refund_cancellation", "cancellation_id"),
        Index("ix_refund_booking", "booking_id"),
        Index("ix_refund_status", "refund_status"),
        Index("ix_refund_gateway", "gateway_transaction_id"),
        {"comment": "Refund transaction tracking"},
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<RefundTransaction(id={self.id}, "
            f"amount={self.refund_amount}, status={self.refund_status})>"
        )
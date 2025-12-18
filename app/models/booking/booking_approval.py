"""
Booking approval models.

This module defines the approval workflow for bookings,
including approval decisions, settings, and bulk operations.
"""

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
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
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.booking.booking import Booking
    from app.models.hostel.hostel import Hostel
    from app.models.user.user import User

__all__ = [
    "BookingApproval",
    "ApprovalSettings",
    "RejectionRecord",
]


class BookingApproval(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Booking approval workflow and decision tracking.
    
    Stores detailed information about booking approval including
    pricing confirmation, payment requirements, and communication
    with the guest.
    
    Attributes:
        booking_id: Reference to the booking (one-to-one)
        approved_by: Admin who approved the booking
        approved_at: When booking was approved
        final_rent_monthly: Final confirmed monthly rent
        final_security_deposit: Final confirmed security deposit
        processing_fee: One-time processing fee
        admin_notes: Internal notes (admin-only)
        message_to_guest: Message sent to guest with approval
        advance_payment_required: Whether advance payment is required
        advance_payment_percentage: Percentage of total as advance
        advance_payment_deadline: Deadline for advance payment
        auto_approved: Whether approval was automatic
        approval_criteria_met: Criteria that triggered auto-approval
    """

    __tablename__ = "booking_approvals"

    # Foreign Key (One-to-One with Booking)
    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to booking (one-to-one)",
    )

    # Approval Metadata
    approved_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who approved the booking",
    )

    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When booking was approved",
    )

    # Pricing Confirmation/Adjustment
    final_rent_monthly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Final confirmed monthly rent amount",
    )

    final_security_deposit: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Final confirmed security deposit amount",
    )

    processing_fee: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="One-time processing or booking fee",
    )

    # Total amounts (calculated)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Total amount after approval (rent × duration + fees)",
    )

    # Notes and Communication
    admin_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Internal notes visible only to admins",
    )

    message_to_guest: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Message sent to guest with approval",
    )

    # Payment Requirements
    advance_payment_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether advance payment is required",
    )

    advance_payment_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("20.00"),
        comment="Percentage of total required as advance (0-100)",
    )

    advance_payment_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Calculated advance payment amount",
    )

    advance_payment_deadline: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Deadline for advance payment",
    )

    # Auto-Approval
    auto_approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether approval was automatic",
    )

    approval_criteria_met: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Criteria that triggered auto-approval (JSON)",
    )

    # Notification Status
    approval_notification_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether approval notification was sent to guest",
    )

    approval_notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When approval notification was sent",
    )

    # Relationships
    booking: Mapped["Booking"] = relationship(
        "Booking",
        back_populates="approval",
    )

    approver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        CheckConstraint(
            "final_rent_monthly >= 0",
            name="ck_approval_rent_positive",
        ),
        CheckConstraint(
            "final_security_deposit >= 0",
            name="ck_approval_deposit_positive",
        ),
        CheckConstraint(
            "processing_fee >= 0",
            name="ck_approval_fee_positive",
        ),
        CheckConstraint(
            "advance_payment_percentage >= 0 AND advance_payment_percentage <= 100",
            name="ck_approval_advance_percentage_range",
        ),
        CheckConstraint(
            "advance_payment_amount >= 0",
            name="ck_approval_advance_amount_positive",
        ),
        Index("ix_approval_booking", "booking_id"),
        Index("ix_approval_approved_at", "approved_at"),
        Index("ix_approval_auto", "auto_approved"),
        UniqueConstraint("booking_id", name="uq_approval_booking"),
        {"comment": "Booking approval workflow and decisions"},
    )

    # Validators
    @validates("final_rent_monthly", "final_security_deposit", "processing_fee", "advance_payment_amount", "total_amount")
    def validate_amounts(self, key: str, value: Decimal) -> Decimal:
        """Validate monetary amounts are non-negative."""
        if value < 0:
            raise ValueError(f"{key} cannot be negative")
        return value

    @validates("advance_payment_percentage")
    def validate_percentage(self, key: str, value: Decimal) -> Decimal:
        """Validate percentage is in valid range."""
        if value < 0 or value > 100:
            raise ValueError("Advance payment percentage must be between 0 and 100")
        return value

    # Properties
    @property
    def is_payment_overdue(self) -> bool:
        """Check if advance payment is overdue."""
        if not self.advance_payment_required or not self.advance_payment_deadline:
            return False
        return datetime.utcnow() > self.advance_payment_deadline

    @property
    def days_until_payment_deadline(self) -> Optional[int]:
        """Calculate days until payment deadline."""
        if not self.advance_payment_deadline:
            return None
        delta = self.advance_payment_deadline - datetime.utcnow()
        return delta.days

    # Methods
    def send_approval_notification(self) -> None:
        """Mark approval notification as sent."""
        self.approval_notification_sent = True
        self.approval_notification_sent_at = datetime.utcnow()

    def calculate_advance_amount(self) -> Decimal:
        """Calculate advance payment amount based on percentage."""
        return (self.total_amount * self.advance_payment_percentage / 100).quantize(
            Decimal("0.01")
        )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<BookingApproval(booking_id={self.booking_id}, "
            f"approved_at={self.approved_at}, auto={self.auto_approved})>"
        )


class RejectionRecord(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Booking rejection details and alternative suggestions.
    
    Stores detailed information about why a booking was rejected
    and any alternative suggestions provided to the guest.
    
    Attributes:
        booking_id: Reference to the booking
        rejected_by: Admin who rejected the booking
        rejected_at: When booking was rejected
        rejection_reason: Detailed reason for rejection
        suggest_alternative_dates: Whether alternative dates were suggested
        alternative_check_in_dates: List of alternative dates (JSON)
        suggest_alternative_room_types: Whether alternative room types suggested
        alternative_room_types: List of alternative room types (JSON)
        message_to_guest: Personalized message to guest
        rejection_notification_sent: Whether notification was sent
        rejection_notification_sent_at: When notification was sent
    """

    __tablename__ = "rejection_records"

    # Foreign Key
    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to booking",
    )

    # Rejection Metadata
    rejected_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who rejected the booking",
    )

    rejected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When booking was rejected",
    )

    # Rejection Details
    rejection_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Detailed reason for rejection",
    )

    # Alternative Suggestions
    suggest_alternative_dates: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether alternative check-in dates were suggested",
    )

    alternative_check_in_dates: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of alternative check-in dates (JSON array)",
    )

    suggest_alternative_room_types: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether alternative room types were suggested",
    )

    alternative_room_types: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of alternative room types (JSON array)",
    )

    # Communication
    message_to_guest: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Personalized message to guest explaining rejection",
    )

    # Notification Status
    rejection_notification_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether rejection notification was sent",
    )

    rejection_notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When rejection notification was sent",
    )

    # Relationships
    booking: Mapped["Booking"] = relationship(
        "Booking",
        foreign_keys=[booking_id],
        lazy="select",
    )

    rejecter: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[rejected_by],
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        Index("ix_rejection_booking", "booking_id"),
        Index("ix_rejection_rejected_at", "rejected_at"),
        {"comment": "Booking rejection details and alternatives"},
    )

    # Validators
    @validates("rejection_reason")
    def validate_reason(self, key: str, value: str) -> str:
        """Validate rejection reason is meaningful."""
        if len(value.strip()) < 10:
            raise ValueError("Rejection reason must be at least 10 characters")
        return value.strip()

    # Methods
    def send_rejection_notification(self) -> None:
        """Mark rejection notification as sent."""
        self.rejection_notification_sent = True
        self.rejection_notification_sent_at = datetime.utcnow()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<RejectionRecord(booking_id={self.booking_id}, "
            f"rejected_at={self.rejected_at})>"
        )


class ApprovalSettings(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Hostel-specific booking approval settings.
    
    Configures auto-approval rules, payment requirements, and
    approval policies for a specific hostel.
    
    Attributes:
        hostel_id: Hostel identifier
        auto_approve_enabled: Enable automatic approval
        auto_approve_conditions: Conditions for auto-approval (JSON)
        approval_expiry_hours: Hours to respond before booking expires
        require_advance_payment: Require advance payment after approval
        advance_payment_percentage: Default advance payment percentage
        advance_payment_deadline_hours: Hours to make advance payment
        refund_processing_days: Days to process refunds
        approval_policy_text: Full approval policy text
        last_updated_by: Admin who last updated settings
    """

    __tablename__ = "approval_settings"

    # Foreign Key
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Hostel identifier",
    )

    # Auto-Approval Configuration
    auto_approve_enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Enable automatic approval of bookings",
    )

    auto_approve_conditions: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Conditions that must be met for auto-approval (JSON)",
    )

    # Timing Configuration
    approval_expiry_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=48,
        comment="Hours to respond to booking before it expires",
    )

    # Payment Configuration
    require_advance_payment: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Require advance payment after approval",
    )

    advance_payment_percentage: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        default=Decimal("20.00"),
        comment="Default advance payment percentage (0-100)",
    )

    advance_payment_deadline_hours: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=72,
        comment="Hours to make advance payment after approval",
    )

    # Refund Configuration
    refund_processing_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=7,
        comment="Number of business days to process refund",
    )

    # Policy Documentation
    approval_policy_text: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Full approval policy text for display to users",
    )

    # Metadata
    last_updated_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who last updated settings",
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="approval_settings",
        lazy="select",
    )

    updater: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[last_updated_by],
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        CheckConstraint(
            "approval_expiry_hours >= 1 AND approval_expiry_hours <= 168",
            name="ck_settings_expiry_range",
        ),
        CheckConstraint(
            "advance_payment_percentage >= 0 AND advance_payment_percentage <= 100",
            name="ck_settings_advance_percentage_range",
        ),
        CheckConstraint(
            "advance_payment_deadline_hours >= 1",
            name="ck_settings_deadline_positive",
        ),
        CheckConstraint(
            "refund_processing_days >= 1 AND refund_processing_days <= 30",
            name="ck_settings_refund_range",
        ),
        Index("ix_settings_hostel", "hostel_id"),
        UniqueConstraint("hostel_id", name="uq_settings_hostel"),
        {"comment": "Hostel-specific booking approval settings"},
    )

    # Validators
    @validates("approval_expiry_hours")
    def validate_expiry_hours(self, key: str, value: int) -> int:
        """Validate approval expiry hours."""
        if value < 1 or value > 168:
            raise ValueError("Approval expiry must be between 1 and 168 hours")
        return value

    @validates("advance_payment_percentage")
    def validate_percentage(self, key: str, value: Decimal) -> Decimal:
        """Validate advance payment percentage."""
        if value < 0 or value > 100:
            raise ValueError("Advance payment percentage must be between 0 and 100")
        return value

    @validates("refund_processing_days")
    def validate_refund_days(self, key: str, value: int) -> int:
        """Validate refund processing days."""
        if value < 1 or value > 30:
            raise ValueError("Refund processing days must be between 1 and 30")
        return value

    # Properties
    @property
    def has_auto_approval(self) -> bool:
        """Check if auto-approval is configured."""
        return self.auto_approve_enabled and self.auto_approve_conditions is not None

    # Methods
    def update_settings(self, updated_by: UUID) -> None:
        """
        Update settings metadata.
        
        Args:
            updated_by: ID of admin updating settings
        """
        self.last_updated_by = updated_by
        self.updated_at = datetime.utcnow()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<ApprovalSettings(hostel_id={self.hostel_id}, "
            f"auto_approve={self.auto_approve_enabled})>"
        )
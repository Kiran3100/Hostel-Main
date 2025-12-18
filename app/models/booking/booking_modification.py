"""
Booking modification models.

This module defines modification requests for existing bookings,
including date changes, duration changes, and room type changes.
"""

from datetime import date as Date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date as SQLDate,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base.base_model import TimestampModel
from app.models.base.enums import RoomType
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.booking.booking import Booking
    from app.models.user.user import User

__all__ = [
    "BookingModification",
    "ModificationApprovalRecord",
]


class BookingModification(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Booking modification request and tracking.
    
    Tracks requests to modify existing bookings including changes
    to check-in dates, duration, room type, and pricing impact.
    
    Attributes:
        booking_id: Reference to the booking
        modification_type: Type of modification (date, duration, room_type, multiple)
        requested_by: Who requested the modification
        requested_at: When modification was requested
        modification_reason: Reason for modification
        modify_check_in_date: Whether to modify check-in date
        new_check_in_date: New check-in date if modifying
        modify_duration: Whether to modify duration
        new_duration_months: New duration if modifying
        modify_room_type: Whether to modify room type
        new_room_type: New room type if modifying
        accept_price_change: Whether user accepts price change
        original_total_amount: Original total amount
        new_total_amount: New total amount after modification
        price_difference: Difference in price
        additional_payment_required: Whether additional payment needed
        modification_status: Status of modification request
        approved_at: When modification was approved
        approved_by: Who approved the modification
        rejection_reason: Reason if rejected
        applied_at: When modification was applied
    """

    __tablename__ = "booking_modifications"

    # Foreign Key
    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to booking",
    )

    # Modification Metadata
    modification_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of modification (date, duration, room_type, multiple)",
    )

    requested_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Who requested the modification",
    )

    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When modification was requested",
    )

    modification_reason: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Reason for modification request",
    )

    # Check-in Date Modification
    modify_check_in_date: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether to modify check-in date",
    )

    original_check_in_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Original check-in date",
    )

    new_check_in_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        comment="New check-in date if modifying",
    )

    # Duration Modification
    modify_duration: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether to modify stay duration",
    )

    original_duration_months: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="Original duration in months",
    )

    new_duration_months: Mapped[Optional[int]] = mapped_column(
        Integer,
        nullable=True,
        comment="New duration in months if modifying",
    )

    # Room Type Modification
    modify_room_type: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether to modify room type",
    )

    original_room_type: Mapped[Optional[RoomType]] = mapped_column(
        SQLEnum(RoomType),
        nullable=True,
        comment="Original room type",
    )

    new_room_type: Mapped[Optional[RoomType]] = mapped_column(
        SQLEnum(RoomType),
        nullable=True,
        comment="New room type if modifying",
    )

    # Price Impact
    accept_price_change: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether user accepts price change",
    )

    original_total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Original total amount",
    )

    new_total_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="New total amount after modification",
    )

    price_difference: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Price difference (positive = increase, negative = decrease)",
    )

    additional_payment_required: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether additional payment is required",
    )

    additional_payment_amount: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Additional payment amount if required",
    )

    # Modification Status
    modification_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        index=True,
        comment="Status of modification (pending, approved, rejected, applied)",
    )

    # Approval Details
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When modification was approved",
    )

    approved_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Who approved the modification",
    )

    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason if modification was rejected",
    )

    rejected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When modification was rejected",
    )

    rejected_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Who rejected the modification",
    )

    # Application
    applied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When modification was applied to booking",
    )

    applied_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Who applied the modification",
    )

    # Relationships
    booking: Mapped["Booking"] = relationship(
        "Booking",
        back_populates="modifications",
    )

    requester: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[requested_by],
        lazy="select",
    )

    approver: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[approved_by],
        lazy="select",
    )

    rejecter: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[rejected_by],
        lazy="select",
    )

    applier: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[applied_by],
        lazy="select",
    )

    approval_record: Mapped[Optional["ModificationApprovalRecord"]] = relationship(
        "ModificationApprovalRecord",
        back_populates="modification",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        CheckConstraint(
            "original_total_amount >= 0",
            name="ck_modification_original_positive",
        ),
        CheckConstraint(
            "new_total_amount IS NULL OR new_total_amount >= 0",
            name="ck_modification_new_positive",
        ),
        Index("ix_modification_booking", "booking_id"),
        Index("ix_modification_status", "modification_status"),
        Index("ix_modification_requested_at", "requested_at"),
        {"comment": "Booking modification requests and tracking"},
    )

    # Validators
    @validates("modification_type")
    def validate_modification_type(self, key: str, value: str) -> str:
        """Validate modification type."""
        valid_types = {"date", "duration", "room_type", "multiple"}
        if value.lower() not in valid_types:
            raise ValueError(f"Invalid modification type. Must be one of {valid_types}")
        return value.lower()

    @validates("modification_status")
    def validate_status(self, key: str, value: str) -> str:
        """Validate modification status."""
        valid_statuses = {"pending", "approved", "rejected", "applied", "cancelled"}
        if value.lower() not in valid_statuses:
            raise ValueError(f"Invalid status. Must be one of {valid_statuses}")
        return value.lower()

    @validates("modification_reason")
    def validate_reason(self, key: str, value: str) -> str:
        """Validate modification reason is meaningful."""
        if len(value.strip()) < 10:
            raise ValueError("Modification reason must be at least 10 characters")
        return value.strip()

    @validates("new_check_in_date")
    def validate_new_check_in_date(self, key: str, value: Optional[Date]) -> Optional[Date]:
        """Validate new check-in date."""
        if value and value < Date.today():
            raise ValueError("New check-in date cannot be in the past")
        return value

    @validates("new_duration_months")
    def validate_new_duration(self, key: str, value: Optional[int]) -> Optional[int]:
        """Validate new duration."""
        if value is not None and (value < 1 or value > 24):
            raise ValueError("New duration must be between 1 and 24 months")
        return value

    # Properties
    @property
    def is_pending(self) -> bool:
        """Check if modification is pending approval."""
        return self.modification_status == "pending"

    @property
    def is_approved(self) -> bool:
        """Check if modification is approved."""
        return self.modification_status == "approved"

    @property
    def is_applied(self) -> bool:
        """Check if modification has been applied."""
        return self.modification_status == "applied"

    @property
    def has_price_increase(self) -> bool:
        """Check if modification results in price increase."""
        return self.price_difference is not None and self.price_difference > 0

    @property
    def has_price_decrease(self) -> bool:
        """Check if modification results in price decrease."""
        return self.price_difference is not None and self.price_difference < 0

    # Methods
    def calculate_price_impact(
        self,
        new_monthly_rent: Decimal,
        new_duration: Optional[int] = None
    ) -> None:
        """
        Calculate price impact of modification.
        
        Args:
            new_monthly_rent: New monthly rent amount
            new_duration: New duration if modifying duration
        """
        duration = new_duration if new_duration else self.original_duration_months
        if not duration:
            return
        
        self.new_total_amount = (new_monthly_rent * duration).quantize(Decimal("0.01"))
        self.price_difference = (self.new_total_amount - self.original_total_amount).quantize(
            Decimal("0.01")
        )
        
        if self.price_difference > 0:
            self.additional_payment_required = True
            self.additional_payment_amount = self.price_difference
        else:
            self.additional_payment_required = False
            self.additional_payment_amount = None

    def approve(self, approved_by: UUID) -> None:
        """
        Approve the modification.
        
        Args:
            approved_by: ID of admin approving the modification
        """
        if self.modification_status != "pending":
            raise ValueError("Can only approve pending modifications")
        
        self.modification_status = "approved"
        self.approved_at = datetime.utcnow()
        self.approved_by = approved_by

    def reject(self, rejected_by: UUID, reason: str) -> None:
        """
        Reject the modification.
        
        Args:
            rejected_by: ID of admin rejecting the modification
            reason: Reason for rejection
        """
        if self.modification_status != "pending":
            raise ValueError("Can only reject pending modifications")
        
        self.modification_status = "rejected"
        self.rejected_at = datetime.utcnow()
        self.rejected_by = rejected_by
        self.rejection_reason = reason

    def apply_modification(self, applied_by: UUID) -> None:
        """
        Mark modification as applied.
        
        Args:
            applied_by: ID of admin applying the modification
        """
        if self.modification_status != "approved":
            raise ValueError("Can only apply approved modifications")
        
        self.modification_status = "applied"
        self.applied_at = datetime.utcnow()
        self.applied_by = applied_by

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<BookingModification(id={self.id}, booking_id={self.booking_id}, "
            f"type={self.modification_type}, status={self.modification_status})>"
        )


class ModificationApprovalRecord(UUIDMixin, TimestampModel):
    """
    Admin approval/rejection details for modifications.
    
    Stores detailed approval decision information including
    price adjustments and admin notes.
    
    Attributes:
        modification_id: Reference to modification request
        approved: Whether modification was approved
        adjusted_price: Admin-adjusted price if overriding calculation
        admin_notes: Internal admin notes about decision
        approval_decision_at: When decision was made
        decision_made_by: Admin who made the decision
    """

    __tablename__ = "modification_approval_records"

    # Foreign Key
    modification_id: Mapped[UUID] = mapped_column(
        ForeignKey("booking_modifications.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
        comment="Reference to modification request",
    )

    # Approval Decision
    approved: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        comment="Whether modification was approved",
    )

    # Price Adjustment
    adjusted_price: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 2),
        nullable=True,
        comment="Admin-adjusted price if overriding calculated price",
    )

    price_adjustment_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for price adjustment",
    )

    # Admin Notes
    admin_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Internal admin notes about the decision",
    )

    # Decision Metadata
    approval_decision_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When approval decision was made",
    )

    decision_made_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who made the decision",
    )

    # Relationships
    modification: Mapped["BookingModification"] = relationship(
        "BookingModification",
        back_populates="approval_record",
    )

    decision_maker: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[decision_made_by],
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        CheckConstraint(
            "adjusted_price IS NULL OR adjusted_price >= 0",
            name="ck_approval_adjusted_price_positive",
        ),
        Index("ix_approval_modification", "modification_id"),
        {"comment": "Modification approval decision records"},
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<ModificationApprovalRecord(modification_id={self.modification_id}, "
            f"approved={self.approved})>"
        )
"""
Booking models for managing hostel bookings.

This module defines the core booking entity with comprehensive lifecycle
management, status tracking, and business rule validation.
"""

from datetime import date as Date, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING, List, Optional
from uuid import UUID, uuid4

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
    event,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base.base_model import TimestampModel
from app.models.base.enums import BookingSource, BookingStatus, RoomType
from app.models.base.mixins import AuditMixin, SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.booking.booking_approval import BookingApproval
    from app.models.booking.booking_assignment import BookingAssignment
    from app.models.booking.booking_cancellation import BookingCancellation
    from app.models.booking.booking_conversion import BookingConversion
    from app.models.booking.booking_guest import BookingGuest
    from app.models.booking.booking_modification import BookingModification
    from app.models.booking.booking_waitlist import BookingWaitlist
    from app.models.hostel.hostel import Hostel
    from app.models.payment.payment import Payment
    from app.models.student.student import Student
    from app.models.user.user import User

__all__ = [
    "Booking",
    "BookingStatusHistory",
    "BookingNote",
]


class Booking(UUIDMixin, TimestampModel, SoftDeleteMixin, AuditMixin):
    """
    Core booking entity for hostel reservations.
    
    Manages the complete booking lifecycle from initial request through
    approval, assignment, and conversion to student profile.
    
    Attributes:
        booking_reference: Unique human-readable booking reference
        visitor_id: ID of the visitor making the booking
        hostel_id: ID of the hostel being booked
        room_type_requested: Type of room requested
        preferred_check_in_date: Desired check-in date
        stay_duration_months: Duration of stay in months
        quoted_rent_monthly: Monthly rent quoted at booking time
        total_amount: Total amount for entire stay
        security_deposit: Security deposit amount
        advance_amount: Advance payment required
        advance_paid: Whether advance has been paid
        booking_status: Current status of the booking
        source: Source of the booking (website, app, etc.)
        special_requests: Guest special requests
        dietary_preferences: Dietary preferences
        has_vehicle: Whether guest has a vehicle
        vehicle_details: Vehicle information
        referral_code: Referral code used
        approved_at: When booking was approved
        approved_by: Who approved the booking
        rejected_at: When booking was rejected
        rejected_by: Who rejected the booking
        rejection_reason: Reason for rejection
        cancelled_at: When booking was cancelled
        cancelled_by: Who cancelled the booking
        cancellation_reason: Reason for cancellation
        converted_to_student: Whether converted to student
        conversion_date: When converted to student
        expires_at: When booking expires if not confirmed
    """

    __tablename__ = "bookings"

    # Unique Booking Reference
    booking_reference: Mapped[str] = mapped_column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
        comment="Unique human-readable booking reference (e.g., BK2024010001)",
    )

    # Foreign Keys
    visitor_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Visitor/guest making the booking",
    )

    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
        comment="Hostel being booked",
    )

    # Booking Details
    room_type_requested: Mapped[RoomType] = mapped_column(
        Enum(RoomType),
        nullable=False,
        index=True,
        comment="Type of room requested",
    )

    preferred_check_in_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Preferred check-in date",
    )

    stay_duration_months: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        comment="Duration of stay in months (1-24)",
    )

    # Pricing Information (precision: 10, scale: 2)
    quoted_rent_monthly: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Monthly rent quoted at booking time",
    )

    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        comment="Total amount for entire stay",
    )

    security_deposit: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Security deposit amount",
    )

    advance_amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2),
        nullable=False,
        default=Decimal("0.00"),
        comment="Advance payment required",
    )

    advance_paid: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether advance payment has been made",
    )

    advance_payment_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        comment="Reference to advance payment transaction",
    )

    # Special Requirements
    special_requests: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Special requests or requirements from guest",
    )

    dietary_preferences: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Dietary preferences (vegetarian, vegan, etc.)",
    )

    has_vehicle: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether guest has a vehicle",
    )

    vehicle_details: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Vehicle details (type, registration)",
    )

    # Booking Source
    source: Mapped[BookingSource] = mapped_column(
        Enum(BookingSource),
        nullable=False,
        default=BookingSource.WEBSITE,
        index=True,
        comment="Source of booking",
    )

    referral_code: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        index=True,
        comment="Referral code used",
    )

    # Status
    booking_status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus),
        nullable=False,
        default=BookingStatus.PENDING,
        index=True,
        comment="Current booking status",
    )

    # Approval Details
    approved_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When booking was approved",
    )

    approved_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who approved the booking",
    )

    # Rejection Details
    rejected_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When booking was rejected",
    )

    rejected_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who rejected the booking",
    )

    rejection_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for rejection",
    )

    # Cancellation Details
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When booking was cancelled",
    )

    cancelled_by: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Who cancelled the booking",
    )

    cancellation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for cancellation",
    )

    # Conversion to Student
    converted_to_student: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether booking was converted to student profile",
    )

    student_profile_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("students.id", ondelete="SET NULL"),
        nullable=True,
        comment="Student profile ID if converted",
    )

    conversion_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Date of conversion to student",
    )

    # Expiry
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When booking expires if not confirmed",
    )

    # Booking Date (for tracking when booking was made)
    booking_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When booking was created",
    )

    # Relationships
    visitor: Mapped["User"] = relationship(
        "User",
        foreign_keys=[visitor_id],
        back_populates="bookings_as_visitor",
        lazy="select",
    )

    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        back_populates="bookings",
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

    canceller: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[cancelled_by],
        lazy="select",
    )

    student_profile: Mapped[Optional["Student"]] = relationship(
        "Student",
        back_populates="original_booking",
        lazy="select",
    )

    advance_payment: Mapped[Optional["Payment"]] = relationship(
        "Payment",
        foreign_keys=[advance_payment_id],
        lazy="select",
    )

    # One-to-One Relationships
    guest_info: Mapped[Optional["BookingGuest"]] = relationship(
        "BookingGuest",
        back_populates="booking",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    assignment: Mapped[Optional["BookingAssignment"]] = relationship(
        "BookingAssignment",
        back_populates="booking",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    approval: Mapped[Optional["BookingApproval"]] = relationship(
        "BookingApproval",
        back_populates="booking",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    cancellation: Mapped[Optional["BookingCancellation"]] = relationship(
        "BookingCancellation",
        back_populates="booking",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    conversion: Mapped[Optional["BookingConversion"]] = relationship(
        "BookingConversion",
        back_populates="booking",
        uselist=False,
        cascade="all, delete-orphan",
        lazy="select",
    )

    # One-to-Many Relationships
    status_history: Mapped[List["BookingStatusHistory"]] = relationship(
        "BookingStatusHistory",
        back_populates="booking",
        cascade="all, delete-orphan",
        order_by="BookingStatusHistory.changed_at.desc()",
        lazy="select",
    )

    notes: Mapped[List["BookingNote"]] = relationship(
        "BookingNote",
        back_populates="booking",
        cascade="all, delete-orphan",
        order_by="BookingNote.created_at.desc()",
        lazy="select",
    )

    modifications: Mapped[List["BookingModification"]] = relationship(
        "BookingModification",
        back_populates="booking",
        cascade="all, delete-orphan",
        order_by="BookingModification.created_at.desc()",
        lazy="select",
    )

    payments: Mapped[List["Payment"]] = relationship(
        "Payment",
        foreign_keys="[Payment.booking_id]",
        back_populates="booking",
        lazy="select",
    )

    waitlist_entries: Mapped[List["BookingWaitlist"]] = relationship(
        "BookingWaitlist",
        back_populates="converted_booking",
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        # Indexes for common queries
        Index("ix_booking_hostel_status", "hostel_id", "booking_status"),
        Index("ix_booking_visitor_status", "visitor_id", "booking_status"),
        Index("ix_booking_checkin_date", "preferred_check_in_date"),
        Index("ix_booking_status_created", "booking_status", "created_at"),
        Index("ix_booking_source_status", "source", "booking_status"),
        
        # Check Constraints
        CheckConstraint(
            "stay_duration_months >= 1 AND stay_duration_months <= 24",
            name="ck_booking_duration_range",
        ),
        CheckConstraint(
            "quoted_rent_monthly >= 0",
            name="ck_booking_rent_positive",
        ),
        CheckConstraint(
            "total_amount >= 0",
            name="ck_booking_total_positive",
        ),
        CheckConstraint(
            "security_deposit >= 0",
            name="ck_booking_deposit_positive",
        ),
        CheckConstraint(
            "advance_amount >= 0",
            name="ck_booking_advance_positive",
        ),
        CheckConstraint(
            "advance_amount <= total_amount",
            name="ck_booking_advance_not_exceed_total",
        ),
        
        # Composite unique constraint for reference
        UniqueConstraint("booking_reference", name="uq_booking_reference"),
        
        {"comment": "Core booking entity for hostel reservations"},
    )

    # Validators
    @validates("stay_duration_months")
    def validate_stay_duration(self, key: str, value: int) -> int:
        """Validate stay duration is within acceptable range."""
        if value < 1 or value > 24:
            raise ValueError("Stay duration must be between 1 and 24 months")
        return value

    @validates("quoted_rent_monthly", "total_amount", "security_deposit", "advance_amount")
    def validate_amounts(self, key: str, value: Decimal) -> Decimal:
        """Validate monetary amounts are non-negative."""
        if value < 0:
            raise ValueError(f"{key} cannot be negative")
        return value

    @validates("preferred_check_in_date")
    def validate_check_in_date(self, key: str, value: Date) -> Date:
        """Validate check-in date is reasonable."""
        # Note: This is a soft validation - we don't strictly enforce future dates
        # as bookings might be backdated by admins in some cases
        if value < Date.today() - timedelta(days=30):
            # Log warning for dates more than 30 days in the past
            pass
        return value

    # Properties
    @property
    def expected_check_out_date(self) -> Date:
        """Calculate expected check-out date."""
        return self.preferred_check_in_date + timedelta(days=self.stay_duration_months * 30)

    @property
    def days_until_check_in(self) -> int:
        """Calculate days until check-in."""
        return (self.preferred_check_in_date - Date.today()).days

    @property
    def is_expiring_soon(self) -> bool:
        """Check if booking is expiring within 24 hours."""
        if not self.expires_at:
            return False
        return (self.expires_at - datetime.utcnow()).total_seconds() < 86400

    @property
    def is_expired(self) -> bool:
        """Check if booking has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def balance_amount(self) -> Decimal:
        """Calculate remaining balance after advance."""
        if self.advance_paid:
            return self.total_amount - self.advance_amount
        return self.total_amount

    @property
    def is_long_term_booking(self) -> bool:
        """Check if this is a long-term booking (>= 6 months)."""
        return self.stay_duration_months >= 6

    @property
    def is_pending_approval(self) -> bool:
        """Check if booking is awaiting approval."""
        return self.booking_status == BookingStatus.PENDING

    @property
    def is_active(self) -> bool:
        """Check if booking is in an active state."""
        active_statuses = {
            BookingStatus.PENDING,
            BookingStatus.APPROVED,
            BookingStatus.CONFIRMED,
            BookingStatus.CHECKED_IN,
        }
        return self.booking_status in active_statuses

    # Methods
    def approve(self, approved_by_id: UUID) -> None:
        """
        Approve the booking.
        
        Args:
            approved_by_id: ID of admin approving the booking
        """
        if self.booking_status != BookingStatus.PENDING:
            raise ValueError(f"Cannot approve booking with status {self.booking_status}")
        
        self.booking_status = BookingStatus.APPROVED
        self.approved_by = approved_by_id
        self.approved_at = datetime.utcnow()
        self.expires_at = None  # Remove expiry once approved

    def reject(self, rejected_by_id: UUID, reason: str) -> None:
        """
        Reject the booking.
        
        Args:
            rejected_by_id: ID of admin rejecting the booking
            reason: Reason for rejection
        """
        if self.booking_status != BookingStatus.PENDING:
            raise ValueError(f"Cannot reject booking with status {self.booking_status}")
        
        self.booking_status = BookingStatus.REJECTED
        self.rejected_by = rejected_by_id
        self.rejected_at = datetime.utcnow()
        self.rejection_reason = reason

    def cancel(self, cancelled_by_id: UUID, reason: str) -> None:
        """
        Cancel the booking.
        
        Args:
            cancelled_by_id: ID of user cancelling the booking
            reason: Reason for cancellation
        """
        if self.booking_status in {BookingStatus.CANCELLED, BookingStatus.COMPLETED}:
            raise ValueError(f"Cannot cancel booking with status {self.booking_status}")
        
        self.booking_status = BookingStatus.CANCELLED
        self.cancelled_by = cancelled_by_id
        self.cancelled_at = datetime.utcnow()
        self.cancellation_reason = reason

    def confirm_payment(self, payment_id: UUID) -> None:
        """
        Confirm advance payment.
        
        Args:
            payment_id: ID of the payment transaction
        """
        self.advance_paid = True
        self.advance_payment_id = payment_id
        if self.booking_status == BookingStatus.APPROVED:
            self.booking_status = BookingStatus.CONFIRMED

    def convert_to_student(self, student_id: UUID) -> None:
        """
        Mark booking as converted to student profile.
        
        Args:
            student_id: ID of the created student profile
        """
        if self.booking_status != BookingStatus.CONFIRMED:
            raise ValueError("Only confirmed bookings can be converted to student")
        
        self.converted_to_student = True
        self.student_profile_id = student_id
        self.conversion_date = Date.today()
        self.booking_status = BookingStatus.CHECKED_IN

    def mark_as_completed(self) -> None:
        """Mark booking as completed."""
        self.booking_status = BookingStatus.COMPLETED

    def mark_as_no_show(self) -> None:
        """Mark booking as no-show."""
        self.booking_status = BookingStatus.NO_SHOW

    def set_expiry(self, hours: int = 48) -> None:
        """
        Set booking expiry time.
        
        Args:
            hours: Number of hours until expiry (default: 48)
        """
        self.expires_at = datetime.utcnow() + timedelta(hours=hours)

    def __repr__(self) -> str:
        """String representation of booking."""
        return (
            f"<Booking(id={self.id}, reference={self.booking_reference}, "
            f"status={self.booking_status}, hostel_id={self.hostel_id})>"
        )


class BookingStatusHistory(UUIDMixin, TimestampModel):
    """
    Booking status change history for audit trail.
    
    Tracks all status transitions for a booking with metadata about
    who changed the status and why.
    
    Attributes:
        booking_id: Reference to the booking
        from_status: Previous status
        to_status: New status
        changed_by: User who changed the status
        change_reason: Reason for status change
        changed_at: When status was changed
        metadata: Additional metadata (JSON)
    """

    __tablename__ = "booking_status_history"

    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Booking reference",
    )

    from_status: Mapped[Optional[BookingStatus]] = mapped_column(
        Enum(BookingStatus),
        nullable=True,
        comment="Previous status (NULL for initial status)",
    )

    to_status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus),
        nullable=False,
        comment="New status",
    )

    changed_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who changed the status",
    )

    change_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for status change",
    )

    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When status was changed",
    )

    # Relationships
    booking: Mapped["Booking"] = relationship(
        "Booking",
        back_populates="status_history",
    )

    changer: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[changed_by],
        lazy="select",
    )

    __table_args__ = (
        Index("ix_status_history_booking_changed", "booking_id", "changed_at"),
        {"comment": "Booking status change audit trail"},
    )

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<BookingStatusHistory(booking_id={self.booking_id}, "
            f"{self.from_status} → {self.to_status})>"
        )


class BookingNote(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Internal notes and communications about a booking.
    
    Allows admins to maintain internal notes about bookings
    for communication and tracking purposes.
    
    Attributes:
        booking_id: Reference to the booking
        note_type: Type of note (internal, guest_communication, etc.)
        content: Note content
        created_by: User who created the note
        is_pinned: Whether note is pinned to top
        visibility: Who can see this note (admin_only, all_staff, etc.)
    """

    __tablename__ = "booking_notes"

    booking_id: Mapped[UUID] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Booking reference",
    )

    note_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="internal",
        comment="Type of note (internal, communication, alert, etc.)",
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Note content",
    )

    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="User who created the note",
    )

    is_pinned: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether note is pinned to top",
    )

    visibility: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        default="all_staff",
        comment="Who can see this note",
    )

    # Relationships
    booking: Mapped["Booking"] = relationship(
        "Booking",
        back_populates="notes",
    )

    creator: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[created_by],
        lazy="select",
    )

    __table_args__ = (
        Index("ix_note_booking_created", "booking_id", "created_at"),
        Index("ix_note_booking_pinned", "booking_id", "is_pinned"),
        {"comment": "Internal booking notes and communications"},
    )

    def __repr__(self) -> str:
        """String representation."""
        return f"<BookingNote(booking_id={self.booking_id}, type={self.note_type})>"


# Event Listeners
@event.listens_for(Booking, "before_insert")
def generate_booking_reference(mapper, connection, target):
    """Generate unique booking reference before insert."""
    if not target.booking_reference:
        # Format: BK + YYYYMMDD + 4-digit sequence
        date_prefix = datetime.utcnow().strftime("%Y%m%d")
        # In production, fetch the latest sequence from database
        # For now, using a simple approach with UUID suffix
        sequence = str(uuid4().int)[:4]
        target.booking_reference = f"BK{date_prefix}{sequence}"


@event.listens_for(Booking, "before_update")
def track_status_changes(mapper, connection, target):
    """Track status changes in history table."""
    from sqlalchemy import inspect
    
    state = inspect(target)
    history = state.attrs.booking_status.history
    
    if history.has_changes():
        # Status has changed - create history record
        old_value = history.deleted[0] if history.deleted else None
        new_value = history.added[0] if history.added else target.booking_status
        
        # This will be saved in a separate transaction
        # In production, you might want to handle this differently
        pass  # Actual implementation would create BookingStatusHistory record


@event.listens_for(Booking, "before_insert")
@event.listens_for(Booking, "before_update")
def set_expiry_for_pending(mapper, connection, target):
    """Set expiry time for pending bookings."""
    if target.booking_status == BookingStatus.PENDING and not target.expires_at:
        # Default 48-hour expiry for new pending bookings
        target.expires_at = datetime.utcnow() + timedelta(hours=48)
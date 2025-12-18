"""
Booking waitlist models.

This module defines waitlist management for when hostels are fully booked,
including priority tracking, notifications, and conversions.
"""

from datetime import date as Date, datetime
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
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base.base_model import TimestampModel
from app.models.base.enums import RoomType, WaitlistStatus
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.booking.booking import Booking
    from app.models.hostel.hostel import Hostel
    from app.models.room.bed import Bed
    from app.models.room.room import Room
    from app.models.user.user import User

__all__ = [
    "BookingWaitlist",
    "WaitlistNotification",
]


class BookingWaitlist(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Waitlist entry for fully booked periods.
    
    Manages waitlist when desired room types or dates are not available,
    including priority tracking and notification management.
    
    Attributes:
        hostel_id: Hostel identifier
        visitor_id: Visitor requesting waitlist
        room_type: Desired room type
        preferred_check_in_date: Desired check-in date
        contact_email: Email for notifications
        contact_phone: Phone for notifications
        notes: Additional notes or preferences
        priority: Position in waitlist (1 = first in line)
        status: Current waitlist status
        estimated_availability_date: Estimated when room might be available
        notified_count: Number of times notified
        last_notified_at: When last notification was sent
        converted_to_booking: Whether waitlist was converted to booking
        converted_booking_id: Booking created from waitlist
        conversion_date: When converted to booking
        expires_at: When waitlist entry expires
    """

    __tablename__ = "booking_waitlists"

    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel identifier",
    )

    visitor_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Visitor requesting waitlist",
    )

    # Preferences
    room_type: Mapped[RoomType] = mapped_column(
        SQLEnum(RoomType),
        nullable=False,
        index=True,
        comment="Desired room type",
    )

    preferred_check_in_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Desired check-in date",
    )

    # Contact Information
    contact_email: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Email address for waitlist notifications",
    )

    contact_phone: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Phone number for notifications",
    )

    # Additional Information
    notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Additional notes or preferences",
    )

    # Waitlist Management
    priority: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        index=True,
        comment="Position in waitlist (1 = first in line)",
    )

    status: Mapped[WaitlistStatus] = mapped_column(
        SQLEnum(WaitlistStatus),
        nullable=False,
        default=WaitlistStatus.WAITING,
        index=True,
        comment="Current waitlist status",
    )

    # Availability Estimation
    estimated_availability_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        comment="Estimated date when room might become available",
    )

    # Notification Tracking
    notified_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of times notified about availability",
    )

    last_notified_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When last notification was sent",
    )

    # Conversion Tracking
    converted_to_booking: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether waitlist was converted to booking",
    )

    converted_booking_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("bookings.id", ondelete="SET NULL"),
        nullable=True,
        comment="Booking created from this waitlist entry",
    )

    conversion_date: Mapped[Optional[Date]] = mapped_column(
        SQLDate,
        nullable=True,
        comment="When converted to booking",
    )

    # Expiry
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        index=True,
        comment="When waitlist entry expires",
    )

    # Cancellation
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When waitlist entry was cancelled",
    )

    cancellation_reason: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Reason for cancellation",
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
    )

    visitor: Mapped["User"] = relationship(
        "User",
        foreign_keys=[visitor_id],
        back_populates="waitlist_entries",
        lazy="select",
    )

    converted_booking: Mapped[Optional["Booking"]] = relationship(
        "Booking",
        foreign_keys=[converted_booking_id],
        back_populates="waitlist_entries",
        lazy="select",
    )

    notifications: Mapped[list["WaitlistNotification"]] = relationship(
        "WaitlistNotification",
        back_populates="waitlist",
        cascade="all, delete-orphan",
        order_by="WaitlistNotification.sent_at.desc()",
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        CheckConstraint(
            "priority >= 1",
            name="ck_waitlist_priority_positive",
        ),
        CheckConstraint(
            "notified_count >= 0",
            name="ck_waitlist_notified_positive",
        ),
        Index("ix_waitlist_hostel_room_type", "hostel_id", "room_type"),
        Index("ix_waitlist_visitor_status", "visitor_id", "status"),
        Index("ix_waitlist_status_priority", "status", "priority"),
        Index("ix_waitlist_check_in_date", "preferred_check_in_date"),
        {"comment": "Waitlist entries for fully booked periods"},
    )

    # Validators
    @validates("contact_email")
    def validate_email(self, key: str, value: str) -> str:
        """Validate email format."""
        value = value.strip().lower()
        if "@" not in value or "." not in value:
            raise ValueError("Invalid email format")
        return value

    @validates("contact_phone")
    def validate_phone(self, key: str, value: str) -> str:
        """Validate and normalize phone number."""
        # Remove common formatting characters
        value = value.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if len(value) < 10:
            raise ValueError("Phone number too short")
        return value

    @validates("priority")
    def validate_priority(self, key: str, value: int) -> int:
        """Validate priority is positive."""
        if value < 1:
            raise ValueError("Priority must be at least 1")
        return value

    # Properties
    @property
    def days_on_waitlist(self) -> int:
        """Calculate days on waitlist."""
        return (datetime.utcnow() - self.created_at).days

    @property
    def is_top_priority(self) -> bool:
        """Check if this is the top priority entry."""
        return self.priority == 1

    @property
    def is_expired(self) -> bool:
        """Check if waitlist entry has expired."""
        if not self.expires_at:
            return False
        return datetime.utcnow() > self.expires_at

    @property
    def days_until_check_in(self) -> int:
        """Calculate days until preferred check-in."""
        return (self.preferred_check_in_date - Date.today()).days

    @property
    def is_active(self) -> bool:
        """Check if waitlist entry is active."""
        return (
            self.status == WaitlistStatus.WAITING and
            not self.is_expired and
            not self.cancelled_at
        )

    # Methods
    def notify_availability(self, room_id: UUID, bed_id: UUID) -> "WaitlistNotification":
        """
        Create notification about room availability.
        
        Args:
            room_id: Available room ID
            bed_id: Available bed ID
            
        Returns:
            Created notification record
        """
        self.notified_count += 1
        self.last_notified_at = datetime.utcnow()
        self.status = WaitlistStatus.NOTIFIED
        
        # Create notification record (to be added to session separately)
        from datetime import timedelta
        
        notification = WaitlistNotification(
            waitlist_id=self.id,
            available_room_id=room_id,
            available_bed_id=bed_id,
            response_deadline=datetime.utcnow() + timedelta(hours=24),
        )
        
        return notification

    def convert_to_booking(self, booking_id: UUID) -> None:
        """
        Mark waitlist as converted to booking.
        
        Args:
            booking_id: ID of created booking
        """
        self.converted_to_booking = True
        self.converted_booking_id = booking_id
        self.conversion_date = Date.today()
        self.status = WaitlistStatus.CONVERTED

    def cancel(self, reason: Optional[str] = None) -> None:
        """
        Cancel waitlist entry.
        
        Args:
            reason: Optional cancellation reason
        """
        if self.status == WaitlistStatus.CANCELLED:
            raise ValueError("Waitlist entry is already cancelled")
        
        self.status = WaitlistStatus.CANCELLED
        self.cancelled_at = datetime.utcnow()
        if reason:
            self.cancellation_reason = reason

    def mark_expired(self) -> None:
        """Mark waitlist entry as expired."""
        self.status = WaitlistStatus.EXPIRED

    def update_priority(self, new_priority: int) -> None:
        """
        Update waitlist priority.
        
        Args:
            new_priority: New priority position
        """
        if new_priority < 1:
            raise ValueError("Priority must be at least 1")
        self.priority = new_priority

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<BookingWaitlist(id={self.id}, hostel_id={self.hostel_id}, "
            f"priority={self.priority}, status={self.status})>"
        )


class WaitlistNotification(UUIDMixin, TimestampModel):
    """
    Notification when room becomes available for waitlist.
    
    Tracks notifications sent to waitlisted visitors when their
    desired room type becomes available.
    
    Attributes:
        waitlist_id: Reference to waitlist entry
        available_room_id: ID of available room
        available_bed_id: ID of available bed
        notification_message: Message sent to visitor
        sent_at: When notification was sent
        response_deadline: Deadline for visitor to respond
        visitor_response: Visitor's response (accept/decline)
        response_received_at: When response was received
        booking_link: Direct link to proceed with booking
        notification_channels: Channels used (email, sms, etc.)
    """

    __tablename__ = "waitlist_notifications"

    # Foreign Keys
    waitlist_id: Mapped[UUID] = mapped_column(
        ForeignKey("booking_waitlists.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Reference to waitlist entry",
    )

    available_room_id: Mapped[UUID] = mapped_column(
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID of available room",
    )

    available_bed_id: Mapped[UUID] = mapped_column(
        ForeignKey("beds.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID of available bed",
    )

    # Notification Details
    notification_message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        comment="Message sent to visitor",
    )

    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        index=True,
        comment="When notification was sent",
    )

    response_deadline: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        comment="Deadline for visitor to respond",
    )

    # Response Tracking
    visitor_response: Mapped[Optional[str]] = mapped_column(
        String(20),
        nullable=True,
        comment="Visitor's response (accepted, declined, no_response)",
    )

    response_received_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When response was received",
    )

    # Booking Details
    booking_link: Mapped[Optional[str]] = mapped_column(
        String(500),
        nullable=True,
        comment="Direct link to proceed with booking",
    )

    booking_created: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether visitor proceeded with booking",
    )

    # Delivery
    notification_channels: Mapped[Optional[list]] = mapped_column(
        nullable=True,
        comment="Channels used for notification (email, sms, push)",
    )

    delivery_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default="pending",
        comment="Delivery status of notification",
    )

    # Relationships
    waitlist: Mapped["BookingWaitlist"] = relationship(
        "BookingWaitlist",
        back_populates="notifications",
    )

    available_room: Mapped[Optional["Room"]] = relationship(
        "Room",
        foreign_keys=[available_room_id],
        lazy="select",
    )

    available_bed: Mapped[Optional["Bed"]] = relationship(
        "Bed",
        foreign_keys=[available_bed_id],
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        Index("ix_notification_waitlist", "waitlist_id"),
        Index("ix_notification_sent_at", "sent_at"),
        Index("ix_notification_response", "visitor_response"),
        {"comment": "Waitlist availability notifications"},
    )

    # Validators
    @validates("visitor_response")
    def validate_response(self, key: str, value: Optional[str]) -> Optional[str]:
        """Validate visitor response."""
        if value is not None:
            valid_responses = {"accepted", "declined", "no_response"}
            if value.lower() not in valid_responses:
                raise ValueError(f"Invalid response. Must be one of {valid_responses}")
            return value.lower()
        return value

    @validates("delivery_status")
    def validate_delivery_status(self, key: str, value: str) -> str:
        """Validate delivery status."""
        valid_statuses = {"pending", "sent", "delivered", "failed", "bounced"}
        if value.lower() not in valid_statuses:
            raise ValueError(f"Invalid delivery status. Must be one of {valid_statuses}")
        return value.lower()

    # Properties
    @property
    def hours_until_deadline(self) -> float:
        """Calculate hours remaining until response deadline."""
        delta = self.response_deadline - datetime.utcnow()
        return delta.total_seconds() / 3600

    @property
    def is_expiring_soon(self) -> bool:
        """Check if notification is expiring within 6 hours."""
        return self.hours_until_deadline <= 6

    @property
    def is_expired(self) -> bool:
        """Check if response deadline has passed."""
        return datetime.utcnow() > self.response_deadline

    @property
    def has_response(self) -> bool:
        """Check if visitor has responded."""
        return self.visitor_response is not None

    # Methods
    def record_response(self, response: str) -> None:
        """
        Record visitor's response.
        
        Args:
            response: Visitor's response (accepted/declined)
        """
        valid_responses = {"accepted", "declined"}
        if response.lower() not in valid_responses:
            raise ValueError(f"Response must be one of {valid_responses}")
        
        self.visitor_response = response.lower()
        self.response_received_at = datetime.utcnow()
        
        if response.lower() == "accepted":
            self.booking_created = True

    def mark_delivered(self) -> None:
        """Mark notification as delivered."""
        self.delivery_status = "delivered"

    def mark_failed(self) -> None:
        """Mark notification delivery as failed."""
        self.delivery_status = "failed"

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<WaitlistNotification(waitlist_id={self.waitlist_id}, "
            f"sent_at={self.sent_at}, response={self.visitor_response})>"
        )
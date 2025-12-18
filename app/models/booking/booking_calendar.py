"""
Booking calendar models.

This module defines calendar views, availability tracking, and
booking events for calendar-based booking management.
"""

from datetime import date as Date, datetime
from typing import TYPE_CHECKING, Optional
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date as SQLDate,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship, validates

from app.models.base.base_model import TimestampModel
from app.models.base.enums import BookingStatus
from app.models.base.mixins import SoftDeleteMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.booking.booking import Booking
    from app.models.hostel.hostel import Hostel
    from app.models.room.bed import Bed
    from app.models.room.room import Room

__all__ = [
    "BookingCalendarEvent",
    "DayAvailability",
    "CalendarBlock",
]


class BookingCalendarEvent(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Calendar events for booking visualization.
    
    Represents booking-related events (check-ins, check-outs, bookings)
    for calendar displays and availability management.
    
    Attributes:
        hostel_id: Hostel identifier
        booking_id: Related booking ID (optional for non-booking events)
        event_type: Type of event (check_in, check_out, booking_request, etc.)
        event_date: Date of the event
        event_title: Display title for the event
        event_description: Detailed description
        guest_name: Guest name for display
        room_number: Room number if assigned
        room_type: Room type
        booking_status: Current booking status
        color_code: Display color for calendar
        is_all_day: Whether this is an all-day event
        start_time: Event start time (if not all-day)
        end_time: Event end time (if not all-day)
        metadata: Additional event metadata (JSON)
    """

    __tablename__ = "booking_calendar_events"

    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel identifier",
    )

    booking_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("bookings.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Related booking ID (NULL for non-booking events)",
    )

    room_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("rooms.id", ondelete="SET NULL"),
        nullable=True,
        comment="Related room ID if applicable",
    )

    # Event Details
    event_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of event (check_in, check_out, booking_request, maintenance, blocked)",
    )

    event_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Date of the event",
    )

    event_title: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Display title for the event",
    )

    event_description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description of the event",
    )

    # Display Information
    guest_name: Mapped[Optional[str]] = mapped_column(
        String(255),
        nullable=True,
        comment="Guest name for display",
    )

    room_number: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Room number if assigned",
    )

    room_type: Mapped[Optional[str]] = mapped_column(
        String(50),
        nullable=True,
        comment="Room type",
    )

    booking_status: Mapped[Optional[BookingStatus]] = mapped_column(
        nullable=True,
        comment="Current booking status if applicable",
    )

    # Visual Properties
    color_code: Mapped[str] = mapped_column(
        String(7),
        nullable=False,
        default="#4CAF50",
        comment="Hex color code for calendar display",
    )

    is_all_day: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether this is an all-day event",
    )

    start_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Event start time (if not all-day)",
    )

    end_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="Event end time (if not all-day)",
    )

    # Additional Data
    metadata: Mapped[Optional[dict]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional event metadata (JSON)",
    )

    # Flags
    is_high_priority: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this is a high-priority event",
    )

    requires_action: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether this event requires admin action",
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
    )

    booking: Mapped[Optional["Booking"]] = relationship(
        "Booking",
        foreign_keys=[booking_id],
        lazy="select",
    )

    room: Mapped[Optional["Room"]] = relationship(
        "Room",
        foreign_keys=[room_id],
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        Index("ix_event_hostel_date", "hostel_id", "event_date"),
        Index("ix_event_type_date", "event_type", "event_date"),
        Index("ix_event_booking", "booking_id"),
        Index("ix_event_priority", "is_high_priority"),
        {"comment": "Booking calendar events for visualization"},
    )

    # Validators
    @validates("event_type")
    def validate_event_type(self, key: str, value: str) -> str:
        """Validate event type."""
        valid_types = {
            "check_in", "check_out", "booking_request", "maintenance",
            "blocked", "announcement", "inspection", "other"
        }
        if value.lower() not in valid_types:
            raise ValueError(f"Invalid event type. Must be one of {valid_types}")
        return value.lower()

    @validates("color_code")
    def validate_color_code(self, key: str, value: str) -> str:
        """Validate hex color code format."""
        import re
        if not re.match(r'^#[0-9A-Fa-f]{6}$', value):
            raise ValueError("Color code must be in hex format (#RRGGBB)")
        return value.upper()

    # Properties
    @property
    def is_past_event(self) -> bool:
        """Check if event is in the past."""
        return self.event_date < Date.today()

    @property
    def is_today(self) -> bool:
        """Check if event is today."""
        return self.event_date == Date.today()

    @property
    def is_upcoming(self) -> bool:
        """Check if event is in the future."""
        return self.event_date > Date.today()

    @property
    def days_until_event(self) -> int:
        """Calculate days until event."""
        return (self.event_date - Date.today()).days

    # Methods
    def mark_action_required(self) -> None:
        """Mark event as requiring action."""
        self.requires_action = True

    def clear_action_required(self) -> None:
        """Clear action required flag."""
        self.requires_action = False

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<BookingCalendarEvent(type={self.event_type}, "
            f"date={self.event_date}, hostel_id={self.hostel_id})>"
        )


class DayAvailability(UUIDMixin, TimestampModel):
    """
    Daily bed availability tracking.
    
    Tracks available and occupied beds for each day for capacity
    planning and availability calculations.
    
    Attributes:
        hostel_id: Hostel identifier
        room_id: Room identifier (NULL for hostel-wide)
        availability_date: Date for this availability snapshot
        total_beds: Total number of beds
        available_beds: Number of beds available
        occupied_beds: Number of beds occupied
        reserved_beds: Number of beds reserved
        maintenance_beds: Number of beds under maintenance
        blocked_beds: Number of beds blocked
        is_fully_booked: Whether all beds are booked
        occupancy_rate: Occupancy rate percentage
        active_bookings: List of active booking IDs (JSON)
    """

    __tablename__ = "day_availability"

    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel identifier",
    )

    room_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Room identifier (NULL for hostel-wide availability)",
    )

    # Date
    availability_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Date for this availability snapshot",
    )

    # Bed Counts
    total_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Total number of beds in hostel/room",
    )

    available_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of beds currently available",
    )

    occupied_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of beds currently occupied",
    )

    reserved_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of beds reserved for confirmed bookings",
    )

    maintenance_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of beds under maintenance",
    )

    blocked_beds: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of beds administratively blocked",
    )

    # Status
    is_fully_booked: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        index=True,
        comment="Whether all beds are booked",
    )

    occupancy_rate: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Occupancy rate as percentage (0-100)",
    )

    # Active Bookings
    active_booking_ids: Mapped[Optional[list]] = mapped_column(
        JSON,
        nullable=True,
        comment="List of active booking IDs for this day (JSON array)",
    )

    # Metadata
    last_calculated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=datetime.utcnow,
        comment="When availability was last calculated",
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
    )

    room: Mapped[Optional["Room"]] = relationship(
        "Room",
        foreign_keys=[room_id],
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        CheckConstraint(
            "total_beds >= 0",
            name="ck_availability_total_positive",
        ),
        CheckConstraint(
            "available_beds >= 0",
            name="ck_availability_available_positive",
        ),
        CheckConstraint(
            "occupied_beds >= 0",
            name="ck_availability_occupied_positive",
        ),
        CheckConstraint(
            "reserved_beds >= 0",
            name="ck_availability_reserved_positive",
        ),
        CheckConstraint(
            "maintenance_beds >= 0",
            name="ck_availability_maintenance_positive",
        ),
        CheckConstraint(
            "blocked_beds >= 0",
            name="ck_availability_blocked_positive",
        ),
        CheckConstraint(
            "occupancy_rate >= 0 AND occupancy_rate <= 100",
            name="ck_availability_occupancy_range",
        ),
        CheckConstraint(
            "available_beds + occupied_beds + reserved_beds + maintenance_beds + blocked_beds <= total_beds",
            name="ck_availability_sum_not_exceed_total",
        ),
        Index("ix_availability_hostel_date", "hostel_id", "availability_date"),
        Index("ix_availability_room_date", "room_id", "availability_date"),
        Index("ix_availability_fully_booked", "is_fully_booked"),
        {"comment": "Daily bed availability tracking"},
    )

    # Properties
    @property
    def availability_level(self) -> str:
        """
        Categorize availability level.
        
        Returns: "full", "low", "medium", or "high"
        """
        if self.is_fully_booked or self.available_beds == 0:
            return "full"
        
        if self.total_beds == 0:
            return "full"
        
        availability_percentage = (self.available_beds / self.total_beds) * 100
        
        if availability_percentage >= 50:
            return "high"
        elif availability_percentage >= 20:
            return "medium"
        else:
            return "low"

    @property
    def is_past_date(self) -> bool:
        """Check if this is a past date."""
        return self.availability_date < Date.today()

    @property
    def is_today(self) -> bool:
        """Check if this is today."""
        return self.availability_date == Date.today()

    # Methods
    def calculate_availability(self) -> None:
        """Calculate and update availability metrics."""
        # Calculate available beds
        unavailable = (
            self.occupied_beds +
            self.reserved_beds +
            self.maintenance_beds +
            self.blocked_beds
        )
        self.available_beds = max(0, self.total_beds - unavailable)
        
        # Update fully booked status
        self.is_fully_booked = self.available_beds == 0
        
        # Calculate occupancy rate
        if self.total_beds > 0:
            occupied = self.occupied_beds + self.reserved_beds
            self.occupancy_rate = int((occupied / self.total_beds) * 100)
        else:
            self.occupancy_rate = 0
        
        # Update timestamp
        self.last_calculated_at = datetime.utcnow()

    def add_active_booking(self, booking_id: UUID) -> None:
        """
        Add booking to active bookings list.
        
        Args:
            booking_id: Booking ID to add
        """
        if self.active_booking_ids is None:
            self.active_booking_ids = []
        
        if str(booking_id) not in self.active_booking_ids:
            self.active_booking_ids.append(str(booking_id))

    def remove_active_booking(self, booking_id: UUID) -> None:
        """
        Remove booking from active bookings list.
        
        Args:
            booking_id: Booking ID to remove
        """
        if self.active_booking_ids and str(booking_id) in self.active_booking_ids:
            self.active_booking_ids.remove(str(booking_id))

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<DayAvailability(hostel_id={self.hostel_id}, "
            f"date={self.availability_date}, available={self.available_beds}/{self.total_beds})>"
        )


class CalendarBlock(UUIDMixin, TimestampModel, SoftDeleteMixin):
    """
    Calendar blocking for maintenance or unavailability.
    
    Allows admins to block specific dates or date ranges for
    rooms or the entire hostel.
    
    Attributes:
        hostel_id: Hostel identifier
        room_id: Room identifier (NULL for hostel-wide block)
        bed_id: Bed identifier (NULL for room-wide block)
        block_type: Type of block (maintenance, renovation, inspection, etc.)
        start_date: Block start date
        end_date: Block end date
        reason: Reason for blocking
        description: Detailed description
        blocked_by: Admin who created the block
        is_active: Whether block is currently active
        affects_bookings: Whether to cancel/reject bookings during block
        notification_sent: Whether notification was sent to affected guests
    """

    __tablename__ = "calendar_blocks"

    # Foreign Keys
    hostel_id: Mapped[UUID] = mapped_column(
        ForeignKey("hostels.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
        comment="Hostel identifier",
    )

    room_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Room identifier (NULL for hostel-wide block)",
    )

    bed_id: Mapped[Optional[UUID]] = mapped_column(
        ForeignKey("beds.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
        comment="Bed identifier (NULL for room-wide block)",
    )

    # Block Details
    block_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
        comment="Type of block (maintenance, renovation, inspection, closure, etc.)",
    )

    start_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Block start date",
    )

    end_date: Mapped[Date] = mapped_column(
        SQLDate,
        nullable=False,
        index=True,
        comment="Block end date",
    )

    reason: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Reason for blocking",
    )

    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Detailed description of the block",
    )

    # Metadata
    blocked_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="Admin who created the block",
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
        comment="Whether block is currently active",
    )

    # Booking Impact
    affects_bookings: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        comment="Whether to cancel/reject bookings during block period",
    )

    affected_booking_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        comment="Number of bookings affected by this block",
    )

    # Notifications
    notification_sent: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether notification was sent to affected guests",
    )

    notification_sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When notification was sent",
    )

    # Completion
    is_completed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        comment="Whether the block period/work is completed",
    )

    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        comment="When block was completed",
    )

    completion_notes: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Notes about completion",
    )

    # Relationships
    hostel: Mapped["Hostel"] = relationship(
        "Hostel",
        lazy="select",
    )

    room: Mapped[Optional["Room"]] = relationship(
        "Room",
        foreign_keys=[room_id],
        lazy="select",
    )

    bed: Mapped[Optional["Bed"]] = relationship(
        "Bed",
        foreign_keys=[bed_id],
        lazy="select",
    )

    blocker: Mapped[Optional["User"]] = relationship(
        "User",
        foreign_keys=[blocked_by],
        lazy="select",
    )

    # Table Configuration
    __table_args__ = (
        CheckConstraint(
            "end_date >= start_date",
            name="ck_block_end_after_start",
        ),
        CheckConstraint(
            "affected_booking_count >= 0",
            name="ck_block_affected_count_positive",
        ),
        Index("ix_block_hostel_dates", "hostel_id", "start_date", "end_date"),
        Index("ix_block_room_dates", "room_id", "start_date", "end_date"),
        Index("ix_block_type", "block_type"),
        Index("ix_block_active", "is_active"),
        {"comment": "Calendar blocking for maintenance and unavailability"},
    )

    # Validators
    @validates("block_type")
    def validate_block_type(self, key: str, value: str) -> str:
        """Validate block type."""
        valid_types = {
            "maintenance", "renovation", "inspection", "closure",
            "cleaning", "repair", "upgrade", "other"
        }
        if value.lower() not in valid_types:
            raise ValueError(f"Invalid block type. Must be one of {valid_types}")
        return value.lower()

    @validates("end_date")
    def validate_end_date(self, key: str, value: Date) -> Date:
        """Validate end date is after or equal to start date."""
        if hasattr(self, 'start_date') and value < self.start_date:
            raise ValueError("End date must be after or equal to start date")
        return value

    # Properties
    @property
    def duration_days(self) -> int:
        """Calculate duration in days."""
        return (self.end_date - self.start_date).days + 1

    @property
    def is_current(self) -> bool:
        """Check if block is currently in effect."""
        today = Date.today()
        return self.is_active and self.start_date <= today <= self.end_date

    @property
    def is_upcoming(self) -> bool:
        """Check if block is upcoming."""
        return self.is_active and self.start_date > Date.today()

    @property
    def is_past(self) -> bool:
        """Check if block is in the past."""
        return self.end_date < Date.today()

    @property
    def days_until_start(self) -> int:
        """Calculate days until block starts."""
        return (self.start_date - Date.today()).days

    @property
    def days_until_end(self) -> int:
        """Calculate days until block ends."""
        return (self.end_date - Date.today()).days

    # Methods
    def deactivate(self) -> None:
        """Deactivate the block."""
        self.is_active = False

    def reactivate(self) -> None:
        """Reactivate the block."""
        if self.is_past:
            raise ValueError("Cannot reactivate a past block")
        self.is_active = True

    def mark_completed(self, notes: Optional[str] = None) -> None:
        """
        Mark block as completed.
        
        Args:
            notes: Optional completion notes
        """
        self.is_completed = True
        self.completed_at = datetime.utcnow()
        if notes:
            self.completion_notes = notes

    def send_notification(self) -> None:
        """Mark notification as sent."""
        self.notification_sent = True
        self.notification_sent_at = datetime.utcnow()

    def __repr__(self) -> str:
        """String representation."""
        return (
            f"<CalendarBlock(type={self.block_type}, "
            f"start={self.start_date}, end={self.end_date}, "
            f"hostel_id={self.hostel_id})>"
        )
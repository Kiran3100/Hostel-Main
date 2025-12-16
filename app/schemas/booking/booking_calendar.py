"""
Booking calendar schemas for calendar views and availability tracking.

This module defines schemas for calendar views, booking events,
and availability tracking across dates.
"""

import datetime as dt
from typing import Dict, List, Union
from uuid import UUID

from pydantic import Field, field_validator, computed_field

from app.schemas.common.base import BaseSchema
from app.schemas.common.enums import BookingStatus

__all__ = [
    "CalendarView",
    "DayBookings",
    "BookingEvent",
    "CalendarEvent",
    "AvailabilityCalendar",
    "DayAvailability",
    "BookingInfo",
]


class BookingEvent(BaseSchema):
    """
    Individual booking event for calendar display.
    
    Represents a booking-related event (check-in, check-out, etc.)
    for calendar visualization.
    """

    booking_id: UUID = Field(
        ...,
        description="Booking identifier",
    )
    booking_reference: str = Field(
        ...,
        description="Booking reference number",
    )
    guest_name: str = Field(
        ...,
        description="Guest name",
    )
    room_number: Union[str, None] = Field(
        None,
        description="Assigned room number if available",
    )
    room_type: str = Field(
        ...,
        description="Room type",
    )
    status: BookingStatus = Field(
        ...,
        description="Current booking status",
    )

    # Event Type Flags
    is_check_in: bool = Field(
        False,
        description="Whether this is a check-in event",
    )
    is_check_out: bool = Field(
        False,
        description="Whether this is a check-out event",
    )

    @computed_field
    @property
    def event_type_display(self) -> str:
        """Get display-friendly event type."""
        if self.is_check_in:
            return "Check-in"
        elif self.is_check_out:
            return "Check-out"
        else:
            return "Booking Request"

    @computed_field
    @property
    def status_color(self) -> str:
        """Get color code for status display."""
        color_map = {
            BookingStatus.PENDING: "#FFA500",  # Orange
            BookingStatus.APPROVED: "#4CAF50",  # Green
            BookingStatus.CONFIRMED: "#2196F3",  # Blue
            BookingStatus.CHECKED_IN: "#9C27B0",  # Purple
            BookingStatus.COMPLETED: "#607D8B",  # Gray
            BookingStatus.REJECTED: "#F44336",  # Red
            BookingStatus.CANCELLED: "#9E9E9E",  # Light Gray
            BookingStatus.EXPIRED: "#757575",  # Dark Gray
        }
        return color_map.get(self.status, "#000000")


class DayBookings(BaseSchema):
    """
    All bookings and events for a specific day.
    
    Aggregates check-ins, check-outs, and pending bookings
    for a single calendar day.
    """

    day_date: dt.date = Field(
        ...,
        description="date for this day's bookings",
    )

    # Events by Type
    check_ins: List[BookingEvent] = Field(
        default_factory=list,
        description="Check-in events for this day",
    )
    check_outs: List[BookingEvent] = Field(
        default_factory=list,
        description="Check-out events for this day",
    )
    pending_bookings: List[BookingEvent] = Field(
        default_factory=list,
        description="Pending booking requests for this day",
    )

    # Availability
    available_beds: int = Field(
        ...,
        ge=0,
        description="Number of beds available on this day",
    )
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total number of beds in hostel",
    )

    @computed_field
    @property
    def total_events(self) -> int:
        """Total number of events for this day."""
        return (
            len(self.check_ins)
            + len(self.check_outs)
            + len(self.pending_bookings)
        )

    @computed_field
    @property
    def occupancy_rate(self) -> float:
        """Calculate occupancy rate for this day."""
        if self.total_beds == 0:
            return 0.0
        occupied = self.total_beds - self.available_beds
        return round((occupied / self.total_beds) * 100, 2)

    @computed_field
    @property
    def is_fully_booked(self) -> bool:
        """Check if hostel is fully booked on this day."""
        return self.available_beds == 0

    @computed_field
    @property
    def is_high_activity_day(self) -> bool:
        """Check if this is a high-activity day (many events)."""
        return self.total_events >= 5


class CalendarView(BaseSchema):
    """
    Monthly calendar view of bookings.
    
    Provides a complete calendar view for a specific month
    showing all booking events and availability.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    month: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}$",
        description="Month in YYYY-MM format",
    )

    # Calendar Data (keyed by date string YYYY-MM-DD)
    days: Dict[str, DayBookings] = Field(
        ...,
        description="Bookings organized by date (YYYY-MM-DD as key)",
    )

    # Summary Statistics
    total_check_ins: int = Field(
        ...,
        ge=0,
        description="Total check-ins scheduled this month",
    )
    total_check_outs: int = Field(
        ...,
        ge=0,
        description="Total check-outs scheduled this month",
    )
    peak_occupancy_date: Union[dt.date, None] = Field(
        None,
        description="date with highest occupancy this month",
    )

    # Room Availability by date
    available_rooms_by_date: Dict[str, int] = Field(
        ...,
        description="Available rooms count by date (YYYY-MM-DD as key)",
    )

    @field_validator("month")
    @classmethod
    def validate_month_format(cls, v: str) -> str:
        """Validate month format."""
        try:
            year, month_num = v.split("-")
            year_int = int(year)
            month_int = int(month_num)
            
            if year_int < 2020 or year_int > 2100:
                raise ValueError("Year must be between 2020 and 2100")
            
            if month_int < 1 or month_int > 12:
                raise ValueError("Month must be between 01 and 12")
            
            # Normalize to ensure zero-padding
            return f"{year_int:04d}-{month_int:02d}"
            
        except ValueError as e:
            raise ValueError(f"Invalid month format: {e}")

    @computed_field
    @property
    def total_events(self) -> int:
        """Calculate total events for the month."""
        return self.total_check_ins + self.total_check_outs

    @computed_field
    @property
    def busiest_week_start(self) -> Union[dt.date, None]:
        """Find the start date of the busiest week."""
        if not self.days:
            return None
        
        # This is a simplified calculation
        # In production, you'd calculate this based on actual weekly totals
        return self.peak_occupancy_date


class CalendarEvent(BaseSchema):
    """
    Generic calendar event for various event types.
    
    Supports booking-related events as well as maintenance,
    announcements, and other calendar items.
    """

    event_id: UUID = Field(
        ...,
        description="Unique event identifier",
    )
    event_type: str = Field(
        ...,
        pattern=r"^(check_in|check_out|booking_request|maintenance|announcement|blocked)$",
        description="Type of event",
    )
    title: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Event title",
    )
    start_date: dt.date = Field(
        ...,
        description="Event start date",
    )
    end_date: Union[dt.date, None] = Field(
        None,
        description="Event end date (for multi-day events)",
    )

    # Related Entities
    booking_id: Union[UUID, None] = Field(
        None,
        description="Related booking ID if applicable",
    )
    room_id: Union[UUID, None] = Field(
        None,
        description="Related room ID if applicable",
    )

    # Display Properties
    color: str = Field(
        ...,
        pattern=r"^#[0-9A-Fa-f]{6}$",
        description="Hex color code for event display",
    )
    is_all_day: bool = Field(
        True,
        description="Whether this is an all-day event",
    )

    @field_validator("end_date")
    @classmethod
    def validate_end_date(cls, v: Union[dt.date, None], info) -> Union[dt.date, None]:
        """Validate end date is after or equal to start date."""
        start_date = info.data.get("start_date")
        if v is not None and start_date is not None:
            if v < start_date:
                raise ValueError(
                    f"End date ({v}) cannot be before start date ({start_date})"
                )
        return v

    @computed_field
    @property
    def duration_days(self) -> int:
        """Calculate event duration in days."""
        if self.end_date is None:
            return 1
        return (self.end_date - self.start_date).days + 1

    @computed_field
    @property
    def is_past_event(self) -> bool:
        """Check if event is in the past."""
        event_end = self.end_date or self.start_date
        return event_end < dt.date.today()


class DayAvailability(BaseSchema):
    """
    Bed availability for a specific day.
    
    Tracks available and booked beds for capacity planning.
    """

    day_date: dt.date = Field(
        ...,
        description="date for this availability snapshot",
    )
    total_beds: int = Field(
        ...,
        ge=0,
        description="Total number of beds in hostel/room",
    )
    available_beds: int = Field(
        ...,
        ge=0,
        description="Number of beds currently available",
    )
    booked_beds: int = Field(
        ...,
        ge=0,
        description="Number of beds currently booked",
    )
    is_fully_booked: bool = Field(
        ...,
        description="Whether all beds are booked",
    )

    # Active Bookings
    active_bookings: List[UUID] = Field(
        default_factory=list,
        description="List of active booking IDs for this day",
    )

    @field_validator("booked_beds")
    @classmethod
    def validate_booked_beds(cls, v: int, info) -> int:
        """Validate booked beds doesn't exceed total."""
        total_beds = info.data.get("total_beds")
        if total_beds is not None and v > total_beds:
            raise ValueError(
                f"Booked beds ({v}) cannot exceed total beds ({total_beds})"
            )
        return v

    @field_validator("available_beds")
    @classmethod
    def validate_available_beds(cls, v: int, info) -> int:
        """Validate available beds calculation."""
        total_beds = info.data.get("total_beds")
        booked_beds = info.data.get("booked_beds")
        
        if total_beds is not None and booked_beds is not None:
            expected_available = total_beds - booked_beds
            if v != expected_available:
                raise ValueError(
                    f"Available beds ({v}) should equal "
                    f"total ({total_beds}) - booked ({booked_beds}) = {expected_available}"
                )
        
        return v

    @computed_field
    @property
    def occupancy_rate(self) -> float:
        """Calculate occupancy rate as percentage."""
        if self.total_beds == 0:
            return 0.0
        return round((self.booked_beds / self.total_beds) * 100, 2)

    @computed_field
    @property
    def availability_level(self) -> str:
        """
        Categorize availability level.
        
        Returns: "high", "medium", "low", or "full"
        """
        if self.is_fully_booked:
            return "full"
        
        availability_percentage = (self.available_beds / self.total_beds) * 100
        
        if availability_percentage >= 50:
            return "high"
        elif availability_percentage >= 20:
            return "medium"
        else:
            return "low"


class AvailabilityCalendar(BaseSchema):
    """
    Room availability calendar for a month.
    
    Provides daily availability tracking for capacity planning
    and booking management.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel identifier",
    )
    room_id: Union[UUID, None] = Field(
        None,
        description="Specific room ID, or None for all rooms",
    )
    month: str = Field(
        ...,
        pattern=r"^\d{4}-\d{2}$",
        description="Month in YYYY-MM format",
    )

    # Availability by date
    availability: Dict[str, DayAvailability] = Field(
        ...,
        description="Daily availability keyed by date (YYYY-MM-DD)",
    )

    @field_validator("month")
    @classmethod
    def validate_month_format(cls, v: str) -> str:
        """Validate and normalize month format."""
        try:
            year, month_num = v.split("-")
            year_int = int(year)
            month_int = int(month_num)
            
            if year_int < 2020 or year_int > 2100:
                raise ValueError("Year must be between 2020 and 2100")
            
            if month_int < 1 or month_int > 12:
                raise ValueError("Month must be between 01 and 12")
            
            return f"{year_int:04d}-{month_int:02d}"
            
        except ValueError as e:
            raise ValueError(f"Invalid month format: {e}")

    @computed_field
    @property
    def average_occupancy_rate(self) -> float:
        """Calculate average occupancy rate for the month."""
        if not self.availability:
            return 0.0
        
        total_rate = sum(day.occupancy_rate for day in self.availability.values())
        return round(total_rate / len(self.availability), 2)

    @computed_field
    @property
    def days_fully_booked(self) -> int:
        """Count number of days that are fully booked."""
        return sum(1 for day in self.availability.values() if day.is_fully_booked)

    @computed_field
    @property
    def peak_occupancy_date(self) -> Union[str, None]:
        """Find date with highest occupancy."""
        if not self.availability:
            return None
        
        peak_day = max(
            self.availability.items(),
            key=lambda x: x[1].occupancy_rate
        )
        return peak_day[0]


class BookingInfo(BaseSchema):
    """Basic booking information for availability calendar."""
    
    booking_id: UUID = Field(..., description="Booking identifier")
    student_name: str = Field(..., description="Student/guest name")
    check_in_date: dt.date = Field(..., description="Check-in date")
    check_out_date: dt.date = Field(..., description="Check-out date")
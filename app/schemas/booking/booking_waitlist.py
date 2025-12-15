# --- File: app/schemas/booking/booking_waitlist.py ---
"""
Booking waitlist schemas for managing waiting lists.

This module defines schemas for waitlist management when hostels
are fully booked, including notifications and conversions.
"""

from __future__ import annotations

from datetime import date as Date, datetime
from typing import List, Optional
from uuid import UUID

from pydantic import EmailStr, Field, field_validator, computed_field

from app.schemas.common.base import BaseCreateSchema, BaseResponseSchema, BaseSchema
from app.schemas.common.enums import RoomType, WaitlistStatus

__all__ = [
    "WaitlistRequest",
    "WaitlistResponse",
    "WaitlistStatusInfo",
    "WaitlistNotification",
    "WaitlistConversion",
    "WaitlistCancellation",
    "WaitlistManagement",
    "WaitlistEntry",
]


class WaitlistRequest(BaseCreateSchema):
    """
    Request to add visitor to waitlist.
    
    Used when desired room type/Date is not available
    and visitor wants to be notified when it becomes available.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel ID for waitlist",
    )
    visitor_id: UUID = Field(
        ...,
        description="Visitor ID requesting waitlist",
    )

    # Preferences
    room_type: RoomType = Field(
        ...,
        description="Desired room type",
    )
    preferred_check_in_date: Date = Field(
        ...,
        description="Desired check-in Date",
    )

    # Contact Information
    contact_email: EmailStr = Field(
        ...,
        description="Email address for waitlist notifications",
    )
    contact_phone: str = Field(
        ...,
        pattern=r"^\+?[1-9]\d{9,14}$",
        description="Phone number for notifications",
    )

    # Additional Information
    notes: Optional[str] = Field(
        None,
        max_length=500,
        description="Additional notes or preferences",
    )

    @field_validator("preferred_check_in_date")
    @classmethod
    def validate_check_in_date(cls, v: Date) -> Date:
        """Validate check-in Date is in the future."""
        if v < Date.today():
            raise ValueError(
                f"Preferred check-in Date ({v.strftime('%Y-%m-%d')}) "
                "cannot be in the past"
            )
        return v

    @field_validator("contact_phone")
    @classmethod
    def normalize_phone(cls, v: str) -> str:
        """Normalize phone number."""
        return v.replace(" ", "").replace("-", "")

    @field_validator("notes")
    @classmethod
    def clean_notes(cls, v: Optional[str]) -> Optional[str]:
        """Clean notes field."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class WaitlistResponse(BaseResponseSchema):
    """
    Response after adding to waitlist.
    
    Confirms waitlist entry with position and estimated timeline.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    visitor_id: UUID = Field(
        ...,
        description="Visitor ID",
    )

    # Waitlist Details
    room_type: RoomType = Field(
        ...,
        description="Room type on waitlist",
    )
    preferred_check_in_date: Date = Field(
        ...,
        description="Preferred check-in Date",
    )

    # Contact
    contact_email: str = Field(
        ...,
        description="Contact email",
    )
    contact_phone: str = Field(
        ...,
        description="Contact phone",
    )

    # Position and Status
    priority: int = Field(
        ...,
        ge=1,
        description="Position in waitlist (1 = first in line)",
    )
    status: WaitlistStatus = Field(
        ...,
        description="Current waitlist status",
    )

    # Estimated Timeline
    estimated_availability_date: Optional[Date] = Field(
        None,
        description="Estimated Date when room might become available",
    )

    created_at: datetime = Field(
        ...,
        description="When added to waitlist",
    )

    @computed_field
    @property
    def days_on_waitlist(self) -> int:
        """Calculate days on waitlist."""
        return (datetime.utcnow() - self.created_at).days

    @computed_field
    @property
    def is_top_priority(self) -> bool:
        """Check if this is the top priority entry."""
        return self.priority == 1


class WaitlistStatusInfo(BaseSchema):
    """
    Current waitlist status for a visitor.
    
    Provides detailed status information about waitlist position
    and notifications.
    """

    waitlist_id: UUID = Field(
        ...,
        description="Waitlist entry ID",
    )
    hostel_name: str = Field(
        ...,
        description="Hostel name",
    )
    room_type: str = Field(
        ...,
        description="Room type",
    )

    # Position Information
    position: int = Field(
        ...,
        ge=1,
        description="Current position in queue (1 = next in line)",
    )
    total_in_queue: int = Field(
        ...,
        ge=1,
        description="Total number of people in this waitlist",
    )

    # Status
    status: str = Field(
        ...,
        pattern=r"^(waiting|notified|converted|expired|cancelled)$",
        description="Current waitlist status",
    )

    # Notification Tracking
    last_notification_sent: Optional[datetime] = Field(
        None,
        description="When last notification was sent",
    )
    notification_count: int = Field(
        0,
        ge=0,
        description="Number of notifications sent",
    )

    # Wait Estimation
    estimated_wait_days: Optional[int] = Field(
        None,
        ge=0,
        description="Estimated days until availability",
    )

    @computed_field
    @property
    def position_percentage(self) -> float:
        """Calculate position as percentage of queue."""
        if self.total_in_queue == 0:
            return 0.0
        return round((self.position / self.total_in_queue) * 100, 2)

    @computed_field
    @property
    def is_next_in_line(self) -> bool:
        """Check if visitor is next in line."""
        return self.position == 1


class WaitlistNotification(BaseSchema):
    """
    Notification when room becomes available.
    
    Sent to waitlisted visitor when their desired room/bed
    becomes available.
    """

    waitlist_id: UUID = Field(
        ...,
        description="Waitlist entry ID",
    )
    visitor_id: UUID = Field(
        ...,
        description="Visitor ID to notify",
    )
    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )

    # Availability Details
    message: str = Field(
        ...,
        description="Notification message",
    )
    available_room_id: UUID = Field(
        ...,
        description="ID of available room",
    )
    available_bed_id: UUID = Field(
        ...,
        description="ID of available bed",
    )

    # Action Required
    response_deadline: datetime = Field(
        ...,
        description="Deadline to respond to this notification",
    )

    # Booking Link
    booking_link: str = Field(
        ...,
        description="Direct link to proceed with booking",
    )

    @computed_field
    @property
    def hours_until_deadline(self) -> float:
        """Calculate hours remaining until response deadline."""
        delta = self.response_deadline - datetime.utcnow()
        return round(delta.total_seconds() / 3600, 1)

    @computed_field
    @property
    def is_expiring_soon(self) -> bool:
        """Check if notification is expiring within 6 hours."""
        return self.hours_until_deadline <= 6


class WaitlistConversion(BaseCreateSchema):
    """
    Convert waitlist entry to booking.
    
    Visitor's response to availability notification.
    """

    waitlist_id: UUID = Field(
        ...,
        description="Waitlist entry ID",
    )
    accept: bool = Field(
        ...,
        description="Whether to accept the available room (True/False)",
    )

    # If Accepting
    proceed_with_booking: bool = Field(
        True,
        description="Whether to proceed with creating booking",
    )


class WaitlistCancellation(BaseCreateSchema):
    """
    Remove entry from waitlist.
    
    Visitor can cancel their waitlist entry at any time.
    """

    waitlist_id: UUID = Field(
        ...,
        description="Waitlist entry ID to cancel",
    )
    cancellation_reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Reason for cancelling waitlist entry",
    )

    @field_validator("cancellation_reason")
    @classmethod
    def clean_reason(cls, v: Optional[str]) -> Optional[str]:
        """Clean cancellation reason."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
        return v


class WaitlistEntry(BaseSchema):
    """
    Individual waitlist entry for admin view.
    
    Detailed information about a single waitlist entry
    for management purposes.
    """

    waitlist_id: UUID = Field(
        ...,
        description="Waitlist entry ID",
    )
    visitor_name: str = Field(
        ...,
        description="Visitor name",
    )
    contact_email: str = Field(
        ...,
        description="Contact email",
    )
    contact_phone: str = Field(
        ...,
        description="Contact phone",
    )

    # Preferences
    preferred_check_in_date: Date = Field(
        ...,
        description="Preferred check-in Date",
    )
    priority: int = Field(
        ...,
        ge=1,
        description="Position in waitlist",
    )
    status: WaitlistStatus = Field(
        ...,
        description="Current status",
    )

    # Tracking
    days_waiting: int = Field(
        ...,
        ge=0,
        description="Number of days on waitlist",
    )
    created_at: datetime = Field(
        ...,
        description="When added to waitlist",
    )

    @computed_field
    @property
    def is_long_wait(self) -> bool:
        """Check if entry has been waiting a long time (>30 days)."""
        return self.days_waiting > 30


class WaitlistManagement(BaseSchema):
    """
    Waitlist management view for admins.
    
    Provides overview of all waitlist entries for a specific
    hostel and room type.
    """

    hostel_id: UUID = Field(
        ...,
        description="Hostel ID",
    )
    room_type: RoomType = Field(
        ...,
        description="Room type for this waitlist",
    )

    # Summary
    total_in_waitlist: int = Field(
        ...,
        ge=0,
        description="Total number of entries in waitlist",
    )

    # Entries
    entries: List[WaitlistEntry] = Field(
        default_factory=list,
        description="List of waitlist entries ordered by priority",
    )

    @computed_field
    @property
    def average_wait_days(self) -> float:
        """Calculate average wait time in days."""
        if not self.entries:
            return 0.0
        
        total_days = sum(entry.days_waiting for entry in self.entries)
        return round(total_days / len(self.entries), 1)

    @computed_field
    @property
    def longest_wait_days(self) -> int:
        """Find longest wait time in days."""
        if not self.entries:
            return 0
        
        return max(entry.days_waiting for entry in self.entries)
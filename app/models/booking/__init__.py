"""
Booking models package.

This module exports all booking-related models for easy importing
across the application.
"""

from app.models.booking.booking import (
    Booking,
    BookingNote,
    BookingStatusHistory,
)
from app.models.booking.booking_approval import (
    ApprovalSettings,
    BookingApproval,
    RejectionRecord,
)
from app.models.booking.booking_assignment import (
    AssignmentHistory,
    BookingAssignment,
)
from app.models.booking.booking_calendar import (
    BookingCalendarEvent,
    CalendarBlock,
    DayAvailability,
)
from app.models.booking.booking_cancellation import (
    BookingCancellation,
    CancellationPolicy,
    RefundTransaction,
)
from app.models.booking.booking_conversion import (
    BookingConversion,
    ChecklistItem,
    ConversionChecklist,
)
from app.models.booking.booking_guest import (
    BookingGuest,
    GuestDocument,
)
from app.models.booking.booking_modification import (
    BookingModification,
    ModificationApprovalRecord,
)
from app.models.booking.booking_waitlist import (
    BookingWaitlist,
    WaitlistNotification,
)


__all__ = [
    # Core Booking
    "Booking",
    "BookingStatusHistory",
    "BookingNote",
    # Guest Information
    "BookingGuest",
    "GuestDocument",
    # Assignment
    "BookingAssignment",
    "AssignmentHistory",
    # Approval
    "BookingApproval",
    "RejectionRecord",
    "ApprovalSettings",
    # Cancellation
    "BookingCancellation",
    "CancellationPolicy",
    "RefundTransaction",
    # Conversion
    "BookingConversion",
    "ConversionChecklist",
    "ChecklistItem",
    # Modification
    "BookingModification",
    "ModificationApprovalRecord",
    # Calendar
    "BookingCalendarEvent",
    "DayAvailability",
    "CalendarBlock",
    # Waitlist
    "BookingWaitlist",
    "WaitlistNotification",
]
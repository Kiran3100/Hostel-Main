# app/repositories/booking/__init__.py
"""
Booking repositories package.

Exports all booking-related repositories for easy importing.
"""

from app.repositories.booking.booking_aggregate_repository import (
    BookingAggregateRepository,
)
from app.repositories.booking.booking_approval_repository import (
    ApprovalSettingsRepository,
    BookingApprovalRepository,
    RejectionRecordRepository,
)
from app.repositories.booking.booking_assignment_repository import (
    BookingAssignmentRepository,
)
from app.repositories.booking.booking_calendar_repository import (
    BookingCalendarEventRepository,
    CalendarBlockRepository,
    DayAvailabilityRepository,
)
from app.repositories.booking.booking_cancellation_repository import (
    BookingCancellationRepository,
    CancellationPolicyRepository,
    RefundTransactionRepository,
)
from app.repositories.booking.booking_conversion_repository import (
    BookingConversionRepository,
    ConversionChecklistRepository,
)
from app.repositories.booking.booking_guest_repository import (
    BookingGuestRepository,
    GuestDocumentRepository,
)
from app.repositories.booking.booking_modification_repository import (
    BookingModificationRepository,
    ModificationApprovalRecordRepository,
)
from app.repositories.booking.booking_repository import (
    BookingRepository,
    BookingSearchCriteria,
    BookingStatistics,
)
from app.repositories.booking.booking_waitlist_repository import (
    BookingWaitlistRepository,
    WaitlistNotificationRepository,
)

__all__ = [
    # Main Booking
    "BookingRepository",
    "BookingSearchCriteria",
    "BookingStatistics",
    # Approval
    "BookingApprovalRepository",
    "ApprovalSettingsRepository",
    "RejectionRecordRepository",
    # Assignment
    "BookingAssignmentRepository",
    # Calendar
    "BookingCalendarEventRepository",
    "DayAvailabilityRepository",
    "CalendarBlockRepository",
    # Cancellation
    "BookingCancellationRepository",
    "CancellationPolicyRepository",
    "RefundTransactionRepository",
    # Conversion
    "BookingConversionRepository",
    "ConversionChecklistRepository",
    # Guest
    "BookingGuestRepository",
    "GuestDocumentRepository",
    # Modification
    "BookingModificationRepository",
    "ModificationApprovalRecordRepository",
    # Waitlist
    "BookingWaitlistRepository",
    "WaitlistNotificationRepository",
    # Aggregate
    "BookingAggregateRepository",
]

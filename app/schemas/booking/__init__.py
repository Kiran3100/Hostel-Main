"""
Booking schemas package.

This module exports all booking-related schemas for easy importing
across the application.
"""

from app.schemas.booking.booking_approval import (
    ApprovalResponse,
    ApprovalSettings,
    BookingApprovalRequest,
    BulkApprovalRequest,
    RejectionRequest,
)
from app.schemas.booking.booking_assignment import (
    AssignmentRequest,
    AssignmentResponse,
    BedAssignment,
    BulkAssignmentRequest,
    ReassignmentRequest,
    RoomAssignment,
    SingleAssignment,
)
from app.schemas.booking.booking_base import (
    BookingBase,
    BookingCreate,
    BookingUpdate,
)
from app.schemas.booking.booking_calendar import (
    AvailabilityCalendar,
    BookingEvent,
    BookingInfo,
    CalendarEvent,
    CalendarView,
    DayAvailability,
    DayBookings,
)
from app.schemas.booking.booking_cancellation import (
    BulkCancellation,
    CancellationCharge,
    CancellationPolicy,
    CancellationRequest,
    CancellationResponse,
    RefundCalculation,
)
from app.schemas.booking.booking_conversion import (
    BulkConversion,
    ChecklistItem,
    ConversionChecklist,
    ConversionResponse,
    ConversionRollback,
    ConvertToStudentRequest,
)
from app.schemas.booking.booking_filters import (
    BookingAnalyticsRequest,
    BookingExportRequest,
    BookingFilterParams,
    BookingSearchRequest,
    BookingSortOptions,
)
from app.schemas.booking.booking_modification import (
    DateChangeRequest,
    DurationChangeRequest,
    ModificationApproval,
    ModificationRequest,
    ModificationResponse,
    RoomTypeChangeRequest,
)
from app.schemas.booking.booking_request import (
    BookingInquiry,
    BookingRequest,
    GuestInformation,
    QuickBookingRequest,
)
from app.schemas.booking.booking_response import (
    BookingConfirmation,
    BookingDetail,
    BookingListItem,
    BookingResponse,
)
from app.schemas.booking.booking_waitlist import (
    WaitlistCancellation,
    WaitlistConversion,
    WaitlistEntry,
    WaitlistManagement,
    WaitlistNotification,
    WaitlistRequest,
    WaitlistResponse,
    WaitlistStatusInfo,
)

__all__ = [
    # Base
    "BookingBase",
    "BookingCreate",
    "BookingUpdate",
    # Request
    "BookingRequest",
    "GuestInformation",
    "BookingInquiry",
    "QuickBookingRequest",
    # Response
    "BookingResponse",
    "BookingDetail",
    "BookingListItem",
    "BookingConfirmation",
    # Approval
    "BookingApprovalRequest",
    "ApprovalResponse",
    "RejectionRequest",
    "BulkApprovalRequest",
    "ApprovalSettings",
    # Assignment
    "RoomAssignment",
    "BedAssignment",
    "AssignmentRequest",
    "AssignmentResponse",
    "BulkAssignmentRequest",
    "SingleAssignment",
    "ReassignmentRequest",
    # Cancellation
    "CancellationRequest",
    "CancellationResponse",
    "RefundCalculation",
    "CancellationPolicy",
    "CancellationCharge",
    "BulkCancellation",
    # Modification
    "ModificationRequest",
    "ModificationResponse",
    "DateChangeRequest",
    "DurationChangeRequest",
    "RoomTypeChangeRequest",
    "ModificationApproval",
    # Calendar
    "CalendarView",
    "DayBookings",
    "BookingEvent",
    "CalendarEvent",
    "AvailabilityCalendar",
    "DayAvailability",
    "BookingInfo",
    # Waitlist
    "WaitlistRequest",
    "WaitlistResponse",
    "WaitlistStatusInfo",
    "WaitlistNotification",
    "WaitlistConversion",
    "WaitlistCancellation",
    "WaitlistManagement",
    "WaitlistEntry",
    # Conversion
    "ConvertToStudentRequest",
    "ConversionResponse",
    "ConversionChecklist",
    "ChecklistItem",
    "BulkConversion",
    "ConversionRollback",
    # Filters
    "BookingFilterParams",
    "BookingSearchRequest",
    "BookingSortOptions",
    "BookingExportRequest",
    "BookingAnalyticsRequest",
]
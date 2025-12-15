# app/services/booking/__init__.py
"""
Booking services package.

- BookingService: core booking CRUD, list/search, status, confirmations.
- BookingCalendarService: calendar & availability views.
- BookingCancellationService: cancellation & refund calculation.
- BookingConversionService: convert bookings to Student profiles.
- BookingModificationService: date/duration/room-type modifications.
- BookingWaitlistService: waitlist creation & management (store-based).
- BookingWorkflowService: wrapper over wf_booking.
- BookingAnalyticsService: booking analytics & KPIs.
"""

from .booking_service import BookingService
from .booking_calendar_service import BookingCalendarService
from .booking_cancellation_service import BookingCancellationService
from .booking_conversion_service import BookingConversionService
from .booking_modification_service import BookingModificationService
from .booking_waitlist_service import BookingWaitlistService
from .booking_workflow_service import BookingWorkflowService
from .booking_analytics_service import BookingAnalyticsService
from .booking_approval_service import BookingApprovalService


__all__ = [
    "BookingService",
    "BookingCalendarService",
    "BookingCancellationService",
    "BookingConversionService",
    "BookingModificationService",
    "BookingWaitlistService",
    "BookingWorkflowService",
    "BookingAnalyticsService",
    "BookingApprovalService",

]
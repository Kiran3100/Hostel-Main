"""
Booking service layer.

Provides business logic for:
- Booking creation/update and search
- Approval workflow
- Assignment/reassignment
- Calendar & availability views
- Cancellation & refund flows
- Conversion to student/resident
- Guest details & document workflows
- Post-creation modification requests & approvals
- Pricing/quote calculation
- Waitlist management
- Booking notifications

Version: 2.0.0
Enhanced with improved error handling, validation, logging, and performance optimizations.
"""

from app.services.booking.booking_service import BookingService
from app.services.booking.booking_search_service import BookingSearchService
from app.services.booking.booking_approval_service import BookingApprovalService
from app.services.booking.booking_assignment_service import BookingAssignmentService
from app.services.booking.booking_calendar_service import BookingCalendarService
from app.services.booking.booking_cancellation_service import BookingCancellationService
from app.services.booking.booking_conversion_service import BookingConversionService
from app.services.booking.booking_guest_service import BookingGuestService
from app.services.booking.booking_modification_service import BookingModificationService
from app.services.booking.booking_notification_service import BookingNotificationService
from app.services.booking.booking_pricing_service import BookingPricingService
from app.services.booking.booking_waitlist_service import BookingWaitlistService

__all__ = [
    "BookingService",
    "BookingSearchService",
    "BookingApprovalService",
    "BookingAssignmentService",
    "BookingCalendarService",
    "BookingCancellationService",
    "BookingConversionService",
    "BookingGuestService",
    "BookingModificationService",
    "BookingNotificationService",
    "BookingPricingService",
    "BookingWaitlistService",
]

__version__ = "2.0.0"
__author__ = "Hostel Management System Team"
__description__ = "Enhanced booking services with comprehensive validation, logging, and performance optimization"

# Service initialization helper
def get_all_services():
    """
    Get dictionary of all available booking services.
    
    Returns:
        Dict mapping service names to service classes
    """
    return {
        "booking": BookingService,
        "search": BookingSearchService,
        "approval": BookingApprovalService,
        "assignment": BookingAssignmentService,
        "calendar": BookingCalendarService,
        "cancellation": BookingCancellationService,
        "conversion": BookingConversionService,
        "guest": BookingGuestService,
        "modification": BookingModificationService,
        "notification": BookingNotificationService,
        "pricing": BookingPricingService,
        "waitlist": BookingWaitlistService,
    }

# Service categories for documentation
SERVICE_CATEGORIES = {
    "core": ["booking", "search"],
    "workflow": ["approval", "assignment", "modification"],
    "financial": ["pricing", "cancellation"],
    "communication": ["notification"],
    "capacity": ["calendar", "waitlist"],
    "user_data": ["guest", "conversion"],
}

def get_services_by_category(category: str):
    """
    Get services belonging to a specific category.
    
    Args:
        category: Category name (core, workflow, financial, communication, capacity, user_data)
        
    Returns:
        List of service names in the category
    """
    return SERVICE_CATEGORIES.get(category, [])
# app/repositories/visitor/__init__.py
from .visitor_repository import VisitorRepository
from .visitor_hostel_repository import VisitorHostelRepository
from .hostel_booking_repository import HostelBookingRepository
from .hostel_review_repository import HostelReviewRepository

__all__ = [
    "VisitorRepository",
    "VisitorHostelRepository",
    "HostelBookingRepository",
    "HostelReviewRepository",
]
# app/services/inquiry/__init__.py
"""
Inquiry-related services.

- InquiryService: core inquiry CRUD, listing, status updates.
- InquiryAssignmentService: assign inquiries to admins/staff (contact owner).
"""

from .inquiry_service import InquiryService
from .inquiry_assignment_service import InquiryAssignmentService

__all__ = [
    "InquiryService",
    "InquiryAssignmentService",
]
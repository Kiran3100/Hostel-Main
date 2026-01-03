# app/services/student/__init__.py
"""
Student Services Package
"""

from .guardian_contact_service import GuardianContactService
from .room_transfer_service import RoomTransferService
from .student_aggregate_service import StudentAggregateService  # Add this
from .student_checkout_service import StudentCheckoutService
from .student_communication_service import StudentCommunicationService
from .student_document_service import StudentDocumentService
from .student_onboarding_service import StudentOnboardingService
from .student_preference_service import StudentPreferenceService
from .student_profile_service import StudentProfileService
from .student_service import StudentService

__all__ = [
    "GuardianContactService",
    "RoomTransferService",
    "StudentAggregateService",  # Add this
    "StudentCheckoutService",
    "StudentCommunicationService",
    "StudentDocumentService",
    "StudentOnboardingService",
    "StudentPreferenceService",
    "StudentProfileService",
    "StudentService",
]

__version__ = "1.0.0"
# app/services/student/__init__.py
"""
Student Services Package

Comprehensive services for student management including:
- Core CRUD operations and data views
- Extended profiles and preferences
- Document management and verification
- Guardian/parent contact management
- Room transfers, swaps, and history tracking
- Onboarding and checkout workflows
- Communication and notification services

All services follow consistent patterns:
- Constructor dependency injection
- Separation of concerns
- Comprehensive error handling
- Type safety with annotations
- Performance-optimized queries
"""

from .guardian_contact_service import GuardianContactService
from .room_transfer_service import RoomTransferService
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
    "StudentCheckoutService",
    "StudentCommunicationService",
    "StudentDocumentService",
    "StudentOnboardingService",
    "StudentPreferenceService",
    "StudentProfileService",
    "StudentService",
]

__version__ = "1.0.0"
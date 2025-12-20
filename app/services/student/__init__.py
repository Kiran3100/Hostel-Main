"""
Student services package.

Exports all student-related services for convenient imports.
"""

from app.services.student.student_service import StudentService
from app.services.student.student_profile_service import StudentProfileService
from app.services.student.student_document_service import StudentDocumentService
from app.services.student.student_preference_service import StudentPreferenceService
from app.services.student.guardian_contact_service import GuardianContactService
from app.services.student.room_transfer_service import RoomTransferService
from app.services.student.student_onboarding_service import StudentOnboardingService
from app.services.student.student_checkout_service import StudentCheckoutService
from app.services.student.student_communication_service import StudentCommunicationService

__all__ = [
    "StudentService",
    "StudentProfileService",
    "StudentDocumentService",
    "StudentPreferenceService",
    "GuardianContactService",
    "RoomTransferService",
    "StudentOnboardingService",
    "StudentCheckoutService",
    "StudentCommunicationService",
]
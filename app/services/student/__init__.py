# app/services/student/__init__.py
"""
Student services package.

Provides services for:

- Core student CRUD and sub-views:
  - StudentService

- Profiles:
  - StudentProfileService

- Preferences & privacy:
  - StudentPreferenceService

- Documents:
  - StudentDocumentService

- Guardian contacts:
  - GuardianContactService

- Room transfers & history:
  - RoomTransferService

- Onboarding & checkout:
  - StudentOnboardingService
  - StudentCheckoutService

- Communications:
  - StudentCommunicationService
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
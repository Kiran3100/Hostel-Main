# --- File: __init__.py ---

"""
Student repositories package.

Exports all student-related repositories for convenient imports.
"""

from app.repositories.student.student_repository import StudentRepository
from app.repositories.student.student_profile_repository import StudentProfileRepository
from app.repositories.student.student_document_repository import StudentDocumentRepository
from app.repositories.student.student_preferences_repository import StudentPreferencesRepository
from app.repositories.student.guardian_contact_repository import GuardianContactRepository
from app.repositories.student.room_transfer_history_repository import RoomTransferHistoryRepository
from app.repositories.student.student_aggregate_repository import StudentAggregateRepository

__all__ = [
    "StudentRepository",
    "StudentProfileRepository",
    "StudentDocumentRepository",
    "StudentPreferencesRepository",
    "GuardianContactRepository",
    "RoomTransferHistoryRepository",
    "StudentAggregateRepository",
]
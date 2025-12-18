# --- File: C:\Hostel-Main\app\models\student\__init__.py ---
"""
Student models package.

Exports all student-related models for convenient imports.
"""

from app.models.student.student import Student
from app.models.student.student_profile import StudentProfile
from app.models.student.student_document import StudentDocument
from app.models.student.student_preferences import StudentPreferences
from app.models.student.guardian_contact import GuardianContact
from app.models.student.room_transfer_history import RoomTransferHistory

__all__ = [
    "Student",
    "StudentProfile",
    "StudentDocument",
    "StudentPreferences",
    "GuardianContact",
    "RoomTransferHistory",
]
# app/services/student/student_preference_service.py
"""
Student Preference Service

Manages student-specific preferences & privacy settings.
"""

from __future__ import annotations

from uuid import UUID
from typing import Optional

from sqlalchemy.orm import Session

from app.repositories.student import StudentPreferencesRepository
from app.schemas.student import (
    StudentPreferences,
    StudentPrivacySettings,
)
from app.core.exceptions import ValidationException


class StudentPreferenceService:
    """
    High-level service for student preferences and privacy.

    Responsibilities:
    - Get/set/update StudentPreferences
    - Get/set StudentPrivacySettings
    """

    def __init__(
        self,
        preferences_repo: StudentPreferencesRepository,
    ) -> None:
        self.preferences_repo = preferences_repo

    # -------------------------------------------------------------------------
    # Preferences
    # -------------------------------------------------------------------------

    def get_preferences(
        self,
        db: Session,
        student_id: UUID,
    ) -> Optional[StudentPreferences]:
        obj = self.preferences_repo.get_by_student_id(db, student_id)
        if not obj:
            return None
        return StudentPreferences.model_validate(obj)

    def set_preferences(
        self,
        db: Session,
        student_id: UUID,
        prefs: StudentPreferences,
    ) -> StudentPreferences:
        """
        Create or replace preferences.
        """
        existing = self.preferences_repo.get_by_student_id(db, student_id)
        data = prefs.model_dump(exclude_none=True)
        data["student_id"] = student_id

        if existing:
            obj = self.preferences_repo.update(db, existing, data)
        else:
            obj = self.preferences_repo.create(db, data)

        return StudentPreferences.model_validate(obj)

    # -------------------------------------------------------------------------
    # Privacy
    # -------------------------------------------------------------------------

    def get_privacy_settings(
        self,
        db: Session,
        student_id: UUID,
    ) -> Optional[StudentPrivacySettings]:
        obj = self.preferences_repo.get_privacy_settings(db, student_id)
        if not obj:
            return None
        return StudentPrivacySettings.model_validate(obj)

    def set_privacy_settings(
        self,
        db: Session,
        student_id: UUID,
        privacy: StudentPrivacySettings,
    ) -> StudentPrivacySettings:
        """
        Create or update privacy settings.
        """
        existing = self.preferences_repo.get_privacy_settings(db, student_id)
        data = privacy.model_dump(exclude_none=True)
        data["student_id"] = student_id

        if existing:
            obj = self.preferences_repo.update_privacy(db, existing, data)
        else:
            obj = self.preferences_repo.create_privacy(db, data)

        return StudentPrivacySettings.model_validate(obj)
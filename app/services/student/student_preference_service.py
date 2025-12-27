# app/services/student/student_preference_service.py
"""
Student Preference Service

Manages student-specific preferences, privacy settings, and notification preferences.
"""

from __future__ import annotations

import logging
from typing import Optional, Dict, Any
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.student import StudentPreferencesRepository
from app.schemas.student import (
    StudentPreferences,
    StudentPrivacySettings,
)
from app.core1.exceptions import (
    ValidationException,
    BusinessLogicException,
    NotFoundException,
)

logger = logging.getLogger(__name__)


class StudentPreferenceService:
    """
    High-level service for student preferences and privacy management.

    Responsibilities:
    - Get, set, and update student preferences
    - Manage privacy settings
    - Handle notification preferences
    - Provide preference defaults

    Privacy considerations:
    - Respects data minimization principles
    - Enforces privacy settings in queries
    - Logs privacy-related changes
    """

    def __init__(
        self,
        preferences_repo: StudentPreferencesRepository,
    ) -> None:
        """
        Initialize service with preferences repository.

        Args:
            preferences_repo: Repository for preference operations
        """
        self.preferences_repo = preferences_repo

    # -------------------------------------------------------------------------
    # General Preferences
    # -------------------------------------------------------------------------

    def get_preferences(
        self,
        db: Session,
        student_id: UUID,
        create_if_missing: bool = False,
    ) -> Optional[StudentPreferences]:
        """
        Retrieve student preferences.

        Args:
            db: Database session
            student_id: UUID of student
            create_if_missing: If True, create default preferences if not found

        Returns:
            StudentPreferences or None
        """
        try:
            obj = self.preferences_repo.get_by_student_id(db, student_id)
            
            if not obj and create_if_missing:
                return self._create_default_preferences(db, student_id)
            
            if not obj:
                return None
            
            return StudentPreferences.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving preferences for {student_id}: {str(e)}"
            )
            raise BusinessLogicException(
                f"Failed to retrieve preferences: {str(e)}"
            ) from e

    def set_preferences(
        self,
        db: Session,
        student_id: UUID,
        prefs: StudentPreferences,
    ) -> StudentPreferences:
        """
        Create or completely replace student preferences.

        Args:
            db: Database session
            student_id: UUID of student
            prefs: New preferences

        Returns:
            StudentPreferences: Updated preferences
        """
        try:
            existing = self.preferences_repo.get_by_student_id(db, student_id)
            
            data = prefs.model_dump(exclude_none=True)
            data["student_id"] = student_id

            if existing:
                obj = self.preferences_repo.update(db, existing, data)
                action = "updated"
            else:
                obj = self.preferences_repo.create(db, data)
                action = "created"

            logger.info(f"Preferences {action} for student: {student_id}")
            
            return StudentPreferences.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Database error setting preferences: {str(e)}")
            raise BusinessLogicException(
                f"Failed to set preferences: {str(e)}"
            ) from e

    def update_preferences(
        self,
        db: Session,
        student_id: UUID,
        updates: Dict[str, Any],
    ) -> StudentPreferences:
        """
        Partially update student preferences.

        Args:
            db: Database session
            student_id: UUID of student
            updates: Dictionary of fields to update

        Returns:
            StudentPreferences: Updated preferences

        Raises:
            NotFoundException: If preferences not found
        """
        existing = self.preferences_repo.get_by_student_id(db, student_id)
        
        if not existing:
            raise NotFoundException(
                f"Preferences not found for student: {student_id}"
            )

        try:
            obj = self.preferences_repo.update(db, existing, updates)
            
            logger.info(
                f"Preferences partially updated for student: {student_id}, "
                f"fields: {list(updates.keys())}"
            )
            
            return StudentPreferences.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Database error updating preferences: {str(e)}")
            raise BusinessLogicException(
                f"Failed to update preferences: {str(e)}"
            ) from e

    def delete_preferences(
        self,
        db: Session,
        student_id: UUID,
    ) -> None:
        """
        Delete student preferences (reset to defaults).

        Args:
            db: Database session
            student_id: UUID of student
        """
        existing = self.preferences_repo.get_by_student_id(db, student_id)
        
        if not existing:
            logger.warning(f"No preferences to delete for student: {student_id}")
            return

        try:
            self.preferences_repo.delete(db, existing)
            logger.info(f"Preferences deleted for student: {student_id}")

        except SQLAlchemyError as e:
            logger.error(f"Database error deleting preferences: {str(e)}")
            raise BusinessLogicException(
                f"Failed to delete preferences: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Privacy Settings
    # -------------------------------------------------------------------------

    def get_privacy_settings(
        self,
        db: Session,
        student_id: UUID,
        create_if_missing: bool = False,
    ) -> Optional[StudentPrivacySettings]:
        """
        Retrieve student privacy settings.

        Args:
            db: Database session
            student_id: UUID of student
            create_if_missing: If True, create default settings if not found

        Returns:
            StudentPrivacySettings or None
        """
        try:
            obj = self.preferences_repo.get_privacy_settings(db, student_id)
            
            if not obj and create_if_missing:
                return self._create_default_privacy(db, student_id)
            
            if not obj:
                return None
            
            return StudentPrivacySettings.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(
                f"Database error retrieving privacy settings for {student_id}: {str(e)}"
            )
            raise BusinessLogicException(
                f"Failed to retrieve privacy settings: {str(e)}"
            ) from e

    def set_privacy_settings(
        self,
        db: Session,
        student_id: UUID,
        privacy: StudentPrivacySettings,
    ) -> StudentPrivacySettings:
        """
        Create or replace student privacy settings.

        Args:
            db: Database session
            student_id: UUID of student
            privacy: New privacy settings

        Returns:
            StudentPrivacySettings: Updated settings
        """
        try:
            existing = self.preferences_repo.get_privacy_settings(db, student_id)
            
            data = privacy.model_dump(exclude_none=True)
            data["student_id"] = student_id

            if existing:
                obj = self.preferences_repo.update_privacy(db, existing, data)
                action = "updated"
            else:
                obj = self.preferences_repo.create_privacy(db, data)
                action = "created"

            logger.info(
                f"Privacy settings {action} for student: {student_id}",
                extra={"privacy_change": True, "student_id": str(student_id)}
            )
            
            return StudentPrivacySettings.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Database error setting privacy: {str(e)}")
            raise BusinessLogicException(
                f"Failed to set privacy settings: {str(e)}"
            ) from e

    def update_privacy_settings(
        self,
        db: Session,
        student_id: UUID,
        updates: Dict[str, Any],
    ) -> StudentPrivacySettings:
        """
        Partially update privacy settings.

        Args:
            db: Database session
            student_id: UUID of student
            updates: Dictionary of fields to update

        Returns:
            StudentPrivacySettings: Updated settings

        Raises:
            NotFoundException: If privacy settings not found
        """
        existing = self.preferences_repo.get_privacy_settings(db, student_id)
        
        if not existing:
            raise NotFoundException(
                f"Privacy settings not found for student: {student_id}"
            )

        try:
            obj = self.preferences_repo.update_privacy(db, existing, updates)
            
            logger.info(
                f"Privacy settings partially updated for student: {student_id}, "
                f"fields: {list(updates.keys())}",
                extra={"privacy_change": True, "student_id": str(student_id)}
            )
            
            return StudentPrivacySettings.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Database error updating privacy: {str(e)}")
            raise BusinessLogicException(
                f"Failed to update privacy settings: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Notification Preferences
    # -------------------------------------------------------------------------

    def update_notification_preferences(
        self,
        db: Session,
        student_id: UUID,
        email_notifications: Optional[bool] = None,
        sms_notifications: Optional[bool] = None,
        push_notifications: Optional[bool] = None,
        notification_categories: Optional[Dict[str, bool]] = None,
    ) -> StudentPreferences:
        """
        Update notification-specific preferences.

        Args:
            db: Database session
            student_id: UUID of student
            email_notifications: Enable/disable email notifications
            sms_notifications: Enable/disable SMS notifications
            push_notifications: Enable/disable push notifications
            notification_categories: Dictionary of category-specific settings

        Returns:
            StudentPreferences: Updated preferences
        """
        updates = {}
        
        if email_notifications is not None:
            updates["email_notifications_enabled"] = email_notifications
        if sms_notifications is not None:
            updates["sms_notifications_enabled"] = sms_notifications
        if push_notifications is not None:
            updates["push_notifications_enabled"] = push_notifications
        if notification_categories is not None:
            updates["notification_categories"] = notification_categories

        if not updates:
            raise ValidationException("No notification preferences provided")

        return self.update_preferences(db, student_id, updates)

    # -------------------------------------------------------------------------
    # Bulk Operations
    # -------------------------------------------------------------------------

    def bulk_update_privacy(
        self,
        db: Session,
        student_ids: list[UUID],
        privacy_updates: Dict[str, Any],
    ) -> int:
        """
        Bulk update privacy settings for multiple students.

        Args:
            db: Database session
            student_ids: List of student UUIDs
            privacy_updates: Privacy settings to apply

        Returns:
            Number of students updated
        """
        if not student_ids:
            return 0

        try:
            count = self.preferences_repo.bulk_update_privacy(
                db,
                student_ids=student_ids,
                updates=privacy_updates,
            )
            
            logger.info(
                f"Bulk privacy update: {count} students updated",
                extra={"privacy_change": True}
            )
            
            return count

        except SQLAlchemyError as e:
            logger.error(f"Database error in bulk privacy update: {str(e)}")
            raise BusinessLogicException(
                f"Failed to bulk update privacy: {str(e)}"
            ) from e

    # -------------------------------------------------------------------------
    # Default Creation Helpers
    # -------------------------------------------------------------------------

    def _create_default_preferences(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentPreferences:
        """
        Create default preferences for a student.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            StudentPreferences: Default preferences
        """
        default_data = {
            "student_id": student_id,
            "language": "en",
            "timezone": "UTC",
            "email_notifications_enabled": True,
            "sms_notifications_enabled": True,
            "push_notifications_enabled": True,
            "notification_categories": {
                "payment_reminders": True,
                "maintenance_updates": True,
                "general_announcements": True,
            },
        }

        try:
            obj = self.preferences_repo.create(db, default_data)
            logger.info(f"Default preferences created for student: {student_id}")
            return StudentPreferences.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Failed to create default preferences: {str(e)}")
            raise BusinessLogicException(
                f"Failed to create default preferences: {str(e)}"
            ) from e

    def _create_default_privacy(
        self,
        db: Session,
        student_id: UUID,
    ) -> StudentPrivacySettings:
        """
        Create default privacy settings for a student.

        Args:
            db: Database session
            student_id: UUID of student

        Returns:
            StudentPrivacySettings: Default privacy settings
        """
        default_data = {
            "student_id": student_id,
            "profile_visibility": "hostel",  # visible to hostel only
            "show_phone_number": False,
            "show_email": False,
            "show_room_info": True,
            "allow_contact_from_students": True,
            "allow_contact_from_staff": True,
        }

        try:
            obj = self.preferences_repo.create_privacy(db, default_data)
            logger.info(
                f"Default privacy settings created for student: {student_id}",
                extra={"privacy_change": True, "student_id": str(student_id)}
            )
            return StudentPrivacySettings.model_validate(obj)

        except SQLAlchemyError as e:
            logger.error(f"Failed to create default privacy: {str(e)}")
            raise BusinessLogicException(
                f"Failed to create default privacy settings: {str(e)}"
            ) from e
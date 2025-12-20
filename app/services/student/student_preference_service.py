"""
Student preference service.

Preference management with personalization, notification controls,
and compatibility matching.
"""

from typing import Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.student.student_preferences_repository import StudentPreferencesRepository
from app.repositories.student.student_repository import StudentRepository
from app.models.student.student_preferences import StudentPreferences
from app.core.exceptions import (
    ValidationError,
    NotFoundError,
    ConflictError
)


class StudentPreferenceService:
    """
    Student preference service for personalization management.
    
    Handles:
        - Notification preferences
        - Privacy settings
        - Meal preferences
        - Lifestyle preferences
        - UI/UX customization
        - Roommate compatibility
    """

    def __init__(self, db: Session):
        """Initialize service with database session."""
        self.db = db
        self.preferences_repo = StudentPreferencesRepository(db)
        self.student_repo = StudentRepository(db)

    # ============================================================================
    # PREFERENCES CRUD
    # ============================================================================

    def create_preferences(
        self,
        student_id: str,
        preferences_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentPreferences:
        """
        Create student preferences.
        
        Args:
            student_id: Student UUID
            preferences_data: Preferences information
            audit_context: Audit context
            
        Returns:
            Created preferences instance
            
        Raises:
            NotFoundError: If student not found
            ConflictError: If preferences already exist
        """
        try:
            # Validate student exists
            student = self.student_repo.find_by_id(student_id)
            if not student:
                raise NotFoundError(f"Student {student_id} not found")
            
            # Check if preferences already exist
            if self.preferences_repo.exists_for_student(student_id):
                raise ConflictError(
                    f"Preferences already exist for student {student_id}"
                )
            
            preferences_data['student_id'] = student_id
            
            preferences = self.preferences_repo.create(
                preferences_data,
                audit_context
            )
            
            self.db.commit()
            
            return preferences
            
        except (NotFoundError, ConflictError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def get_preferences_by_student_id(
        self,
        student_id: str
    ) -> StudentPreferences:
        """
        Get preferences by student ID.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Preferences instance
            
        Raises:
            NotFoundError: If preferences not found
        """
        preferences = self.preferences_repo.find_by_student_id(student_id)
        
        if not preferences:
            raise NotFoundError(
                f"Preferences not found for student {student_id}"
            )
        
        return preferences

    def update_preferences(
        self,
        student_id: str,
        update_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentPreferences:
        """
        Update student preferences.
        
        Args:
            student_id: Student UUID
            update_data: Fields to update
            audit_context: Audit context
            
        Returns:
            Updated preferences instance
            
        Raises:
            NotFoundError: If preferences not found
        """
        try:
            preferences = self.preferences_repo.update_by_student_id(
                student_id,
                update_data,
                audit_context
            )
            
            if not preferences:
                raise NotFoundError(
                    f"Preferences not found for student {student_id}"
                )
            
            self.db.commit()
            
            return preferences
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    # ============================================================================
    # NOTIFICATION PREFERENCES
    # ============================================================================

    def update_notification_channels(
        self,
        student_id: str,
        email: bool,
        sms: bool,
        push: bool,
        whatsapp: bool,
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentPreferences:
        """
        Update notification channel preferences.
        
        Args:
            student_id: Student UUID
            email: Enable email notifications
            sms: Enable SMS notifications
            push: Enable push notifications
            whatsapp: Enable WhatsApp notifications
            audit_context: Audit context
            
        Returns:
            Updated preferences instance
        """
        try:
            preferences = self.preferences_repo.update_notification_channels(
                student_id,
                email,
                sms,
                push,
                whatsapp,
                audit_context
            )
            
            if not preferences:
                raise NotFoundError(
                    f"Preferences not found for student {student_id}"
                )
            
            self.db.commit()
            
            return preferences
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def update_notification_types(
        self,
        student_id: str,
        notification_types: dict[str, bool],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentPreferences:
        """
        Update notification type preferences.
        
        Args:
            student_id: Student UUID
            notification_types: Dictionary of notification type settings
            audit_context: Audit context
            
        Returns:
            Updated preferences instance
        """
        try:
            preferences = self.preferences_repo.update_notification_types(
                student_id,
                notification_types,
                audit_context
            )
            
            if not preferences:
                raise NotFoundError(
                    f"Preferences not found for student {student_id}"
                )
            
            self.db.commit()
            
            return preferences
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def configure_quiet_hours(
        self,
        student_id: str,
        enabled: bool,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentPreferences:
        """
        Configure quiet hours for notifications.
        
        Args:
            student_id: Student UUID
            enabled: Enable quiet hours
            start_time: Start time (HH:MM format)
            end_time: End time (HH:MM format)
            audit_context: Audit context
            
        Returns:
            Updated preferences instance
            
        Raises:
            ValidationError: If time format invalid
        """
        try:
            # Validate time format if enabled
            if enabled:
                if not start_time or not end_time:
                    raise ValidationError(
                        "Start and end times required when enabling quiet hours"
                    )
                
                self._validate_time_format(start_time)
                self._validate_time_format(end_time)
            
            preferences = self.preferences_repo.set_quiet_hours(
                student_id,
                enabled,
                start_time,
                end_time,
                audit_context
            )
            
            if not preferences:
                raise NotFoundError(
                    f"Preferences not found for student {student_id}"
                )
            
            self.db.commit()
            
            return preferences
            
        except (NotFoundError, ValidationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def enable_digest_mode(
        self,
        student_id: str,
        enabled: bool,
        digest_time: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentPreferences:
        """
        Configure digest mode for notifications.
        
        Args:
            student_id: Student UUID
            enabled: Enable digest mode
            digest_time: Preferred digest time (HH:MM format)
            audit_context: Audit context
            
        Returns:
            Updated preferences instance
        """
        try:
            if enabled and digest_time:
                self._validate_time_format(digest_time)
            
            preferences = self.preferences_repo.enable_digest_mode(
                student_id,
                enabled,
                digest_time,
                audit_context
            )
            
            if not preferences:
                raise NotFoundError(
                    f"Preferences not found for student {student_id}"
                )
            
            self.db.commit()
            
            return preferences
            
        except (NotFoundError, ValidationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def _validate_time_format(self, time_str: str) -> None:
        """
        Validate time format (HH:MM).
        
        Args:
            time_str: Time string
            
        Raises:
            ValidationError: If format invalid
        """
        try:
            parts = time_str.split(':')
            if len(parts) != 2:
                raise ValueError()
            
            hour, minute = int(parts[0]), int(parts[1])
            
            if not (0 <= hour <= 23 and 0 <= minute <= 59):
                raise ValueError()
            
        except (ValueError, AttributeError):
            raise ValidationError(
                f"Invalid time format: {time_str}. Expected HH:MM (24-hour)"
            )

    # ============================================================================
    # PRIVACY SETTINGS
    # ============================================================================

    def update_privacy_settings(
        self,
        student_id: str,
        privacy_settings: dict[str, bool],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentPreferences:
        """
        Update privacy settings.
        
        Args:
            student_id: Student UUID
            privacy_settings: Dictionary of privacy settings
            audit_context: Audit context
            
        Returns:
            Updated preferences instance
        """
        try:
            preferences = self.preferences_repo.update_privacy_settings(
                student_id,
                privacy_settings,
                audit_context
            )
            
            if not preferences:
                raise NotFoundError(
                    f"Preferences not found for student {student_id}"
                )
            
            self.db.commit()
            
            return preferences
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def set_profile_visibility(
        self,
        student_id: str,
        public: bool,
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentPreferences:
        """
        Set profile visibility (public/private).
        
        Args:
            student_id: Student UUID
            public: Make profile public
            audit_context: Audit context
            
        Returns:
            Updated preferences instance
        """
        privacy_settings = {
            'show_profile_to_others': public,
            'appear_in_directory': public,
            'searchable_by_name': public
        }
        
        return self.update_privacy_settings(
            student_id,
            privacy_settings,
            audit_context
        )

    # ============================================================================
    # MEAL PREFERENCES
    # ============================================================================

    def update_meal_preferences(
        self,
        student_id: str,
        meal_plan_type: str,
        skip_breakfast: bool = False,
        skip_lunch: bool = False,
        skip_dinner: bool = False,
        notes: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentPreferences:
        """
        Update meal preferences.
        
        Args:
            student_id: Student UUID
            meal_plan_type: Meal plan type
            skip_breakfast: Skip breakfast
            skip_lunch: Skip lunch
            skip_dinner: Skip dinner
            notes: Additional notes
            audit_context: Audit context
            
        Returns:
            Updated preferences instance
        """
        try:
            # Validate meal plan type
            valid_plans = ['full', 'breakfast_only', 'lunch_dinner', 'custom']
            if meal_plan_type not in valid_plans:
                raise ValidationError(
                    f"Invalid meal plan type: {meal_plan_type}"
                )
            
            preferences = self.preferences_repo.update_meal_preferences(
                student_id,
                meal_plan_type,
                skip_breakfast,
                skip_lunch,
                skip_dinner,
                notes,
                audit_context
            )
            
            if not preferences:
                raise NotFoundError(
                    f"Preferences not found for student {student_id}"
                )
            
            self.db.commit()
            
            return preferences
            
        except (NotFoundError, ValidationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def get_meal_plan_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get distribution of meal plans.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Meal plan distribution
        """
        return self.preferences_repo.get_meal_plan_distribution(hostel_id)

    # ============================================================================
    # LIFESTYLE PREFERENCES
    # ============================================================================

    def update_lifestyle_preferences(
        self,
        student_id: str,
        preferences: dict[str, str],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentPreferences:
        """
        Update lifestyle and room preferences.
        
        Args:
            student_id: Student UUID
            preferences: Dictionary of lifestyle preferences
            audit_context: Audit context
            
        Returns:
            Updated preferences instance
        """
        try:
            prefs = self.preferences_repo.update_lifestyle_preferences(
                student_id,
                preferences,
                audit_context
            )
            
            if not prefs:
                raise NotFoundError(
                    f"Preferences not found for student {student_id}"
                )
            
            self.db.commit()
            
            return prefs
            
        except NotFoundError:
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def find_compatible_roommates(
        self,
        student_id: str,
        hostel_id: str
    ) -> list[StudentPreferences]:
        """
        Find students with compatible lifestyle preferences.
        
        Args:
            student_id: Student UUID
            hostel_id: Hostel UUID
            
        Returns:
            List of compatible student preferences
        """
        return self.preferences_repo.find_compatible_roommates(
            student_id,
            hostel_id
        )

    # ============================================================================
    # UI/UX PREFERENCES
    # ============================================================================

    def update_ui_preferences(
        self,
        student_id: str,
        theme: Optional[str] = None,
        dashboard_layout: Optional[str] = None,
        compact_view: Optional[bool] = None,
        show_tips: Optional[bool] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentPreferences:
        """
        Update UI/UX preferences.
        
        Args:
            student_id: Student UUID
            theme: Theme preference
            dashboard_layout: Dashboard layout
            compact_view: Use compact view
            show_tips: Show tips
            audit_context: Audit context
            
        Returns:
            Updated preferences instance
        """
        try:
            # Validate theme if provided
            if theme:
                valid_themes = ['light', 'dark', 'auto']
                if theme not in valid_themes:
                    raise ValidationError(f"Invalid theme: {theme}")
            
            preferences = self.preferences_repo.update_ui_preferences(
                student_id,
                theme,
                dashboard_layout,
                compact_view,
                show_tips,
                audit_context
            )
            
            if not preferences:
                raise NotFoundError(
                    f"Preferences not found for student {student_id}"
                )
            
            self.db.commit()
            
            return preferences
            
        except (NotFoundError, ValidationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def get_theme_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get distribution of theme preferences.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Theme distribution
        """
        return self.preferences_repo.get_theme_distribution(hostel_id)

    # ============================================================================
    # LANGUAGE PREFERENCES
    # ============================================================================

    def update_language_preference(
        self,
        student_id: str,
        language: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentPreferences:
        """
        Update language preference.
        
        Args:
            student_id: Student UUID
            language: Language code
            audit_context: Audit context
            
        Returns:
            Updated preferences instance
        """
        try:
            # Validate language code
            valid_languages = ['en', 'hi', 'ta', 'te', 'mr', 'bn', 'gu', 'kn', 'ml', 'pa']
            if language not in valid_languages:
                raise ValidationError(f"Invalid language code: {language}")
            
            preferences = self.preferences_repo.update_language_preference(
                student_id,
                language,
                audit_context
            )
            
            if not preferences:
                raise NotFoundError(
                    f"Preferences not found for student {student_id}"
                )
            
            self.db.commit()
            
            return preferences
            
        except (NotFoundError, ValidationError):
            self.db.rollback()
            raise
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")

    def get_language_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get distribution of language preferences.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Language distribution
        """
        return self.preferences_repo.get_language_distribution(hostel_id)

    # ============================================================================
    # STATISTICS
    # ============================================================================

    def get_notification_statistics(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, Any]:
        """
        Get notification preference statistics.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Notification statistics
        """
        return self.preferences_repo.get_notification_statistics(hostel_id)

    # ============================================================================
    # BULK OPERATIONS
    # ============================================================================

    def bulk_update_notification_channel(
        self,
        student_ids: list[str],
        channel: str,
        enabled: bool,
        audit_context: Optional[dict[str, Any]] = None
    ) -> int:
        """
        Bulk update notification channel preference.
        
        Args:
            student_ids: List of student UUIDs
            channel: Channel name
            enabled: Enable or disable
            audit_context: Audit context
            
        Returns:
            Number of preferences updated
        """
        try:
            count = self.preferences_repo.bulk_update_notification_channel(
                student_ids,
                channel,
                enabled,
                audit_context
            )
            
            self.db.commit()
            
            return count
            
        except SQLAlchemyError as e:
            self.db.rollback()
            raise ValidationError(f"Database error: {str(e)}")
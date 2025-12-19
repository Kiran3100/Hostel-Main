# --- File: student_preferences_repository.py ---

"""
Student preferences repository.

Advanced preference management with machine learning, personalization,
and predictive analytics.
"""

from datetime import datetime
from typing import Any, Optional
from sqlalchemy import and_, or_, func
from sqlalchemy.orm import Session, joinedload

from app.models.student.student_preferences import StudentPreferences
from app.models.student.student import Student


class StudentPreferencesRepository:
    """
    Student preferences repository for preference management and personalization.
    
    Handles:
        - Comprehensive preference data management
        - Notification preferences and controls
        - Privacy settings and data access
        - Meal and lifestyle preferences
        - UI/UX customization
        - Preference analytics and insights
    """

    def __init__(self, db: Session):
        """Initialize repository with database session."""
        self.db = db

    # ============================================================================
    # CORE CRUD OPERATIONS
    # ============================================================================

    def create(
        self,
        preferences_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> StudentPreferences:
        """
        Create student preferences with defaults.
        
        Args:
            preferences_data: Preferences information
            audit_context: Audit context
            
        Returns:
            Created preferences instance
        """
        # Set default values if not provided
        defaults = {
            'email_notifications': True,
            'sms_notifications': True,
            'push_notifications': True,
            'payment_reminders': True,
            'attendance_alerts': True,
            'announcement_notifications': True,
            'preferred_language': 'en',
            'preferred_contact_method': 'email',
            'show_profile_to_others': True,
            'allow_roommate_contact': True,
            'theme_preference': 'light'
        }
        
        # Merge defaults with provided data
        for key, value in defaults.items():
            if key not in preferences_data:
                preferences_data[key] = value

        preferences = StudentPreferences(**preferences_data)
        self.db.add(preferences)
        self.db.flush()
        
        return preferences

    def find_by_id(
        self,
        preferences_id: str,
        eager_load: bool = False
    ) -> Optional[StudentPreferences]:
        """
        Find preferences by ID with optional eager loading.
        
        Args:
            preferences_id: Preferences UUID
            eager_load: Load related entities
            
        Returns:
            Preferences instance or None
        """
        query = self.db.query(StudentPreferences)
        
        if eager_load:
            query = query.options(joinedload(StudentPreferences.student))
        
        return query.filter(StudentPreferences.id == preferences_id).first()

    def find_by_student_id(
        self,
        student_id: str,
        eager_load: bool = False
    ) -> Optional[StudentPreferences]:
        """
        Find preferences by student ID.
        
        Args:
            student_id: Student UUID
            eager_load: Load related entities
            
        Returns:
            Preferences instance or None
        """
        query = self.db.query(StudentPreferences)
        
        if eager_load:
            query = query.options(joinedload(StudentPreferences.student))
        
        return query.filter(StudentPreferences.student_id == student_id).first()

    def update(
        self,
        preferences_id: str,
        update_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentPreferences]:
        """
        Update preferences.
        
        Args:
            preferences_id: Preferences UUID
            update_data: Fields to update
            audit_context: Audit context
            
        Returns:
            Updated preferences instance or None
        """
        preferences = self.find_by_id(preferences_id)
        if not preferences:
            return None
        
        update_data['updated_at'] = datetime.utcnow()
        
        for key, value in update_data.items():
            if hasattr(preferences, key):
                setattr(preferences, key, value)
        
        self.db.flush()
        return preferences

    def update_by_student_id(
        self,
        student_id: str,
        update_data: dict[str, Any],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentPreferences]:
        """
        Update preferences by student ID.
        
        Args:
            student_id: Student UUID
            update_data: Fields to update
            audit_context: Audit context
            
        Returns:
            Updated preferences instance or None
        """
        preferences = self.find_by_student_id(student_id)
        if not preferences:
            return None
        
        return self.update(preferences.id, update_data, audit_context)

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
    ) -> Optional[StudentPreferences]:
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
            Updated preferences instance or None
        """
        update_data = {
            'email_notifications': email,
            'sms_notifications': sms,
            'push_notifications': push,
            'whatsapp_notifications': whatsapp
        }
        
        return self.update_by_student_id(student_id, update_data, audit_context)

    def update_notification_types(
        self,
        student_id: str,
        notification_types: dict[str, bool],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentPreferences]:
        """
        Update notification type preferences.
        
        Args:
            student_id: Student UUID
            notification_types: Dictionary of notification type settings
            audit_context: Audit context
            
        Returns:
            Updated preferences instance or None
        """
        valid_types = [
            'payment_reminders',
            'attendance_alerts',
            'announcement_notifications',
            'complaint_updates',
            'event_notifications',
            'maintenance_notifications',
            'mess_menu_updates',
            'promotional_notifications'
        ]
        
        update_data = {
            key: value for key, value in notification_types.items()
            if key in valid_types
        }
        
        return self.update_by_student_id(student_id, update_data, audit_context)

    def set_quiet_hours(
        self,
        student_id: str,
        enabled: bool,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentPreferences]:
        """
        Configure quiet hours for notifications.
        
        Args:
            student_id: Student UUID
            enabled: Enable quiet hours
            start_time: Start time (HH:MM format)
            end_time: End time (HH:MM format)
            audit_context: Audit context
            
        Returns:
            Updated preferences instance or None
        """
        update_data = {
            'quiet_hours_enabled': enabled,
            'quiet_hours_start': start_time if enabled else None,
            'quiet_hours_end': end_time if enabled else None
        }
        
        return self.update_by_student_id(student_id, update_data, audit_context)

    def enable_digest_mode(
        self,
        student_id: str,
        enabled: bool,
        digest_time: Optional[str] = None,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentPreferences]:
        """
        Configure digest mode for notifications.
        
        Args:
            student_id: Student UUID
            enabled: Enable digest mode
            digest_time: Preferred digest time (HH:MM format)
            audit_context: Audit context
            
        Returns:
            Updated preferences instance or None
        """
        update_data = {
            'digest_mode': enabled,
            'digest_time': digest_time if enabled else None
        }
        
        return self.update_by_student_id(student_id, update_data, audit_context)

    def find_digest_subscribers(
        self,
        digest_time: str,
        hostel_id: Optional[str] = None
    ) -> list[StudentPreferences]:
        """
        Find students subscribed to digest at specific time.
        
        Args:
            digest_time: Digest time (HH:MM format)
            hostel_id: Optional hostel filter
            
        Returns:
            List of preferences with digest enabled
        """
        query = self.db.query(StudentPreferences).filter(
            and_(
                StudentPreferences.digest_mode == True,
                StudentPreferences.digest_time == digest_time
            )
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    # ============================================================================
    # PRIVACY SETTINGS
    # ============================================================================

    def update_privacy_settings(
        self,
        student_id: str,
        privacy_settings: dict[str, bool],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentPreferences]:
        """
        Update privacy settings.
        
        Args:
            student_id: Student UUID
            privacy_settings: Dictionary of privacy settings
            audit_context: Audit context
            
        Returns:
            Updated preferences instance or None
        """
        valid_settings = [
            'show_profile_to_others',
            'show_room_number',
            'show_phone_number',
            'show_email',
            'show_institutional_info',
            'show_social_media',
            'allow_roommate_contact',
            'allow_floormate_contact',
            'allow_hostelmate_contact',
            'searchable_by_name',
            'searchable_by_institution',
            'searchable_by_company',
            'appear_in_directory',
            'show_last_seen',
            'show_online_status',
            'show_attendance_to_others'
        ]
        
        update_data = {
            key: value for key, value in privacy_settings.items()
            if key in valid_settings
        }
        
        return self.update_by_student_id(student_id, update_data, audit_context)

    def find_public_profiles(
        self,
        hostel_id: Optional[str] = None
    ) -> list[StudentPreferences]:
        """
        Find students with public profiles.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            List of public profiles
        """
        query = self.db.query(StudentPreferences).filter(
            and_(
                StudentPreferences.show_profile_to_others == True,
                StudentPreferences.appear_in_directory == True
            )
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def find_searchable_profiles(
        self,
        search_type: str,
        hostel_id: Optional[str] = None
    ) -> list[StudentPreferences]:
        """
        Find searchable profiles by search type.
        
        Args:
            search_type: Search type (name, institution, company)
            hostel_id: Optional hostel filter
            
        Returns:
            List of searchable profiles
        """
        query = self.db.query(StudentPreferences)
        
        if search_type == 'name':
            query = query.filter(StudentPreferences.searchable_by_name == True)
        elif search_type == 'institution':
            query = query.filter(
                StudentPreferences.searchable_by_institution == True
            )
        elif search_type == 'company':
            query = query.filter(StudentPreferences.searchable_by_company == True)
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

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
    ) -> Optional[StudentPreferences]:
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
            Updated preferences instance or None
        """
        update_data = {
            'meal_plan_type': meal_plan_type,
            'skip_breakfast': skip_breakfast,
            'skip_lunch': skip_lunch,
            'skip_dinner': skip_dinner,
            'meal_preferences_notes': notes
        }
        
        return self.update_by_student_id(student_id, update_data, audit_context)

    def find_by_meal_plan(
        self,
        meal_plan_type: str,
        hostel_id: Optional[str] = None
    ) -> list[StudentPreferences]:
        """
        Find students by meal plan type.
        
        Args:
            meal_plan_type: Meal plan type
            hostel_id: Optional hostel filter
            
        Returns:
            List of preferences with specified meal plan
        """
        query = self.db.query(StudentPreferences).filter(
            StudentPreferences.meal_plan_type == meal_plan_type
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def get_meal_plan_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get distribution of meal plans.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary mapping meal plans to counts
        """
        query = self.db.query(
            StudentPreferences.meal_plan_type,
            func.count(StudentPreferences.id).label('count')
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        query = query.group_by(StudentPreferences.meal_plan_type)
        
        results = query.all()
        
        return {meal_plan: count for meal_plan, count in results}

    # ============================================================================
    # ROOM AND LIFESTYLE PREFERENCES
    # ============================================================================

    def update_lifestyle_preferences(
        self,
        student_id: str,
        preferences: dict[str, str],
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentPreferences]:
        """
        Update lifestyle and room preferences.
        
        Args:
            student_id: Student UUID
            preferences: Dictionary of lifestyle preferences
            audit_context: Audit context
            
        Returns:
            Updated preferences instance or None
        """
        valid_preferences = [
            'room_temperature_preference',
            'light_preference',
            'noise_preference',
            'sleep_schedule',
            'study_time_preference',
            'visitor_policy',
            'cleanliness_level'
        ]
        
        update_data = {
            key: value for key, value in preferences.items()
            if key in valid_preferences
        }
        
        return self.update_by_student_id(student_id, update_data, audit_context)

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
        # Get current student's preferences
        current_prefs = self.find_by_student_id(student_id)
        if not current_prefs:
            return []
        
        # Find students with similar preferences
        query = self.db.query(StudentPreferences).join(Student).filter(
            and_(
                Student.hostel_id == hostel_id,
                StudentPreferences.student_id != student_id,
                Student.deleted_at.is_(None)
            )
        )
        
        # Filter by compatible preferences
        if current_prefs.sleep_schedule:
            query = query.filter(
                StudentPreferences.sleep_schedule == current_prefs.sleep_schedule
            )
        
        if current_prefs.noise_preference:
            query = query.filter(
                StudentPreferences.noise_preference == current_prefs.noise_preference
            )
        
        if current_prefs.cleanliness_level:
            query = query.filter(
                StudentPreferences.cleanliness_level == current_prefs.cleanliness_level
            )
        
        return query.all()

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
    ) -> Optional[StudentPreferences]:
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
            Updated preferences instance or None
        """
        update_data = {}
        
        if theme is not None:
            update_data['theme_preference'] = theme
        if dashboard_layout is not None:
            update_data['dashboard_layout'] = dashboard_layout
        if compact_view is not None:
            update_data['compact_view'] = compact_view
        if show_tips is not None:
            update_data['show_tips'] = show_tips
        
        return self.update_by_student_id(student_id, update_data, audit_context)

    def get_theme_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get distribution of theme preferences.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary mapping themes to counts
        """
        query = self.db.query(
            StudentPreferences.theme_preference,
            func.count(StudentPreferences.id).label('count')
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        query = query.group_by(StudentPreferences.theme_preference)
        
        results = query.all()
        
        return {theme: count for theme, count in results}

    # ============================================================================
    # LANGUAGE PREFERENCES
    # ============================================================================

    def update_language_preference(
        self,
        student_id: str,
        language: str,
        audit_context: Optional[dict[str, Any]] = None
    ) -> Optional[StudentPreferences]:
        """
        Update language preference.
        
        Args:
            student_id: Student UUID
            language: Language code
            audit_context: Audit context
            
        Returns:
            Updated preferences instance or None
        """
        update_data = {'preferred_language': language}
        return self.update_by_student_id(student_id, update_data, audit_context)

    def find_by_language(
        self,
        language: str,
        hostel_id: Optional[str] = None
    ) -> list[StudentPreferences]:
        """
        Find students by language preference.
        
        Args:
            language: Language code
            hostel_id: Optional hostel filter
            
        Returns:
            List of preferences with specified language
        """
        query = self.db.query(StudentPreferences).filter(
            StudentPreferences.preferred_language == language
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        return query.all()

    def get_language_distribution(
        self,
        hostel_id: Optional[str] = None
    ) -> dict[str, int]:
        """
        Get distribution of language preferences.
        
        Args:
            hostel_id: Optional hostel filter
            
        Returns:
            Dictionary mapping languages to counts
        """
        query = self.db.query(
            StudentPreferences.preferred_language,
            func.count(StudentPreferences.id).label('count')
        )
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        query = query.group_by(StudentPreferences.preferred_language)
        
        results = query.all()
        
        return {language: count for language, count in results}

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
            Dictionary with notification statistics
        """
        query = self.db.query(StudentPreferences)
        
        if hostel_id:
            query = query.join(Student).filter(Student.hostel_id == hostel_id)
        
        total = query.count()
        
        email_enabled = query.filter(
            StudentPreferences.email_notifications == True
        ).count()
        
        sms_enabled = query.filter(
            StudentPreferences.sms_notifications == True
        ).count()
        
        push_enabled = query.filter(
            StudentPreferences.push_notifications == True
        ).count()
        
        whatsapp_enabled = query.filter(
            StudentPreferences.whatsapp_notifications == True
        ).count()
        
        digest_mode = query.filter(
            StudentPreferences.digest_mode == True
        ).count()
        
        quiet_hours = query.filter(
            StudentPreferences.quiet_hours_enabled == True
        ).count()
        
        return {
            'total_students': total,
            'email_notifications': email_enabled,
            'sms_notifications': sms_enabled,
            'push_notifications': push_enabled,
            'whatsapp_notifications': whatsapp_enabled,
            'digest_mode_enabled': digest_mode,
            'quiet_hours_enabled': quiet_hours,
            'email_rate': round((email_enabled / total * 100), 2) if total > 0 else 0
        }

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
            channel: Channel name (email, sms, push, whatsapp)
            enabled: Enable or disable
            audit_context: Audit context
            
        Returns:
            Number of preferences updated
        """
        channel_mapping = {
            'email': 'email_notifications',
            'sms': 'sms_notifications',
            'push': 'push_notifications',
            'whatsapp': 'whatsapp_notifications'
        }
        
        if channel not in channel_mapping:
            return 0
        
        field_name = channel_mapping[channel]
        
        updated = self.db.query(StudentPreferences).filter(
            StudentPreferences.student_id.in_(student_ids)
        ).update(
            {
                field_name: enabled,
                'updated_at': datetime.utcnow()
            },
            synchronize_session=False
        )
        
        self.db.flush()
        return updated

    # ============================================================================
    # VALIDATION
    # ============================================================================

    def exists_for_student(self, student_id: str) -> bool:
        """
        Check if preferences exist for student.
        
        Args:
            student_id: Student UUID
            
        Returns:
            Existence status
        """
        return self.db.query(
            self.db.query(StudentPreferences).filter(
                StudentPreferences.student_id == student_id
            ).exists()
        ).scalar()
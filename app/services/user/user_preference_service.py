# --- File: C:\Hostel-Main\app\services\user\user_preference_service.py ---
"""
User Preference Service - Notification and privacy preferences management.
"""
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from datetime import time

from app.models.user import UserProfile
from app.repositories.user import UserProfileRepository
from app.core.exceptions import EntityNotFoundError, BusinessRuleViolationError


class UserPreferenceService:
    """
    Service for managing user preferences including notifications,
    privacy settings, communication preferences, and personalization.
    """

    def __init__(self, db: Session):
        self.db = db
        self.profile_repo = UserProfileRepository(db)

    # ==================== Notification Preferences ====================

    def get_notification_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get user notification preferences.
        
        Args:
            user_id: User ID
            
        Returns:
            Notification preferences dictionary
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        return profile.notification_preferences or self._get_default_notification_preferences()

    def update_notification_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any],
        validate: bool = True
    ) -> UserProfile:
        """
        Update notification preferences with validation.
        
        Args:
            user_id: User ID
            preferences: Notification preferences dictionary
            validate: Validate preference values
            
        Returns:
            Updated UserProfile
            
        Raises:
            BusinessRuleViolationError: If validation fails
        """
        if validate:
            preferences = self._validate_notification_preferences(preferences)
        
        profile = self.profile_repo.update_notification_preferences(user_id, preferences)
        
        self._log_preference_event(user_id, "notification_preferences_updated", {
            "changed_keys": list(preferences.keys())
        })
        
        return profile

    def _validate_notification_preferences(self, prefs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate notification preferences."""
        validated = {}
        
        # Boolean notification toggles
        boolean_keys = [
            'email_notifications', 'sms_notifications', 'push_notifications',
            'booking_notifications', 'payment_notifications', 'complaint_notifications',
            'announcement_notifications', 'maintenance_notifications', 'marketing_notifications'
        ]
        
        for key in boolean_keys:
            if key in prefs:
                if not isinstance(prefs[key], bool):
                    raise BusinessRuleViolationError(f"{key} must be a boolean")
                validated[key] = prefs[key]
        
        # Digest frequency validation
        if 'digest_frequency' in prefs:
            valid_frequencies = ['immediate', 'hourly', 'daily', 'weekly', 'never']
            if prefs['digest_frequency'] not in valid_frequencies:
                raise BusinessRuleViolationError(
                    f"Invalid digest_frequency. Must be one of: {', '.join(valid_frequencies)}"
                )
            validated['digest_frequency'] = prefs['digest_frequency']
        
        # Quiet hours validation
        if 'quiet_hours_start' in prefs:
            if prefs['quiet_hours_start'] is not None:
                self._validate_time_string(prefs['quiet_hours_start'])
            validated['quiet_hours_start'] = prefs['quiet_hours_start']
        
        if 'quiet_hours_end' in prefs:
            if prefs['quiet_hours_end'] is not None:
                self._validate_time_string(prefs['quiet_hours_end'])
            validated['quiet_hours_end'] = prefs['quiet_hours_end']
        
        return validated

    def _validate_time_string(self, time_str: str) -> None:
        """Validate time string in HH:MM format."""
        import re
        if not re.match(r'^([0-1]?[0-9]|2[0-3]):[0-5][0-9]$', time_str):
            raise BusinessRuleViolationError(
                f"Invalid time format: {time_str}. Use HH:MM format (e.g., 09:00, 23:30)"
            )

    def enable_notification_channel(
        self,
        user_id: str,
        channel: str  # email, sms, push
    ) -> UserProfile:
        """
        Enable a specific notification channel.
        
        Args:
            user_id: User ID
            channel: Notification channel (email, sms, push)
            
        Returns:
            Updated UserProfile
        """
        valid_channels = ['email', 'sms', 'push']
        if channel not in valid_channels:
            raise BusinessRuleViolationError(
                f"Invalid channel. Must be one of: {', '.join(valid_channels)}"
            )
        
        current_prefs = self.get_notification_preferences(user_id)
        current_prefs[f'{channel}_notifications'] = True
        
        return self.update_notification_preferences(user_id, current_prefs, validate=False)

    def disable_notification_channel(
        self,
        user_id: str,
        channel: str
    ) -> UserProfile:
        """Disable a specific notification channel."""
        valid_channels = ['email', 'sms', 'push']
        if channel not in valid_channels:
            raise BusinessRuleViolationError(
                f"Invalid channel. Must be one of: {', '.join(valid_channels)}"
            )
        
        current_prefs = self.get_notification_preferences(user_id)
        current_prefs[f'{channel}_notifications'] = False
        
        return self.update_notification_preferences(user_id, current_prefs, validate=False)

    def enable_notification_type(
        self,
        user_id: str,
        notification_type: str  # booking, payment, complaint, etc.
    ) -> UserProfile:
        """
        Enable a specific notification type.
        
        Args:
            user_id: User ID
            notification_type: Type of notification
            
        Returns:
            Updated UserProfile
        """
        valid_types = [
            'booking', 'payment', 'complaint', 'announcement', 
            'maintenance', 'marketing'
        ]
        
        if notification_type not in valid_types:
            raise BusinessRuleViolationError(
                f"Invalid notification type. Must be one of: {', '.join(valid_types)}"
            )
        
        current_prefs = self.get_notification_preferences(user_id)
        current_prefs[f'{notification_type}_notifications'] = True
        
        return self.update_notification_preferences(user_id, current_prefs, validate=False)

    def disable_notification_type(
        self,
        user_id: str,
        notification_type: str
    ) -> UserProfile:
        """Disable a specific notification type."""
        valid_types = [
            'booking', 'payment', 'complaint', 'announcement', 
            'maintenance', 'marketing'
        ]
        
        if notification_type not in valid_types:
            raise BusinessRuleViolationError(
                f"Invalid notification type. Must be one of: {', '.join(valid_types)}"
            )
        
        current_prefs = self.get_notification_preferences(user_id)
        current_prefs[f'{notification_type}_notifications'] = False
        
        return self.update_notification_preferences(user_id, current_prefs, validate=False)

    def set_digest_frequency(
        self,
        user_id: str,
        frequency: str  # immediate, hourly, daily, weekly, never
    ) -> UserProfile:
        """
        Set notification digest frequency.
        
        Args:
            user_id: User ID
            frequency: Digest frequency
            
        Returns:
            Updated UserProfile
        """
        valid_frequencies = ['immediate', 'hourly', 'daily', 'weekly', 'never']
        if frequency not in valid_frequencies:
            raise BusinessRuleViolationError(
                f"Invalid frequency. Must be one of: {', '.join(valid_frequencies)}"
            )
        
        current_prefs = self.get_notification_preferences(user_id)
        current_prefs['digest_frequency'] = frequency
        
        return self.update_notification_preferences(user_id, current_prefs, validate=False)

    def set_quiet_hours(
        self,
        user_id: str,
        start_time: str,  # HH:MM format
        end_time: str     # HH:MM format
    ) -> UserProfile:
        """
        Set quiet hours for notifications.
        
        Args:
            user_id: User ID
            start_time: Start time (HH:MM format, e.g., "22:00")
            end_time: End time (HH:MM format, e.g., "08:00")
            
        Returns:
            Updated UserProfile
        """
        self._validate_time_string(start_time)
        self._validate_time_string(end_time)
        
        current_prefs = self.get_notification_preferences(user_id)
        current_prefs['quiet_hours_start'] = start_time
        current_prefs['quiet_hours_end'] = end_time
        
        return self.update_notification_preferences(user_id, current_prefs, validate=False)

    def disable_quiet_hours(self, user_id: str) -> UserProfile:
        """Disable quiet hours."""
        current_prefs = self.get_notification_preferences(user_id)
        current_prefs['quiet_hours_start'] = None
        current_prefs['quiet_hours_end'] = None
        
        return self.update_notification_preferences(user_id, current_prefs, validate=False)

    def enable_all_notifications(self, user_id: str) -> UserProfile:
        """Enable all notification channels and types."""
        prefs = {
            'email_notifications': True,
            'sms_notifications': True,
            'push_notifications': True,
            'booking_notifications': True,
            'payment_notifications': True,
            'complaint_notifications': True,
            'announcement_notifications': True,
            'maintenance_notifications': True,
            'marketing_notifications': True
        }
        
        return self.update_notification_preferences(user_id, prefs, validate=False)

    def disable_all_notifications(self, user_id: str) -> UserProfile:
        """Disable all notification channels and types."""
        prefs = {
            'email_notifications': False,
            'sms_notifications': False,
            'push_notifications': False,
            'booking_notifications': False,
            'payment_notifications': False,
            'complaint_notifications': False,
            'announcement_notifications': False,
            'maintenance_notifications': False,
            'marketing_notifications': False
        }
        
        return self.update_notification_preferences(user_id, prefs, validate=False)

    # ==================== Privacy Settings ====================

    def get_privacy_settings(self, user_id: str) -> Dict[str, Any]:
        """
        Get user privacy settings.
        
        Args:
            user_id: User ID
            
        Returns:
            Privacy settings dictionary
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        return profile.privacy_settings or self._get_default_privacy_settings()

    def update_privacy_settings(
        self,
        user_id: str,
        settings: Dict[str, Any],
        validate: bool = True
    ) -> UserProfile:
        """
        Update privacy settings with validation.
        
        Args:
            user_id: User ID
            settings: Privacy settings dictionary
            validate: Validate setting values
            
        Returns:
            Updated UserProfile
        """
        if validate:
            settings = self._validate_privacy_settings(settings)
        
        profile = self.profile_repo.update_privacy_settings(user_id, settings)
        
        self._log_preference_event(user_id, "privacy_settings_updated", {
            "changed_keys": list(settings.keys())
        })
        
        return profile

    def _validate_privacy_settings(self, settings: Dict[str, Any]) -> Dict[str, Any]:
        """Validate privacy settings."""
        validated = {}
        
        # Profile visibility
        if 'profile_visibility' in settings:
            valid_visibility = ['public', 'friends', 'private']
            if settings['profile_visibility'] not in valid_visibility:
                raise BusinessRuleViolationError(
                    f"Invalid profile_visibility. Must be one of: {', '.join(valid_visibility)}"
                )
            validated['profile_visibility'] = settings['profile_visibility']
        
        # Boolean settings
        boolean_keys = [
            'show_email', 'show_phone', 'show_date_of_birth',
            'allow_friend_requests', 'show_online_status'
        ]
        
        for key in boolean_keys:
            if key in settings:
                if not isinstance(settings[key], bool):
                    raise BusinessRuleViolationError(f"{key} must be a boolean")
                validated[key] = settings[key]
        
        return validated

    def set_profile_visibility(
        self,
        user_id: str,
        visibility: str  # public, friends, private
    ) -> UserProfile:
        """
        Set profile visibility level.
        
        Args:
            user_id: User ID
            visibility: Visibility level
            
        Returns:
            Updated UserProfile
        """
        valid_visibility = ['public', 'friends', 'private']
        if visibility not in valid_visibility:
            raise BusinessRuleViolationError(
                f"Invalid visibility. Must be one of: {', '.join(valid_visibility)}"
            )
        
        current_settings = self.get_privacy_settings(user_id)
        current_settings['profile_visibility'] = visibility
        
        return self.update_privacy_settings(user_id, current_settings, validate=False)

    def toggle_field_visibility(
        self,
        user_id: str,
        field: str,  # email, phone, date_of_birth
        visible: bool
    ) -> UserProfile:
        """
        Toggle visibility of a profile field.
        
        Args:
            user_id: User ID
            field: Field name
            visible: Visibility flag
            
        Returns:
            Updated UserProfile
        """
        valid_fields = ['email', 'phone', 'date_of_birth']
        if field not in valid_fields:
            raise BusinessRuleViolationError(
                f"Invalid field. Must be one of: {', '.join(valid_fields)}"
            )
        
        current_settings = self.get_privacy_settings(user_id)
        current_settings[f'show_{field}'] = visible
        
        return self.update_privacy_settings(user_id, current_settings, validate=False)

    def set_online_status_visibility(
        self,
        user_id: str,
        visible: bool
    ) -> UserProfile:
        """Set online status visibility."""
        current_settings = self.get_privacy_settings(user_id)
        current_settings['show_online_status'] = visible
        
        return self.update_privacy_settings(user_id, current_settings, validate=False)

    def allow_friend_requests(
        self,
        user_id: str,
        allow: bool
    ) -> UserProfile:
        """Allow or disallow friend requests."""
        current_settings = self.get_privacy_settings(user_id)
        current_settings['allow_friend_requests'] = allow
        
        return self.update_privacy_settings(user_id, current_settings, validate=False)

    # ==================== Communication Preferences ====================

    def get_communication_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get communication preferences."""
        profile = self.profile_repo.get_by_user_id(user_id)
        return profile.communication_preferences or self._get_default_communication_preferences()

    def update_communication_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any],
        validate: bool = True
    ) -> UserProfile:
        """
        Update communication preferences.
        
        Args:
            user_id: User ID
            preferences: Communication preferences dictionary
            validate: Validate preference values
            
        Returns:
            Updated UserProfile
        """
        if validate:
            preferences = self._validate_communication_preferences(preferences)
        
        profile = self.profile_repo.update_communication_preferences(user_id, preferences)
        
        self._log_preference_event(user_id, "communication_preferences_updated", {
            "changed_keys": list(preferences.keys())
        })
        
        return profile

    def _validate_communication_preferences(self, prefs: Dict[str, Any]) -> Dict[str, Any]:
        """Validate communication preferences."""
        validated = {}
        
        if 'preferred_contact_method' in prefs:
            valid_methods = ['email', 'phone', 'sms', 'app']
            if prefs['preferred_contact_method'] not in valid_methods:
                raise BusinessRuleViolationError(
                    f"Invalid preferred_contact_method. Must be one of: {', '.join(valid_methods)}"
                )
            validated['preferred_contact_method'] = prefs['preferred_contact_method']
        
        if 'best_contact_time' in prefs:
            valid_times = ['morning', 'afternoon', 'evening', 'anytime']
            if prefs['best_contact_time'] not in valid_times:
                raise BusinessRuleViolationError(
                    f"Invalid best_contact_time. Must be one of: {', '.join(valid_times)}"
                )
            validated['best_contact_time'] = prefs['best_contact_time']
        
        if 'do_not_disturb' in prefs:
            if not isinstance(prefs['do_not_disturb'], bool):
                raise BusinessRuleViolationError("do_not_disturb must be a boolean")
            validated['do_not_disturb'] = prefs['do_not_disturb']
        
        return validated

    def set_preferred_contact_method(
        self,
        user_id: str,
        method: str  # email, phone, sms, app
    ) -> UserProfile:
        """Set preferred contact method."""
        valid_methods = ['email', 'phone', 'sms', 'app']
        if method not in valid_methods:
            raise BusinessRuleViolationError(
                f"Invalid method. Must be one of: {', '.join(valid_methods)}"
            )
        
        current_prefs = self.get_communication_preferences(user_id)
        current_prefs['preferred_contact_method'] = method
        
        return self.update_communication_preferences(user_id, current_prefs, validate=False)

    def set_best_contact_time(
        self,
        user_id: str,
        time_preference: str  # morning, afternoon, evening, anytime
    ) -> UserProfile:
        """Set best time to contact."""
        valid_times = ['morning', 'afternoon', 'evening', 'anytime']
        if time_preference not in valid_times:
            raise BusinessRuleViolationError(
                f"Invalid time. Must be one of: {', '.join(valid_times)}"
            )
        
        current_prefs = self.get_communication_preferences(user_id)
        current_prefs['best_contact_time'] = time_preference
        
        return self.update_communication_preferences(user_id, current_prefs, validate=False)

    def enable_do_not_disturb(self, user_id: str) -> UserProfile:
        """Enable do not disturb mode."""
        current_prefs = self.get_communication_preferences(user_id)
        current_prefs['do_not_disturb'] = True
        
        return self.update_communication_preferences(user_id, current_prefs, validate=False)

    def disable_do_not_disturb(self, user_id: str) -> UserProfile:
        """Disable do not disturb mode."""
        current_prefs = self.get_communication_preferences(user_id)
        current_prefs['do_not_disturb'] = False
        
        return self.update_communication_preferences(user_id, current_prefs, validate=False)

    # ==================== Preference Presets ====================

    def apply_privacy_preset(
        self,
        user_id: str,
        preset: str  # open, moderate, private
    ) -> UserProfile:
        """
        Apply a privacy preset configuration.
        
        Args:
            user_id: User ID
            preset: Preset name (open, moderate, private)
            
        Returns:
            Updated UserProfile
        """
        presets = {
            'open': {
                'profile_visibility': 'public',
                'show_email': True,
                'show_phone': True,
                'show_date_of_birth': True,
                'allow_friend_requests': True,
                'show_online_status': True
            },
            'moderate': {
                'profile_visibility': 'friends',
                'show_email': False,
                'show_phone': False,
                'show_date_of_birth': False,
                'allow_friend_requests': True,
                'show_online_status': True
            },
            'private': {
                'profile_visibility': 'private',
                'show_email': False,
                'show_phone': False,
                'show_date_of_birth': False,
                'allow_friend_requests': False,
                'show_online_status': False
            }
        }
        
        if preset not in presets:
            raise BusinessRuleViolationError(
                f"Invalid preset. Must be one of: {', '.join(presets.keys())}"
            )
        
        profile = self.update_privacy_settings(user_id, presets[preset], validate=False)
        
        self._log_preference_event(user_id, "privacy_preset_applied", {
            "preset": preset
        })
        
        return profile

    def apply_notification_preset(
        self,
        user_id: str,
        preset: str  # all, essential, minimal, none
    ) -> UserProfile:
        """
        Apply a notification preset configuration.
        
        Args:
            user_id: User ID
            preset: Preset name
            
        Returns:
            Updated UserProfile
        """
        presets = {
            'all': {
                'email_notifications': True,
                'sms_notifications': True,
                'push_notifications': True,
                'booking_notifications': True,
                'payment_notifications': True,
                'complaint_notifications': True,
                'announcement_notifications': True,
                'maintenance_notifications': True,
                'marketing_notifications': True,
                'digest_frequency': 'immediate'
            },
            'essential': {
                'email_notifications': True,
                'sms_notifications': False,
                'push_notifications': True,
                'booking_notifications': True,
                'payment_notifications': True,
                'complaint_notifications': True,
                'announcement_notifications': False,
                'maintenance_notifications': True,
                'marketing_notifications': False,
                'digest_frequency': 'daily'
            },
            'minimal': {
                'email_notifications': True,
                'sms_notifications': False,
                'push_notifications': False,
                'booking_notifications': True,
                'payment_notifications': True,
                'complaint_notifications': False,
                'announcement_notifications': False,
                'maintenance_notifications': False,
                'marketing_notifications': False,
                'digest_frequency': 'weekly'
            },
            'none': {
                'email_notifications': False,
                'sms_notifications': False,
                'push_notifications': False,
                'booking_notifications': False,
                'payment_notifications': False,
                'complaint_notifications': False,
                'announcement_notifications': False,
                'maintenance_notifications': False,
                'marketing_notifications': False,
                'digest_frequency': 'never'
            }
        }
        
        if preset not in presets:
            raise BusinessRuleViolationError(
                f"Invalid preset. Must be one of: {', '.join(presets.keys())}"
            )
        
        profile = self.update_notification_preferences(user_id, presets[preset], validate=False)
        
        self._log_preference_event(user_id, "notification_preset_applied", {
            "preset": preset
        })
        
        return profile

    # ==================== Preference Export/Import ====================

    def export_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Export all user preferences.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with all preferences
        """
        return {
            'notification_preferences': self.get_notification_preferences(user_id),
            'privacy_settings': self.get_privacy_settings(user_id),
            'communication_preferences': self.get_communication_preferences(user_id)
        }

    def import_preferences(
        self,
        user_id: str,
        preferences: Dict[str, Any],
        validate: bool = True
    ) -> UserProfile:
        """
        Import user preferences in bulk.
        
        Args:
            user_id: User ID
            preferences: Complete preferences dictionary
            validate: Validate imported preferences
            
        Returns:
            Updated UserProfile
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        
        update_data = {}
        
        if 'notification_preferences' in preferences:
            if validate:
                preferences['notification_preferences'] = self._validate_notification_preferences(
                    preferences['notification_preferences']
                )
            update_data['notification_preferences'] = preferences['notification_preferences']
        
        if 'privacy_settings' in preferences:
            if validate:
                preferences['privacy_settings'] = self._validate_privacy_settings(
                    preferences['privacy_settings']
                )
            update_data['privacy_settings'] = preferences['privacy_settings']
        
        if 'communication_preferences' in preferences:
            if validate:
                preferences['communication_preferences'] = self._validate_communication_preferences(
                    preferences['communication_preferences']
                )
            update_data['communication_preferences'] = preferences['communication_preferences']
        
        if update_data:
            profile = self.profile_repo.update(profile.id, update_data)
            
            self._log_preference_event(user_id, "preferences_imported", {
                "categories": list(update_data.keys())
            })
        
        return profile

    def reset_to_defaults(self, user_id: str) -> UserProfile:
        """
        Reset all preferences to default values.
        
        Args:
            user_id: User ID
            
        Returns:
            Updated UserProfile
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        
        update_data = {
            'notification_preferences': self._get_default_notification_preferences(),
            'privacy_settings': self._get_default_privacy_settings(),
            'communication_preferences': self._get_default_communication_preferences()
        }
        
        profile = self.profile_repo.update(profile.id, update_data)
        
        self._log_preference_event(user_id, "preferences_reset_to_defaults", {})
        
        return profile

    # ==================== Helper Methods ====================

    def _get_default_notification_preferences(self) -> Dict[str, Any]:
        """Get default notification preferences."""
        return {
            "email_notifications": True,
            "sms_notifications": True,
            "push_notifications": True,
            "booking_notifications": True,
            "payment_notifications": True,
            "complaint_notifications": True,
            "announcement_notifications": True,
            "maintenance_notifications": True,
            "marketing_notifications": False,
            "digest_frequency": "immediate",
            "quiet_hours_start": None,
            "quiet_hours_end": None
        }

    def _get_default_privacy_settings(self) -> Dict[str, Any]:
        """Get default privacy settings."""
        return {
            "profile_visibility": "public",
            "show_email": False,
            "show_phone": False,
            "show_date_of_birth": False,
            "allow_friend_requests": True,
            "show_online_status": True
        }

    def _get_default_communication_preferences(self) -> Dict[str, Any]:
        """Get default communication preferences."""
        return {
            "preferred_contact_method": "email",
            "best_contact_time": "anytime",
            "do_not_disturb": False
        }

    def _log_preference_event(
        self,
        user_id: str,
        event_type: str,
        event_data: Dict[str, Any]
    ) -> None:
        """Log preference event for auditing."""
        # TODO: Implement event logging
        pass

    # ==================== Preference Validation ====================

    def validate_all_preferences(self, user_id: str) -> Dict[str, List[str]]:
        """
        Validate all user preferences and return any errors.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary of validation errors by category
        """
        errors = {
            'notification_preferences': [],
            'privacy_settings': [],
            'communication_preferences': []
        }
        
        # Validate notification preferences
        try:
            notif_prefs = self.get_notification_preferences(user_id)
            self._validate_notification_preferences(notif_prefs)
        except BusinessRuleViolationError as e:
            errors['notification_preferences'].append(str(e))
        
        # Validate privacy settings
        try:
            privacy_settings = self.get_privacy_settings(user_id)
            self._validate_privacy_settings(privacy_settings)
        except BusinessRuleViolationError as e:
            errors['privacy_settings'].append(str(e))
        
        # Validate communication preferences
        try:
            comm_prefs = self.get_communication_preferences(user_id)
            self._validate_communication_preferences(comm_prefs)
        except BusinessRuleViolationError as e:
            errors['communication_preferences'].append(str(e))
        
        return {k: v for k, v in errors.items() if v}  # Return only categories with errors



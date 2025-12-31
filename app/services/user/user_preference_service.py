"""
User Preference Service

Manages user-level preferences (notification settings, quiet hours, etc.).
Enhanced with validation, default preferences, and preference categories.
"""

import logging
from typing import Union, Dict, Any
from uuid import UUID
from datetime import time

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.notification import NotificationPreferencesRepository
from app.schemas.user import NotificationPreferencesUpdate
from app.models.notification.notification_preferences import NotificationPreference
from app.core.exceptions import ValidationError, BusinessLogicError, NotFoundError

logger = logging.getLogger(__name__)


class UserPreferenceService:
    """
    High-level service for user preferences.

    Currently focuses on notification preferences stored in notification.NotificationPreference.
    Can be extended to handle other preference types.

    Responsibilities:
    - Get/update notification preferences
    - Validate preference data
    - Apply default preferences
    - Handle quiet hours logic
    """

    # Default notification preferences
    DEFAULT_PREFERENCES = {
        "email_notifications": True,
        "sms_notifications": False,
        "push_notifications": True,
        "in_app_notifications": True,
        "digest_frequency": "daily",
        "quiet_hours_enabled": False,
        "quiet_hours_start": None,
        "quiet_hours_end": None,
    }

    def __init__(
        self,
        notification_pref_repo: NotificationPreferencesRepository,
    ) -> None:
        self.notification_pref_repo = notification_pref_repo

    # -------------------------------------------------------------------------
    # Notification Preferences
    # -------------------------------------------------------------------------

    def get_notification_preferences(
        self,
        db: Session,
        user_id: UUID,
        create_if_missing: bool = False,
    ) -> Union[NotificationPreference, None]:
        """
        Get user notification preferences.

        Args:
            db: Database session
            user_id: User identifier
            create_if_missing: If True, creates default preferences if none exist

        Returns:
            NotificationPreference instance or None
        """
        try:
            preferences = self.notification_pref_repo.get_by_user_id(db, user_id)

            if not preferences and create_if_missing:
                preferences = self._create_default_preferences(db, user_id)

            return preferences

        except SQLAlchemyError as e:
            logger.error(
                f"Database error getting notification preferences for user {user_id}: {str(e)}"
            )
            raise BusinessLogicError("Failed to retrieve notification preferences")

    def update_notification_preferences(
        self,
        db: Session,
        user_id: UUID,
        update: NotificationPreferencesUpdate,
    ) -> NotificationPreference:
        """
        Create or update notification preferences for a user.

        Args:
            db: Database session
            user_id: User identifier
            update: Preference updates

        Returns:
            Updated NotificationPreference instance

        Raises:
            ValidationError: If validation fails
        """
        # Validate the update data
        self._validate_preferences(update)

        try:
            existing = self.notification_pref_repo.get_by_user_id(db, user_id)
            data = update.model_dump(exclude_none=True)
            data["user_id"] = user_id

            if existing:
                # Update existing preferences
                pref = self.notification_pref_repo.update(db, existing, data)
                logger.info(f"Updated notification preferences for user {user_id}")
            else:
                # Create new preferences (merge with defaults)
                merged_data = {**self.DEFAULT_PREFERENCES, **data}
                pref = self.notification_pref_repo.create(db, merged_data)
                logger.info(f"Created notification preferences for user {user_id}")

            return pref

        except SQLAlchemyError as e:
            logger.error(
                f"Database error updating notification preferences for user {user_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicError("Failed to update notification preferences")

    def reset_to_defaults(
        self,
        db: Session,
        user_id: UUID,
    ) -> NotificationPreference:
        """
        Reset notification preferences to default values.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            Updated NotificationPreference instance
        """
        try:
            existing = self.notification_pref_repo.get_by_user_id(db, user_id)

            data = {**self.DEFAULT_PREFERENCES, "user_id": user_id}

            if existing:
                pref = self.notification_pref_repo.update(db, existing, data)
            else:
                pref = self.notification_pref_repo.create(db, data)

            logger.info(f"Reset notification preferences to defaults for user {user_id}")

            return pref

        except SQLAlchemyError as e:
            logger.error(
                f"Database error resetting preferences for user {user_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicError("Failed to reset notification preferences")

    # -------------------------------------------------------------------------
    # Quiet Hours Management
    # -------------------------------------------------------------------------

    def set_quiet_hours(
        self,
        db: Session,
        user_id: UUID,
        start_time: time,
        end_time: time,
        enabled: bool = True,
    ) -> NotificationPreference:
        """
        Set quiet hours for a user.

        Args:
            db: Database session
            user_id: User identifier
            start_time: Start time for quiet hours
            end_time: End time for quiet hours
            enabled: Whether quiet hours are enabled

        Returns:
            Updated NotificationPreference instance

        Raises:
            ValidationError: If validation fails
        """
        # Validate quiet hours
        if start_time == end_time:
            raise ValidationError("Quiet hours start and end times cannot be the same")

        try:
            existing = self.notification_pref_repo.get_by_user_id(db, user_id)

            data = {
                "user_id": user_id,
                "quiet_hours_enabled": enabled,
                "quiet_hours_start": start_time,
                "quiet_hours_end": end_time,
            }

            if existing:
                pref = self.notification_pref_repo.update(db, existing, data)
            else:
                merged_data = {**self.DEFAULT_PREFERENCES, **data}
                pref = self.notification_pref_repo.create(db, merged_data)

            logger.info(
                f"Set quiet hours for user {user_id}: "
                f"{start_time.strftime('%H:%M')} - {end_time.strftime('%H:%M')} "
                f"(enabled={enabled})"
            )

            return pref

        except SQLAlchemyError as e:
            logger.error(f"Database error setting quiet hours for user {user_id}: {str(e)}")
            db.rollback()
            raise BusinessLogicError("Failed to set quiet hours")

    def disable_quiet_hours(
        self,
        db: Session,
        user_id: UUID,
    ) -> NotificationPreference:
        """
        Disable quiet hours for a user.

        Args:
            db: Database session
            user_id: User identifier

        Returns:
            Updated NotificationPreference instance
        """
        try:
            existing = self.notification_pref_repo.get_by_user_id(db, user_id)

            if not existing:
                raise NotFoundError("No notification preferences found for user")

            pref = self.notification_pref_repo.update(
                db,
                existing,
                {"quiet_hours_enabled": False},
            )

            logger.info(f"Disabled quiet hours for user {user_id}")

            return pref

        except SQLAlchemyError as e:
            logger.error(
                f"Database error disabling quiet hours for user {user_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicError("Failed to disable quiet hours")

    def is_in_quiet_hours(
        self,
        db: Session,
        user_id: UUID,
        check_time: Union[time, None] = None,
    ) -> bool:
        """
        Check if current time (or specified time) is within user's quiet hours.

        Args:
            db: Database session
            user_id: User identifier
            check_time: Optional time to check (defaults to current time)

        Returns:
            True if in quiet hours, False otherwise
        """
        from datetime import datetime

        preferences = self.get_notification_preferences(db, user_id)

        if not preferences or not preferences.quiet_hours_enabled:
            return False

        if not preferences.quiet_hours_start or not preferences.quiet_hours_end:
            return False

        if check_time is None:
            check_time = datetime.now().time()

        start = preferences.quiet_hours_start
        end = preferences.quiet_hours_end

        # Handle overnight quiet hours (e.g., 22:00 - 06:00)
        if start <= end:
            return start <= check_time <= end
        else:
            return check_time >= start or check_time <= end

    # -------------------------------------------------------------------------
    # Channel-Specific Preferences
    # -------------------------------------------------------------------------

    def enable_channel(
        self,
        db: Session,
        user_id: UUID,
        channel: str,
    ) -> NotificationPreference:
        """
        Enable a specific notification channel.

        Args:
            db: Database session
            user_id: User identifier
            channel: Channel name ('email', 'sms', 'push', 'in_app')

        Returns:
            Updated NotificationPreference instance

        Raises:
            ValidationError: If channel is invalid
        """
        valid_channels = ["email", "sms", "push", "in_app"]
        if channel not in valid_channels:
            raise ValidationError(f"Invalid channel. Must be one of: {valid_channels}")

        field_name = f"{channel}_notifications"
        
        try:
            existing = self.notification_pref_repo.get_by_user_id(db, user_id)
            
            data = {"user_id": user_id, field_name: True}

            if existing:
                pref = self.notification_pref_repo.update(db, existing, data)
            else:
                merged_data = {**self.DEFAULT_PREFERENCES, **data}
                pref = self.notification_pref_repo.create(db, merged_data)

            logger.info(f"Enabled {channel} notifications for user {user_id}")

            return pref

        except SQLAlchemyError as e:
            logger.error(
                f"Database error enabling {channel} for user {user_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicError(f"Failed to enable {channel} notifications")

    def disable_channel(
        self,
        db: Session,
        user_id: UUID,
        channel: str,
    ) -> NotificationPreference:
        """
        Disable a specific notification channel.

        Args:
            db: Database session
            user_id: User identifier
            channel: Channel name ('email', 'sms', 'push', 'in_app')

        Returns:
            Updated NotificationPreference instance

        Raises:
            ValidationError: If channel is invalid
        """
        valid_channels = ["email", "sms", "push", "in_app"]
        if channel not in valid_channels:
            raise ValidationError(f"Invalid channel. Must be one of: {valid_channels}")

        field_name = f"{channel}_notifications"

        try:
            existing = self.notification_pref_repo.get_by_user_id(db, user_id)

            if not existing:
                raise NotFoundError("No notification preferences found for user")

            pref = self.notification_pref_repo.update(
                db,
                existing,
                {field_name: False},
            )

            logger.info(f"Disabled {channel} notifications for user {user_id}")

            return pref

        except SQLAlchemyError as e:
            logger.error(
                f"Database error disabling {channel} for user {user_id}: {str(e)}"
            )
            db.rollback()
            raise BusinessLogicError(f"Failed to disable {channel} notifications")

    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------

    def _create_default_preferences(
        self,
        db: Session,
        user_id: UUID,
    ) -> NotificationPreference:
        """Create default notification preferences for a user."""
        data = {**self.DEFAULT_PREFERENCES, "user_id": user_id}
        
        pref = self.notification_pref_repo.create(db, data)
        logger.info(f"Created default notification preferences for user {user_id}")
        
        return pref

    def _validate_preferences(self, update: NotificationPreferencesUpdate) -> None:
        """Validate notification preference update data."""
        data = update.model_dump(exclude_none=True)

        # Validate digest frequency if provided
        if "digest_frequency" in data:
            valid_frequencies = ["realtime", "hourly", "daily", "weekly", "never"]
            if data["digest_frequency"] not in valid_frequencies:
                raise ValidationError(
                    f"Invalid digest frequency. Must be one of: {valid_frequencies}"
                )

        # Validate quiet hours if provided
        if "quiet_hours_enabled" in data and data["quiet_hours_enabled"]:
            if "quiet_hours_start" not in data or "quiet_hours_end" not in data:
                raise ValidationError(
                    "Both quiet_hours_start and quiet_hours_end must be provided "
                    "when enabling quiet hours"
                )

        # Validate that at least one notification channel is enabled
        channels = ["email_notifications", "sms_notifications", "push_notifications", "in_app_notifications"]
        channel_values = [data.get(ch) for ch in channels if ch in data]
        
        if channel_values and not any(channel_values):
            raise ValidationError("At least one notification channel must be enabled")
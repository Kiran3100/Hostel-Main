# --- File: C:\Hostel-Main\app\services\notification\notification_preference_service.py ---
"""
Notification Preference Service - Manages user notification preferences.

Handles user settings, channel preferences, quiet hours, digest settings,
and unsubscribe management.
"""

from datetime import datetime, time, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
import secrets

from sqlalchemy.orm import Session

from app.models.notification.notification_preferences import (
    NotificationPreference,
    ChannelPreference,
    UnsubscribeToken
)
from app.repositories.notification.notification_preferences_repository import (
    NotificationPreferencesRepository
)
from app.core.exceptions import PreferenceError

logger = logging.getLogger(__name__)


class NotificationPreferenceService:
    """
    Service for user notification preference management.
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.preference_repo = NotificationPreferencesRepository(db_session)

    def get_user_preferences(
        self,
        user_id: UUID
    ) -> NotificationPreference:
        """
        Get or create user notification preferences.
        
        Args:
            user_id: User ID
            
        Returns:
            NotificationPreference
        """
        try:
            return self.preference_repo.get_or_create_preferences(user_id)
        except Exception as e:
            logger.error(f"Error getting preferences: {str(e)}", exc_info=True)
            raise PreferenceError(f"Failed to get preferences: {str(e)}")

    def update_global_settings(
        self,
        user_id: UUID,
        notifications_enabled: Optional[bool] = None,
        email_enabled: Optional[bool] = None,
        sms_enabled: Optional[bool] = None,
        push_enabled: Optional[bool] = None,
        in_app_enabled: Optional[bool] = None,
        preferred_language: Optional[str] = None,
        timezone: Optional[str] = None
    ) -> NotificationPreference:
        """
        Update global notification settings.
        
        Args:
            user_id: User ID
            notifications_enabled: Master toggle
            email_enabled: Email channel toggle
            sms_enabled: SMS channel toggle
            push_enabled: Push channel toggle
            in_app_enabled: In-app channel toggle
            preferred_language: Language code
            timezone: Timezone string
            
        Returns:
            Updated preferences
        """
        try:
            settings = {}
            
            if notifications_enabled is not None:
                settings['notifications_enabled'] = notifications_enabled
            if email_enabled is not None:
                settings['email_enabled'] = email_enabled
            if sms_enabled is not None:
                settings['sms_enabled'] = sms_enabled
            if push_enabled is not None:
                settings['push_enabled'] = push_enabled
            if in_app_enabled is not None:
                settings['in_app_enabled'] = in_app_enabled
            if preferred_language is not None:
                settings['preferred_language'] = preferred_language
            if timezone is not None:
                settings['timezone'] = timezone
            
            self.preference_repo.update_global_settings(user_id, settings)
            
            return self.preference_repo.get_or_create_preferences(user_id)
            
        except Exception as e:
            logger.error(f"Error updating global settings: {str(e)}", exc_info=True)
            raise PreferenceError(f"Failed to update settings: {str(e)}")

    def update_category_preferences(
        self,
        user_id: UUID,
        payment_notifications: Optional[bool] = None,
        booking_notifications: Optional[bool] = None,
        complaint_notifications: Optional[bool] = None,
        announcement_notifications: Optional[bool] = None,
        maintenance_notifications: Optional[bool] = None,
        attendance_notifications: Optional[bool] = None,
        marketing_notifications: Optional[bool] = None
    ) -> NotificationPreference:
        """
        Update category-specific notification preferences.
        
        Args:
            user_id: User ID
            payment_notifications: Payment category toggle
            booking_notifications: Booking category toggle
            complaint_notifications: Complaint category toggle
            announcement_notifications: Announcement category toggle
            maintenance_notifications: Maintenance category toggle
            attendance_notifications: Attendance category toggle
            marketing_notifications: Marketing category toggle
            
        Returns:
            Updated preferences
        """
        try:
            settings = {}
            
            if payment_notifications is not None:
                settings['payment_notifications'] = payment_notifications
            if booking_notifications is not None:
                settings['booking_notifications'] = booking_notifications
            if complaint_notifications is not None:
                settings['complaint_notifications'] = complaint_notifications
            if announcement_notifications is not None:
                settings['announcement_notifications'] = announcement_notifications
            if maintenance_notifications is not None:
                settings['maintenance_notifications'] = maintenance_notifications
            if attendance_notifications is not None:
                settings['attendance_notifications'] = attendance_notifications
            if marketing_notifications is not None:
                settings['marketing_notifications'] = marketing_notifications
            
            self.preference_repo.update_global_settings(user_id, settings)
            
            return self.preference_repo.get_or_create_preferences(user_id)
            
        except Exception as e:
            logger.error(f"Error updating category preferences: {str(e)}", exc_info=True)
            raise PreferenceError(f"Failed to update category preferences: {str(e)}")

    def configure_quiet_hours(
        self,
        user_id: UUID,
        enabled: bool,
        start_time: Optional[time] = None,
        end_time: Optional[time] = None,
        apply_weekdays: bool = True,
        apply_weekends: bool = True,
        allow_urgent: bool = True
    ) -> NotificationPreference:
        """
        Configure quiet hours settings.
        
        Args:
            user_id: User ID
            enabled: Enable quiet hours
            start_time: Quiet hours start time
            end_time: Quiet hours end time
            apply_weekdays: Apply on weekdays
            apply_weekends: Apply on weekends
            allow_urgent: Allow urgent notifications
            
        Returns:
            Updated preferences
        """
        try:
            quiet_hours_config = {
                'quiet_hours_enabled': enabled,
                'quiet_hours_start': start_time,
                'quiet_hours_end': end_time,
                'quiet_hours_weekdays': apply_weekdays,
                'quiet_hours_weekends': apply_weekends,
                'quiet_hours_allow_urgent': allow_urgent
            }
            
            self.preference_repo.update_quiet_hours(user_id, quiet_hours_config)
            
            logger.info(f"Quiet hours configured for user {user_id}")
            
            return self.preference_repo.get_or_create_preferences(user_id)
            
        except Exception as e:
            logger.error(f"Error configuring quiet hours: {str(e)}", exc_info=True)
            raise PreferenceError(f"Failed to configure quiet hours: {str(e)}")

    def configure_digest_settings(
        self,
        user_id: UUID,
        daily_digest_enabled: Optional[bool] = None,
        daily_digest_time: Optional[time] = None,
        weekly_digest_enabled: Optional[bool] = None,
        weekly_digest_day: Optional[str] = None,
        weekly_digest_time: Optional[time] = None
    ) -> NotificationPreference:
        """
        Configure digest notification settings.
        
        Args:
            user_id: User ID
            daily_digest_enabled: Enable daily digest
            daily_digest_time: Time for daily digest
            weekly_digest_enabled: Enable weekly digest
            weekly_digest_day: Day for weekly digest
            weekly_digest_time: Time for weekly digest
            
        Returns:
            Updated preferences
        """
        try:
            digest_config = {}
            
            if daily_digest_enabled is not None:
                digest_config['daily_digest_enabled'] = daily_digest_enabled
            if daily_digest_time is not None:
                digest_config['daily_digest_time'] = daily_digest_time
            if weekly_digest_enabled is not None:
                digest_config['weekly_digest_enabled'] = weekly_digest_enabled
            if weekly_digest_day is not None:
                digest_config['weekly_digest_day'] = weekly_digest_day.lower()
            if weekly_digest_time is not None:
                digest_config['weekly_digest_time'] = weekly_digest_time
            
            self.preference_repo.update_digest_settings(user_id, digest_config)
            
            logger.info(f"Digest settings configured for user {user_id}")
            
            return self.preference_repo.get_or_create_preferences(user_id)
            
        except Exception as e:
            logger.error(f"Error configuring digest: {str(e)}", exc_info=True)
            raise PreferenceError(f"Failed to configure digest: {str(e)}")

    def update_channel_preferences(
        self,
        user_id: UUID,
        channel: str,
        settings: Dict[str, Any],
        category_preferences: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Update channel-specific preferences.
        
        Args:
            user_id: User ID
            channel: Channel name (email, sms, push, in_app)
            settings: Channel settings
            category_preferences: Category-level preferences for channel
            
        Returns:
            Success status
        """
        try:
            success = self.preference_repo.update_channel_preferences(
                user_id,
                channel,
                settings,
                category_preferences
            )
            
            if success:
                logger.info(f"Channel preferences updated for user {user_id}: {channel}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error updating channel preferences: {str(e)}", exc_info=True)
            raise PreferenceError(f"Failed to update channel preferences: {str(e)}")

    def generate_unsubscribe_link(
        self,
        user_id: UUID,
        unsubscribe_type: str = 'all',
        category: Optional[str] = None
    ) -> str:
        """
        Generate secure unsubscribe link.
        
        Args:
            user_id: User ID
            unsubscribe_type: Type (all, email, sms, marketing, category)
            category: Specific category if type is 'category'
            
        Returns:
            Unsubscribe URL
        """
        try:
            from app.core.config import settings
            
            token = self.preference_repo.create_unsubscribe_token(
                user_id,
                unsubscribe_type,
                category
            )
            
            unsubscribe_url = f"{settings.APP_URL}/unsubscribe/{token}"
            
            logger.info(f"Unsubscribe link generated for user {user_id}")
            
            return unsubscribe_url
            
        except Exception as e:
            logger.error(f"Error generating unsubscribe link: {str(e)}", exc_info=True)
            raise PreferenceError(f"Failed to generate unsubscribe link: {str(e)}")

    def process_unsubscribe(
        self,
        token: str,
        reason: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process unsubscribe request.
        
        Args:
            token: Unsubscribe token
            reason: Reason for unsubscribing
            ip_address: User's IP address
            
        Returns:
            Unsubscribe result
        """
        try:
            result = self.preference_repo.process_unsubscribe(
                token,
                reason,
                ip_address
            )
            
            if result['success']:
                logger.info(
                    f"Unsubscribe processed: {result['unsubscribe_type']} "
                    f"for user {result['user_id']}"
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Error processing unsubscribe: {str(e)}", exc_info=True)
            raise PreferenceError(f"Failed to process unsubscribe: {str(e)}")

    def get_users_in_quiet_hours(
        self,
        check_time: Optional[datetime] = None
    ) -> List[UUID]:
        """
        Find users currently in quiet hours.
        
        Args:
            check_time: Time to check (default: now)
            
        Returns:
            List of user IDs in quiet hours
        """
        try:
            return self.preference_repo.find_users_in_quiet_hours(check_time)
        except Exception as e:
            logger.error(f"Error finding users in quiet hours: {str(e)}", exc_info=True)
            return []

    def get_users_for_digest(
        self,
        digest_type: str,
        target_time: Optional[time] = None
    ) -> List[UUID]:
        """
        Get users eligible for digest notifications.
        
        Args:
            digest_type: 'daily' or 'weekly'
            target_time: Target time to check
            
        Returns:
            List of user IDs
        """
        try:
            return self.preference_repo.get_users_for_digest(digest_type, target_time)
        except Exception as e:
            logger.error(f"Error getting digest users: {str(e)}", exc_info=True)
            return []

    def get_preference_analytics(self) -> Dict[str, Any]:
        """Get comprehensive preference analytics."""
        try:
            return self.preference_repo.get_preference_analytics()
        except Exception as e:
            logger.error(f"Error getting preference analytics: {str(e)}", exc_info=True)
            raise

    def get_preference_trends(
        self,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """Get preference change trends."""
        try:
            return self.preference_repo.get_preference_trends(days)
        except Exception as e:
            logger.error(f"Error getting preference trends: {str(e)}", exc_info=True)
            raise

    def bulk_update_preferences(
        self,
        user_ids: List[UUID],
        updates: Dict[str, Any]
    ) -> int:
        """
        Bulk update preferences for multiple users.
        
        Args:
            user_ids: List of user IDs
            updates: Preference updates to apply
            
        Returns:
            Number of users updated
        """
        try:
            updated_count = self.preference_repo.bulk_update_preferences(
                user_ids,
                updates
            )
            
            logger.info(f"Bulk updated preferences for {updated_count} users")
            
            return updated_count
            
        except Exception as e:
            logger.error(f"Error bulk updating preferences: {str(e)}", exc_info=True)
            return 0



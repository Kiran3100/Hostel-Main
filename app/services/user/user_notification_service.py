# --- File: C:\Hostel-Main\app\services\user\user_notification_service.py ---
"""
User Notification Service - User-specific notification management.
"""
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from app.repositories.user import UserRepository, UserProfileRepository
from app.core.exceptions import EntityNotFoundError


class UserNotificationService:
    """
    Service for managing user notifications and communication.
    Coordinates with notification system based on user preferences.
    """

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)
        self.profile_repo = UserProfileRepository(db)

    # ==================== Notification Sending ====================

    def send_notification(
        self,
        user_id: str,
        notification_type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        channels: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Send notification to user based on preferences.
        
        Args:
            user_id: User ID
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            data: Additional data
            channels: Specific channels to use (overrides preferences)
            
        Returns:
            Notification send status
        """
        user = self.user_repo.get_by_id(user_id)
        profile = self.profile_repo.get_by_user_id(user_id)
        
        # Get user preferences
        prefs = profile.notification_preferences if profile else {}
        
        # Determine channels to use
        if not channels:
            channels = self._get_enabled_channels(prefs, notification_type)
        
        results = {
            'user_id': user_id,
            'notification_type': notification_type,
            'channels_used': channels,
            'sent': []
        }
        
        # Send to each channel
        for channel in channels:
            if channel == 'email' and user.is_email_verified:
                # TODO: Integrate with email service
                results['sent'].append({
                    'channel': 'email',
                    'status': 'sent',
                    'destination': user.email
                })
            
            elif channel == 'sms' and user.is_phone_verified:
                # TODO: Integrate with SMS service
                results['sent'].append({
                    'channel': 'sms',
                    'status': 'sent',
                    'destination': user.phone
                })
            
            elif channel == 'push':
                # TODO: Integrate with push notification service
                results['sent'].append({
                    'channel': 'push',
                    'status': 'sent'
                })
        
        return results

    def _get_enabled_channels(
        self,
        preferences: Dict[str, Any],
        notification_type: str
    ) -> List[str]:
        """
        Get enabled notification channels based on preferences.
        
        Args:
            preferences: User notification preferences
            notification_type: Type of notification
            
        Returns:
            List of enabled channels
        """
        channels = []
        
        # Check if this notification type is enabled
        type_key = f'{notification_type}_notifications'
        if not preferences.get(type_key, True):
            return channels
        
        # Add enabled channels
        if preferences.get('email_notifications', True):
            channels.append('email')
        
        if preferences.get('sms_notifications', False):
            channels.append('sms')
        
        if preferences.get('push_notifications', True):
            channels.append('push')
        
        return channels

    # ==================== Bulk Notifications ====================

    def send_bulk_notification(
        self,
        user_ids: List[str],
        notification_type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Send notification to multiple users.
        
        Args:
            user_ids: List of user IDs
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            data: Additional data
            
        Returns:
            Bulk send summary
        """
        results = {
            'total_users': len(user_ids),
            'sent_count': 0,
            'failed_count': 0,
            'failed_users': []
        }
        
        for user_id in user_ids:
            try:
                self.send_notification(
                    user_id,
                    notification_type,
                    title,
                    message,
                    data
                )
                results['sent_count'] += 1
            except Exception as e:
                results['failed_count'] += 1
                results['failed_users'].append({
                    'user_id': user_id,
                    'error': str(e)
                })
        
        return results

    # ==================== Notification Templates ====================

    def send_welcome_notification(self, user_id: str) -> Dict[str, Any]:
        """Send welcome notification to new user."""
        user = self.user_repo.get_by_id(user_id)
        
        return self.send_notification(
            user_id=user_id,
            notification_type='announcement',
            title='Welcome to Our Platform!',
            message=f'Hello {user.full_name}, welcome to our hostel management system!',
            channels=['email', 'push']
        )

    def send_verification_reminder(self, user_id: str) -> Dict[str, Any]:
        """Send verification reminder."""
        user = self.user_repo.get_by_id(user_id)
        
        unverified = []
        if not user.is_email_verified:
            unverified.append('email')
        if not user.is_phone_verified:
            unverified.append('phone')
        
        if not unverified:
            return {'status': 'no_action_needed'}
        
        return self.send_notification(
            user_id=user_id,
            notification_type='announcement',
            title='Verify Your Account',
            message=f'Please verify your {" and ".join(unverified)} to access all features.',
            channels=['email' if 'phone' in unverified else 'sms']
        )

    def send_profile_completion_reminder(self, user_id: str) -> Dict[str, Any]:
        """Send profile completion reminder."""
        profile = self.profile_repo.get_by_user_id(user_id)
        
        if not profile or profile.profile_completion_percentage >= 80:
            return {'status': 'no_action_needed'}
        
        return self.send_notification(
            user_id=user_id,
            notification_type='announcement',
            title='Complete Your Profile',
            message=f'Your profile is {profile.profile_completion_percentage}% complete. Complete it to unlock all features!',
            channels=['email']
        )

    def send_security_alert(
        self,
        user_id: str,
        alert_type: str,
        details: str
    ) -> Dict[str, Any]:
        """Send security alert."""
        return self.send_notification(
            user_id=user_id,
            notification_type='announcement',
            title=f'Security Alert: {alert_type}',
            message=details,
            channels=['email', 'sms', 'push']
        )

    def send_password_changed_notification(self, user_id: str) -> Dict[str, Any]:
        """Send notification when password is changed."""
        return self.send_notification(
            user_id=user_id,
            notification_type='announcement',
            title='Password Changed',
            message='Your password was recently changed. If you did not make this change, please contact support immediately.',
            channels=['email', 'sms']
        )

    def send_login_from_new_device(
        self,
        user_id: str,
        device_info: Dict[str, Any],
        ip_address: str
    ) -> Dict[str, Any]:
        """Send notification for login from new device."""
        device_name = device_info.get('device_type', 'Unknown device')
        
        return self.send_notification(
            user_id=user_id,
            notification_type='announcement',
            title='New Device Login',
            message=f'Your account was accessed from a new device ({device_name}) at IP {ip_address}.',
            channels=['email', 'push']
        )

    # ==================== Digest Notifications ====================

    def send_daily_digest(self, user_id: str) -> Dict[str, Any]:
        """Send daily activity digest."""
        profile = self.profile_repo.get_by_user_id(user_id)
        
        if not profile:
            return {'status': 'no_profile'}
        
        prefs = profile.notification_preferences or {}
        
        if prefs.get('digest_frequency') != 'daily':
            return {'status': 'not_subscribed_to_daily'}
        
        # Gather digest content
        # TODO: Aggregate user's daily activity
        
        return self.send_notification(
            user_id=user_id,
            notification_type='announcement',
            title='Your Daily Digest',
            message='Here is your daily activity summary...',
            channels=['email']
        )

    def send_weekly_digest(self, user_id: str) -> Dict[str, Any]:
        """Send weekly activity digest."""
        profile = self.profile_repo.get_by_user_id(user_id)
        
        if not profile:
            return {'status': 'no_profile'}
        
        prefs = profile.notification_preferences or {}
        
        if prefs.get('digest_frequency') != 'weekly':
            return {'status': 'not_subscribed_to_weekly'}
        
        return self.send_notification(
            user_id=user_id,
            notification_type='announcement',
            title='Your Weekly Summary',
            message='Here is your weekly activity summary...',
            channels=['email']
        )

    # ==================== Preference-Based Sending ====================

    def can_send_notification(
        self,
        user_id: str,
        notification_type: str
    ) -> bool:
        """
        Check if notification can be sent based on user preferences.
        
        Args:
            user_id: User ID
            notification_type: Type of notification
            
        Returns:
            True if can send
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        
        if not profile:
            return True  # Default to allowing
        
        prefs = profile.notification_preferences or {}
        
        # Check if notification type is enabled
        type_key = f'{notification_type}_notifications'
        return prefs.get(type_key, True)

    def is_in_quiet_hours(self, user_id: str) -> bool:
        """
        Check if user is in quiet hours.
        
        Args:
            user_id: User ID
            
        Returns:
            True if in quiet hours
        """
        profile = self.profile_repo.get_by_user_id(user_id)
        
        if not profile:
            return False
        
        prefs = profile.notification_preferences or {}
        
        quiet_start = prefs.get('quiet_hours_start')
        quiet_end = prefs.get('quiet_hours_end')
        
        if not quiet_start or not quiet_end:
            return False
        
        # Parse time and check
        # TODO: Implement proper time zone aware quiet hours check
        
        return False



# --- File: C:\Hostel-Main\app\services\notification\push_notification_service.py ---
"""
Push Notification Service - Handles push delivery across iOS, Android, and Web.

Integrates with FCM (Firebase Cloud Messaging) and APNs (Apple Push Notification service)
for device-specific push notification delivery with badge management and engagement tracking.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
import json

from sqlalchemy.orm import Session

from app.models.notification.notification import Notification
from app.models.notification.push_notification import PushNotification
from app.models.notification.device_token import DeviceToken
from app.repositories.notification.push_notification_repository import (
    PushNotificationRepository
)
from app.repositories.notification.device_token_repository import DeviceTokenRepository
from app.repositories.notification.notification_repository import NotificationRepository
from app.schemas.common.enums import NotificationStatus, DeviceType
from app.core.config import settings
from app.core.exceptions import PushDeliveryError

logger = logging.getLogger(__name__)


class PushNotificationService:
    """
    Service for push notification delivery and device management.
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.push_repo = PushNotificationRepository(db_session)
        self.device_repo = DeviceTokenRepository(db_session)
        self.notification_repo = NotificationRepository(db_session)
        
        # Initialize push providers
        self.fcm_provider = self._initialize_fcm_provider()
        self.apns_provider = self._initialize_apns_provider()
        self.web_push_provider = self._initialize_web_push_provider()

    def send_push(
        self,
        notification: Notification,
        device_token_id: Optional[UUID] = None,
        image_url: Optional[str] = None,
        action_url: Optional[str] = None,
        actions: Optional[List[Dict[str, str]]] = None,
        badge_strategy: str = 'increment',
        sound: str = 'default',
        priority: str = 'high',
        ttl: int = 86400,
        data: Optional[Dict[str, Any]] = None
    ) -> List[PushNotification]:
        """
        Send push notification to user's devices.
        
        Args:
            notification: Base notification object
            device_token_id: Specific device to target (None = all user devices)
            image_url: Large image URL for rich notifications
            action_url: Deep link or URL to open
            actions: List of action buttons
            badge_strategy: How to handle badge count (set/increment/decrement)
            sound: Notification sound
            priority: Notification priority (low/normal/high)
            ttl: Time to live in seconds
            data: Custom data payload
            
        Returns:
            List of PushNotification objects for each device
        """
        try:
            # Get target devices
            if device_token_id:
                devices = [self.device_repo.find_by_id(device_token_id)]
                if not devices[0]:
                    raise PushDeliveryError("Device token not found")
            else:
                # Get all active devices for user
                if not notification.recipient_user_id:
                    raise PushDeliveryError("No recipient user ID for push notification")
                
                devices = self.device_repo.find_active_tokens_for_user(
                    notification.recipient_user_id
                )
                
                if not devices:
                    logger.warning(
                        f"No active devices found for user {notification.recipient_user_id}"
                    )
                    return []
            
            # Prepare push notifications for each device
            push_notifications = []
            
            for device in devices:
                try:
                    push_notification = self._send_to_device(
                        notification=notification,
                        device=device,
                        image_url=image_url,
                        action_url=action_url,
                        actions=actions,
                        badge_strategy=badge_strategy,
                        sound=sound,
                        priority=priority,
                        ttl=ttl,
                        data=data
                    )
                    
                    push_notifications.append(push_notification)
                    
                except Exception as e:
                    logger.error(
                        f"Error sending push to device {device.id}: {str(e)}",
                        exc_info=True
                    )
                    continue
            
            if push_notifications:
                # Update notification status
                notification.status = NotificationStatus.SENT
                notification.sent_at = datetime.utcnow()
                self.db_session.commit()
            else:
                notification.status = NotificationStatus.FAILED
                notification.failed_at = datetime.utcnow()
                notification.failure_reason = "No push notifications delivered"
                self.db_session.commit()
            
            return push_notifications
            
        except Exception as e:
            logger.error(f"Error sending push notification: {str(e)}", exc_info=True)
            
            # Update notification as failed
            notification.status = NotificationStatus.FAILED
            notification.failed_at = datetime.utcnow()
            notification.failure_reason = str(e)
            self.db_session.commit()
            
            raise PushDeliveryError(f"Failed to send push notification: {str(e)}")

    def _send_to_device(
        self,
        notification: Notification,
        device: DeviceToken,
        image_url: Optional[str],
        action_url: Optional[str],
        actions: Optional[List[Dict[str, str]]],
        badge_strategy: str,
        sound: str,
        priority: str,
        ttl: int,
        data: Optional[Dict[str, Any]]
    ) -> PushNotification:
        """Send push notification to a specific device."""
        # Calculate badge count
        badge_count = self._calculate_badge_count(device, badge_strategy)
        
        # Create push notification record
        push_data = {
            'title': notification.subject or 'Notification',
            'body': notification.message_body[:500],  # Limit to 500 chars
            'image_url': image_url,
            'action_url': action_url,
            'actions': actions or [],
            'badge_count': badge_count,
            'badge_strategy': badge_strategy,
            'sound': sound,
            'priority': priority,
            'ttl': ttl,
            'data': data or {},
            'device_token_id': device.id
        }
        
        # Platform-specific settings
        if device.device_type == DeviceType.ANDROID.value:
            push_data['android_channel_id'] = settings.ANDROID_NOTIFICATION_CHANNEL_ID
        elif device.device_type == DeviceType.IOS.value:
            push_data['ios_category'] = settings.IOS_NOTIFICATION_CATEGORY
        
        push_notification = self.push_repo.create_push_with_targeting(
            notification=notification,
            push_data=push_data,
            device_token_id=device.id
        )
        
        # Send via appropriate provider
        try:
            if device.device_type == DeviceType.IOS.value:
                provider_response = self._send_via_apns(
                    device_token=device.device_token,
                    push_notification=push_notification
                )
            elif device.device_type == DeviceType.ANDROID.value:
                provider_response = self._send_via_fcm(
                    device_token=device.device_token,
                    push_notification=push_notification
                )
            elif device.device_type == DeviceType.WEB.value:
                provider_response = self._send_via_web_push(
                    device_token=device.device_token,
                    push_notification=push_notification
                )
            else:
                raise PushDeliveryError(f"Unsupported device type: {device.device_type}")
            
            # Update push notification with provider response
            push_notification.provider_message_id = provider_response.get('message_id')
            push_notification.provider_response = provider_response
            push_notification.delivery_status = 'sent'
            push_notification.delivered = True
            
            # Update device last used
            device.last_used_at = datetime.utcnow()
            
            # Update badge count on device
            if device.device_type == DeviceType.IOS.value:
                device.current_badge_count = badge_count
            
            self.db_session.commit()
            
            logger.info(
                f"Push notification sent to device {device.id} ({device.device_type})"
            )
            
            return push_notification
            
        except Exception as e:
            # Check if token is invalid
            if self._is_invalid_token_error(e):
                logger.warning(f"Invalid device token {device.id}, marking as invalid")
                device.mark_invalid()
                self.db_session.commit()
            
            # Update push notification as failed
            push_notification.delivered = False
            push_notification.delivery_status = 'failed'
            push_notification.error_code = getattr(e, 'code', 'UNKNOWN')
            push_notification.error_message = str(e)
            
            self.db_session.commit()
            
            raise

    def handle_delivery_receipt(
        self,
        provider_message_id: str,
        delivered: bool,
        delivery_status: str,
        provider_response: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Handle push delivery receipt from provider."""
        try:
            push = self.push_repo.find_by_provider_message_id(provider_message_id)
            
            if not push:
                logger.warning(
                    f"Push notification not found for message ID: {provider_message_id}"
                )
                return False
            
            error_details = None
            if error_code or error_message:
                error_details = {
                    'code': error_code,
                    'message': error_message
                }
            
            success = self.push_repo.update_delivery_status(
                push.id,
                delivered,
                delivery_status,
                provider_response,
                error_details
            )
            
            return success
            
        except Exception as e:
            logger.error(f"Error handling delivery receipt: {str(e)}", exc_info=True)
            return False

    def track_push_tap(
        self,
        push_id: UUID,
        action_taken: Optional[str] = None
    ) -> bool:
        """Track push notification tap."""
        try:
            return self.push_repo.track_push_tap(push_id, action_taken)
        except Exception as e:
            logger.error(f"Error tracking push tap: {str(e)}", exc_info=True)
            return False

    def update_badge_count_for_user(
        self,
        user_id: UUID,
        count: Optional[int] = None,
        increment: Optional[int] = None,
        decrement: Optional[int] = None
    ) -> int:
        """Update badge count for user's iOS devices."""
        try:
            if count is not None:
                # Set specific count
                devices = self.device_repo.find_active_tokens_by_type(
                    user_id,
                    DeviceType.IOS
                )
                for device in devices:
                    device.current_badge_count = max(0, count)
                self.db_session.commit()
                return len(devices)
            elif increment is not None:
                return self.device_repo.increment_badge_for_user(user_id, increment)
            elif decrement is not None:
                return self.device_repo.increment_badge_for_user(user_id, -decrement)
            
            return 0
            
        except Exception as e:
            logger.error(f"Error updating badge count: {str(e)}", exc_info=True)
            return 0

    def reset_badge_count_for_user(self, user_id: UUID) -> int:
        """Reset badge count to 0 for user's iOS devices."""
        try:
            return self.device_repo.reset_badge_for_user(user_id)
        except Exception as e:
            logger.error(f"Error resetting badge count: {str(e)}", exc_info=True)
            return 0

    def get_delivery_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        device_type: Optional[DeviceType] = None,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get push notification delivery analytics."""
        try:
            return self.push_repo.get_delivery_analytics(
                start_date,
                end_date,
                device_type,
                hostel_id
            )
        except Exception as e:
            logger.error(f"Error getting delivery analytics: {str(e)}", exc_info=True)
            raise

    def get_engagement_trends(
        self,
        days: int = 30,
        group_by: str = 'day'
    ) -> List[Dict[str, Any]]:
        """Get push notification engagement trends."""
        try:
            return self.push_repo.get_engagement_trends(days, group_by)
        except Exception as e:
            logger.error(f"Error getting engagement trends: {str(e)}", exc_info=True)
            raise

    # Helper methods
    def _initialize_fcm_provider(self):
        """Initialize Firebase Cloud Messaging provider."""
        from app.integrations.push.fcm_provider import FCMProvider
        return FCMProvider()

    def _initialize_apns_provider(self):
        """Initialize Apple Push Notification service provider."""
        from app.integrations.push.apns_provider import APNsProvider
        return APNsProvider()

    def _initialize_web_push_provider(self):
        """Initialize Web Push provider."""
        from app.integrations.push.web_push_provider import WebPushProvider
        return WebPushProvider()

    def _send_via_fcm(
        self,
        device_token: str,
        push_notification: PushNotification
    ) -> Dict[str, Any]:
        """Send push via Firebase Cloud Messaging."""
        payload = {
            'token': device_token,
            'notification': {
                'title': push_notification.title,
                'body': push_notification.body,
            },
            'data': push_notification.data,
            'android': {
                'priority': push_notification.priority,
                'ttl': f'{push_notification.ttl}s',
                'notification': {
                    'channel_id': push_notification.android_channel_id,
                    'sound': push_notification.sound,
                }
            }
        }
        
        if push_notification.image_url:
            payload['notification']['image'] = push_notification.image_url
        
        return self.fcm_provider.send(payload)

    def _send_via_apns(
        self,
        device_token: str,
        push_notification: PushNotification
    ) -> Dict[str, Any]:
        """Send push via Apple Push Notification service."""
        payload = {
            'token': device_token,
            'aps': {
                'alert': {
                    'title': push_notification.title,
                    'body': push_notification.body,
                },
                'badge': push_notification.badge_count,
                'sound': push_notification.sound,
                'category': push_notification.ios_category,
            },
            'data': push_notification.data
        }
        
        if push_notification.action_url:
            payload['data']['url'] = push_notification.action_url
        
        return self.apns_provider.send(payload)

    def _send_via_web_push(
        self,
        device_token: str,
        push_notification: PushNotification
    ) -> Dict[str, Any]:
        """Send web push notification."""
        payload = {
            'subscription': json.loads(device_token),
            'data': json.dumps({
                'title': push_notification.title,
                'body': push_notification.body,
                'icon': push_notification.icon,
                'image': push_notification.image_url,
                'data': push_notification.data,
            }),
            'ttl': push_notification.ttl
        }
        
        return self.web_push_provider.send(payload)

    def _calculate_badge_count(
        self,
        device: DeviceToken,
        strategy: str
    ) -> int:
        """Calculate badge count based on strategy."""
        current_count = device.current_badge_count or 0
        
        if strategy == 'set':
            return 1
        elif strategy == 'increment':
            return current_count + 1
        elif strategy == 'decrement':
            return max(0, current_count - 1)
        else:
            return current_count

    def _is_invalid_token_error(self, error: Exception) -> bool:
        """Check if error indicates invalid device token."""
        error_str = str(error).lower()
        invalid_indicators = [
            'invalid token',
            'unregistered',
            'not registered',
            'baddevicetoken',
            'invalid registration'
        ]
        
        return any(indicator in error_str for indicator in invalid_indicators)
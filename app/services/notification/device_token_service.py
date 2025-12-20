# --- File: C:\Hostel-Main\app\services\notification\device_token_service.py ---
"""
Device Token Service - Manages device registration for push notifications.

Handles device token lifecycle, badge management, and device analytics.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from app.models.notification.device_token import DeviceToken
from app.repositories.notification.device_token_repository import DeviceTokenRepository
from app.schemas.common.enums import DeviceType
from app.core.exceptions import DeviceTokenError

logger = logging.getLogger(__name__)


class DeviceTokenService:
    """
    Service for device token management.
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.device_repo = DeviceTokenRepository(db_session)

    def register_device(
        self,
        user_id: UUID,
        device_token: str,
        device_type: DeviceType,
        device_name: Optional[str] = None,
        device_model: Optional[str] = None,
        os_version: Optional[str] = None,
        app_version: Optional[str] = None,
        timezone: Optional[str] = None,
        locale: Optional[str] = None
    ) -> DeviceToken:
        """
        Register or update device token.
        
        Args:
            user_id: User ID
            device_token: Push notification token
            device_type: Device platform
            device_name: Device name
            device_model: Device model
            os_version: OS version
            app_version: App version
            timezone: Device timezone
            locale: Device locale
            
        Returns:
            DeviceToken
        """
        try:
            device_info = {
                'device_name': device_name,
                'device_model': device_model,
                'os_version': os_version,
                'app_version': app_version,
                'timezone': timezone,
                'locale': locale
            }
            
            # Remove None values
            device_info = {k: v for k, v in device_info.items() if v is not None}
            
            device = self.device_repo.register_or_update_token(
                user_id,
                device_token,
                device_type,
                device_info
            )
            
            logger.info(
                f"Device registered for user {user_id}: {device_type.value}"
            )
            
            return device
            
        except Exception as e:
            logger.error(f"Error registering device: {str(e)}", exc_info=True)
            raise DeviceTokenError(f"Failed to register device: {str(e)}")

    def unregister_device(
        self,
        user_id: UUID,
        device_token: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Unregister device token.
        
        Args:
            user_id: User ID
            device_token: Device token to unregister
            reason: Reason for unregistration
            
        Returns:
            Success status
        """
        try:
            device = self.device_repo.find_by_user_and_token(user_id, device_token)
            
            if not device:
                logger.warning(f"Device token not found for user {user_id}")
                return False
            
            success = self.device_repo.deactivate_token(device.id, reason)
            
            if success:
                logger.info(f"Device unregistered for user {user_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error unregistering device: {str(e)}", exc_info=True)
            return False

    def get_user_devices(
        self,
        user_id: UUID,
        active_only: bool = True
    ) -> List[DeviceToken]:
        """
        Get user's registered devices.
        
        Args:
            user_id: User ID
            active_only: Return only active devices
            
        Returns:
            List of devices
        """
        try:
            if active_only:
                return self.device_repo.find_active_tokens_for_user(user_id)
            else:
                return self.db_session.query(DeviceToken).filter(
                    DeviceToken.user_id == user_id
                ).all()
                
        except Exception as e:
            logger.error(f"Error getting user devices: {str(e)}", exc_info=True)
            return []

    def update_badge_count(
        self,
        device_token_id: UUID,
        count: int
    ) -> bool:
        """
        Update badge count for device.
        
        Args:
            device_token_id: Device ID
            count: New badge count
            
        Returns:
            Success status
        """
        try:
            return self.device_repo.update_badge_count(device_token_id, count)
        except Exception as e:
            logger.error(f"Error updating badge count: {str(e)}", exc_info=True)
            return False

    def increment_user_badge(
        self,
        user_id: UUID,
        amount: int = 1
    ) -> int:
        """
        Increment badge count for all user's iOS devices.
        
        Args:
            user_id: User ID
            amount: Amount to increment
            
        Returns:
            Number of devices updated
        """
        try:
            return self.device_repo.increment_badge_for_user(user_id, amount)
        except Exception as e:
            logger.error(f"Error incrementing badge: {str(e)}", exc_info=True)
            return 0

    def reset_user_badge(
        self,
        user_id: UUID
    ) -> int:
        """
        Reset badge count for all user's iOS devices.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of devices updated
        """
        try:
            return self.device_repo.reset_badge_for_user(user_id)
        except Exception as e:
            logger.error(f"Error resetting badge: {str(e)}", exc_info=True)
            return 0

    def mark_token_invalid(
        self,
        device_token: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Mark device token as invalid (from provider feedback).
        
        Args:
            device_token: Device token
            reason: Reason for invalidity
            
        Returns:
            Success status
        """
        try:
            return self.device_repo.mark_token_invalid(device_token, reason)
        except Exception as e:
            logger.error(f"Error marking token invalid: {str(e)}", exc_info=True)
            return False

    def cleanup_stale_tokens(
        self,
        days: int = 90
    ) -> int:
        """
        Clean up stale device tokens.
        
        Args:
            days: Days of inactivity before considering stale
            
        Returns:
            Number of tokens cleaned up
        """
        try:
            stale_tokens = self.device_repo.find_stale_tokens(days)
            
            for token in stale_tokens:
                self.device_repo.deactivate_token(
                    token.id,
                    f"Inactive for {days} days"
                )
            
            logger.info(f"Cleaned up {len(stale_tokens)} stale device tokens")
            
            return len(stale_tokens)
            
        except Exception as e:
            logger.error(f"Error cleaning up stale tokens: {str(e)}", exc_info=True)
            return 0

    def cleanup_invalid_tokens(
        self,
        batch_size: int = 1000
    ) -> int:
        """
        Clean up invalid device tokens.
        
        Args:
            batch_size: Batch size for cleanup
            
        Returns:
            Number of tokens deleted
        """
        try:
            deleted = self.device_repo.cleanup_invalid_tokens(batch_size)
            
            if deleted > 0:
                logger.info(f"Deleted {deleted} invalid device tokens")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Error cleaning up invalid tokens: {str(e)}", exc_info=True)
            return 0

    def get_device_statistics(self) -> Dict[str, Any]:
        """Get device token statistics."""
        try:
            return self.device_repo.get_device_statistics()
        except Exception as e:
            logger.error(f"Error getting device statistics: {str(e)}", exc_info=True)
            raise



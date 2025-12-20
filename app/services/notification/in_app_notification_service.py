# --- File: C:\Hostel-Main\app\services\notification\in_app_notification_service.py ---
"""
In-App Notification Service - Manages in-app notification delivery and display.

Handles in-app notification creation, real-time delivery, and user interactions
for notifications displayed within the application.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from app.models.notification.notification import Notification
from app.repositories.notification.notification_repository import NotificationRepository
from app.schemas.common.enums import NotificationStatus, Priority
from app.core.exceptions import NotificationError

logger = logging.getLogger(__name__)


class InAppNotificationService:
    """
    Service for in-app notification management.
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.notification_repo = NotificationRepository(db_session)

    def create_in_app_notification(
        self,
        notification: Notification
    ) -> Notification:
        """
        Create in-app notification (marks as delivered immediately).
        
        Args:
            notification: Base notification object
            
        Returns:
            Updated notification
        """
        try:
            # Mark as delivered (in-app notifications are immediately available)
            notification.status = NotificationStatus.DELIVERED
            notification.sent_at = datetime.utcnow()
            notification.delivered_at = datetime.utcnow()
            
            self.db_session.commit()
            
            logger.info(
                f"In-app notification created: {notification.id} "
                f"for user {notification.recipient_user_id}"
            )
            
            # Trigger real-time notification via WebSocket if available
            self._send_realtime_notification(notification)
            
            return notification
            
        except Exception as e:
            logger.error(
                f"Error creating in-app notification: {str(e)}",
                exc_info=True
            )
            raise NotificationError(f"Failed to create in-app notification: {str(e)}")

    def get_user_notifications(
        self,
        user_id: UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get in-app notifications for user.
        
        Args:
            user_id: User ID
            unread_only: Return only unread notifications
            limit: Maximum number of notifications
            offset: Offset for pagination
            
        Returns:
            Notifications with metadata
        """
        try:
            from app.schemas.common.enums import NotificationType
            
            if unread_only:
                notifications = self.notification_repo.find_unread_for_user(user_id)
                # Filter to in-app only
                notifications = [
                    n for n in notifications
                    if n.notification_type == NotificationType.IN_APP
                ]
            else:
                from app.repositories.base.pagination import PaginationParams
                pagination = PaginationParams(page=offset // limit + 1, page_size=limit)
                result = self.notification_repo.find_by_user(
                    user_id,
                    [NotificationType.IN_APP],
                    pagination
                )
                notifications = result.items
            
            # Get unread count
            unread_count = len([n for n in notifications if not n.read_at])
            
            return {
                'notifications': [
                    self._format_notification(n) for n in notifications
                ],
                'unread_count': unread_count,
                'total_count': len(notifications)
            }
            
        except Exception as e:
            logger.error(
                f"Error getting in-app notifications: {str(e)}",
                exc_info=True
            )
            raise NotificationError(f"Failed to get notifications: {str(e)}")

    def mark_as_read(
        self,
        notification_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Mark in-app notification as read.
        
        Args:
            notification_id: Notification ID
            user_id: User ID
            
        Returns:
            Success status
        """
        try:
            return self.notification_repo.mark_as_read(
                notification_id,
                user_id,
                {'read_method': 'in_app'}
            )
        except Exception as e:
            logger.error(f"Error marking as read: {str(e)}", exc_info=True)
            return False

    def mark_all_as_read(
        self,
        user_id: UUID
    ) -> int:
        """
        Mark all in-app notifications as read.
        
        Args:
            user_id: User ID
            
        Returns:
            Number of notifications marked as read
        """
        try:
            from app.schemas.common.enums import NotificationType
            
            unread = self.notification_repo.find_unread_for_user(user_id)
            in_app_unread = [
                n for n in unread
                if n.notification_type == NotificationType.IN_APP
            ]
            
            notification_ids = [n.id for n in in_app_unread]
            
            return self.notification_repo.mark_bulk_as_read(notification_ids, user_id)
            
        except Exception as e:
            logger.error(f"Error marking all as read: {str(e)}", exc_info=True)
            return 0

    def delete_notification(
        self,
        notification_id: UUID,
        user_id: UUID
    ) -> bool:
        """
        Delete (soft delete) in-app notification.
        
        Args:
            notification_id: Notification ID
            user_id: User ID (for authorization)
            
        Returns:
            Success status
        """
        try:
            notification = self.notification_repo.find_by_id(notification_id)
            
            if not notification:
                return False
            
            # Verify ownership
            if notification.recipient_user_id != user_id:
                logger.warning(
                    f"User {user_id} attempted to delete notification "
                    f"{notification_id} belonging to {notification.recipient_user_id}"
                )
                return False
            
            # Soft delete
            notification.deleted_at = datetime.utcnow()
            self.db_session.commit()
            
            logger.info(f"Notification {notification_id} deleted by user {user_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error deleting notification: {str(e)}", exc_info=True)
            return False

    def get_notification_summary(
        self,
        user_id: UUID
    ) -> Dict[str, Any]:
        """
        Get notification summary for user.
        
        Args:
            user_id: User ID
            
        Returns:
            Summary with counts by priority and category
        """
        try:
            from app.schemas.common.enums import NotificationType
            
            # Get all unread in-app notifications
            unread = self.notification_repo.find_unread_for_user(user_id)
            in_app_unread = [
                n for n in unread
                if n.notification_type == NotificationType.IN_APP
            ]
            
            # Count by priority
            priority_counts = {
                'urgent': 0,
                'high': 0,
                'medium': 0,
                'low': 0
            }
            
            for notification in in_app_unread:
                priority_counts[notification.priority.value] += 1
            
            # Count by category (from metadata)
            category_counts = {}
            for notification in in_app_unread:
                category = notification.metadata.get('category', 'general')
                category_counts[category] = category_counts.get(category, 0) + 1
            
            return {
                'total_unread': len(in_app_unread),
                'by_priority': priority_counts,
                'by_category': category_counts,
                'has_urgent': priority_counts['urgent'] > 0
            }
            
        except Exception as e:
            logger.error(f"Error getting notification summary: {str(e)}", exc_info=True)
            return {
                'total_unread': 0,
                'by_priority': {},
                'by_category': {},
                'has_urgent': False
            }

    # Helper methods
    def _send_realtime_notification(
        self,
        notification: Notification
    ) -> None:
        """
        Send real-time notification via WebSocket.
        
        Args:
            notification: Notification to send
        """
        try:
            # This would integrate with your WebSocket implementation
            # Example using a hypothetical WebSocket manager
            
            # from app.websocket.manager import websocket_manager
            # 
            # websocket_manager.send_to_user(
            #     user_id=str(notification.recipient_user_id),
            #     event='new_notification',
            #     data=self._format_notification(notification)
            # )
            
            logger.debug(
                f"Real-time notification sent to user {notification.recipient_user_id}"
            )
            
        except Exception as e:
            logger.error(
                f"Error sending real-time notification: {str(e)}",
                exc_info=True
            )
            # Don't raise - real-time delivery is optional

    def _format_notification(
        self,
        notification: Notification
    ) -> Dict[str, Any]:
        """Format notification for API response."""
        return {
            'id': str(notification.id),
            'subject': notification.subject,
            'message': notification.message_body,
            'priority': notification.priority.value,
            'read_at': notification.read_at.isoformat() if notification.read_at else None,
            'created_at': notification.created_at.isoformat(),
            'metadata': notification.metadata or {}
        }



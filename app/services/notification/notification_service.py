# --- File: C:\Hostel-Main\app\services\notification\notification_service.py ---
"""
Core Notification Service - Central orchestration for all notification operations.

Handles notification lifecycle, multi-channel delivery, status tracking,
and coordinates with specialized channel services.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Union
from uuid import UUID
import logging

from sqlalchemy.orm import Session

from app.models.notification.notification import Notification
from app.models.user.user import User
from app.repositories.notification.notification_repository import NotificationRepository
from app.repositories.notification.notification_template_repository import NotificationTemplateRepository
from app.repositories.notification.notification_preferences_repository import NotificationPreferencesRepository
from app.repositories.notification.notification_routing_repository import NotificationRoutingRepository
from app.repositories.notification.notification_queue_repository import NotificationQueueRepository
from app.schemas.common.enums import (
    NotificationType,
    NotificationStatus,
    Priority
)
from app.services.notification.email_notification_service import EmailNotificationService
from app.services.notification.sms_notification_service import SMSNotificationService
from app.services.notification.push_notification_service import PushNotificationService
from app.services.notification.in_app_notification_service import InAppNotificationService
from app.core.exceptions import (
    NotificationError,
    TemplateNotFoundError,
    RecipientNotFoundError,
    ValidationError
)

logger = logging.getLogger(__name__)


class NotificationService:
    """
    Central notification service orchestrating all notification operations.
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.notification_repo = NotificationRepository(db_session)
        self.template_repo = NotificationTemplateRepository(db_session)
        self.preferences_repo = NotificationPreferencesRepository(db_session)
        self.routing_repo = NotificationRoutingRepository(db_session)
        self.queue_repo = NotificationQueueRepository(db_session)
        
        # Channel-specific services
        self.email_service = EmailNotificationService(db_session)
        self.sms_service = SMSNotificationService(db_session)
        self.push_service = PushNotificationService(db_session)
        self.in_app_service = InAppNotificationService(db_session)

    # Core notification operations
    def send_notification(
        self,
        recipient_user_id: Optional[UUID] = None,
        recipient_email: Optional[str] = None,
        recipient_phone: Optional[str] = None,
        notification_type: NotificationType = None,
        subject: Optional[str] = None,
        message_body: str = None,
        template_code: Optional[str] = None,
        template_variables: Optional[Dict[str, Any]] = None,
        priority: Priority = Priority.MEDIUM,
        scheduled_at: Optional[datetime] = None,
        hostel_id: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None,
        channels: Optional[List[str]] = None,
        auto_route: bool = True
    ) -> Union[Notification, List[Notification]]:
        """
        Send notification with automatic routing and channel selection.
        
        Args:
            recipient_user_id: Target user ID
            recipient_email: Direct email address
            recipient_phone: Direct phone number
            notification_type: Specific channel or auto-detect
            subject: Notification subject (for email/push)
            message_body: Message content (if not using template)
            template_code: Template to use
            template_variables: Variables for template rendering
            priority: Notification priority
            scheduled_at: Schedule for future delivery
            hostel_id: Associated hostel
            metadata: Additional metadata
            channels: Specific channels to use (overrides routing)
            auto_route: Apply routing rules automatically
            
        Returns:
            Notification or list of notifications (multi-channel)
        """
        try:
            # Validate recipient
            if not any([recipient_user_id, recipient_email, recipient_phone]):
                raise ValidationError("At least one recipient identifier required")
            
            # Get user preferences if user_id provided
            user_preferences = None
            if recipient_user_id:
                user_preferences = self.preferences_repo.get_or_create_preferences(
                    recipient_user_id
                )
                
                # Check if user has notifications enabled
                if not user_preferences.notifications_enabled:
                    logger.info(f"Notifications disabled for user {recipient_user_id}")
                    return None
                
                # Check quiet hours
                if self._is_in_quiet_hours(user_preferences, priority):
                    if priority != Priority.URGENT:
                        # Queue for later delivery
                        return self._schedule_for_after_quiet_hours(
                            user_preferences,
                            recipient_user_id,
                            template_code,
                            template_variables,
                            metadata
                        )
            
            # Apply routing rules if enabled
            if auto_route and hostel_id:
                routing_context = {
                    'hostel_id': hostel_id,
                    'priority': priority.value,
                    'event_type': metadata.get('event_type') if metadata else None,
                    'user_role': metadata.get('user_role') if metadata else None
                }
                
                matched_rules = self.routing_repo.find_matching_rules(
                    routing_context,
                    hostel_id
                )
                
                if matched_rules:
                    # Use first matching rule
                    rule = matched_rules[0]
                    channels = channels or rule.channels
                    template_code = template_code or rule.template_code
            
            # Prepare content from template or direct input
            if template_code:
                content = self._render_template(template_code, template_variables or {})
                subject = subject or content.get('subject')
                message_body = message_body or content.get('body')
            elif not message_body:
                raise ValidationError("Either template_code or message_body required")
            
            # Determine channels to use
            target_channels = self._determine_channels(
                notification_type,
                channels,
                user_preferences
            )
            
            # Create notifications for each channel
            notifications = []
            for channel in target_channels:
                notification = self._create_notification(
                    channel=channel,
                    recipient_user_id=recipient_user_id,
                    recipient_email=recipient_email,
                    recipient_phone=recipient_phone,
                    subject=subject,
                    message_body=message_body,
                    priority=priority,
                    scheduled_at=scheduled_at,
                    hostel_id=hostel_id,
                    template_code=template_code,
                    template_variables=template_variables,
                    metadata=metadata
                )
                
                # Send immediately or queue
                if scheduled_at and scheduled_at > datetime.utcnow():
                    self._queue_notification(notification, scheduled_at)
                else:
                    self._dispatch_notification(notification)
                
                notifications.append(notification)
            
            return notifications[0] if len(notifications) == 1 else notifications
            
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}", exc_info=True)
            raise NotificationError(f"Failed to send notification: {str(e)}")

    def send_bulk_notifications(
        self,
        recipients: List[Dict[str, Any]],
        template_code: str,
        notification_type: NotificationType,
        priority: Priority = Priority.MEDIUM,
        batch_name: Optional[str] = None,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """
        Send notifications to multiple recipients efficiently.
        
        Args:
            recipients: List of recipient dicts with user_id/email/phone and variables
            template_code: Template to use
            notification_type: Notification channel
            priority: Priority level
            batch_name: Name for this batch
            hostel_id: Associated hostel
            
        Returns:
            Batch information with job tracking
        """
        try:
            # Create batch
            batch = self.queue_repo.create_batch(
                batch_name=batch_name,
                notification_type=notification_type,
                total_notifications=len(recipients)
            )
            
            # Create notifications and queue them
            created_count = 0
            for recipient_data in recipients:
                try:
                    # Render template with recipient-specific variables
                    content = self._render_template(
                        template_code,
                        recipient_data.get('variables', {})
                    )
                    
                    # Create notification
                    notification = self._create_notification(
                        channel=notification_type,
                        recipient_user_id=recipient_data.get('user_id'),
                        recipient_email=recipient_data.get('email'),
                        recipient_phone=recipient_data.get('phone'),
                        subject=content.get('subject'),
                        message_body=content.get('body'),
                        priority=priority,
                        hostel_id=hostel_id,
                        template_code=template_code,
                        template_variables=recipient_data.get('variables'),
                        metadata={'batch_id': str(batch.id)}
                    )
                    
                    # Queue notification
                    self.queue_repo.enqueue_notification(
                        notification=notification,
                        priority=priority,
                        batch_id=batch.id
                    )
                    
                    created_count += 1
                    
                except Exception as e:
                    logger.error(
                        f"Error creating notification for recipient {recipient_data}: {str(e)}"
                    )
                    continue
            
            logger.info(
                f"Created batch {batch.id} with {created_count}/{len(recipients)} notifications"
            )
            
            return {
                'batch_id': str(batch.id),
                'total_recipients': len(recipients),
                'notifications_created': created_count,
                'status': 'queued'
            }
            
        except Exception as e:
            logger.error(f"Error sending bulk notifications: {str(e)}", exc_info=True)
            raise NotificationError(f"Failed to send bulk notifications: {str(e)}")

    def get_user_notifications(
        self,
        user_id: UUID,
        notification_types: Optional[List[NotificationType]] = None,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0
    ) -> Dict[str, Any]:
        """
        Get notifications for a user with filtering and pagination.
        """
        try:
            if unread_only:
                notifications = self.notification_repo.find_unread_for_user(user_id)
            else:
                from app.repositories.base.pagination import PaginationParams
                pagination = PaginationParams(page=offset // limit + 1, page_size=limit)
                result = self.notification_repo.find_by_user(
                    user_id,
                    notification_types,
                    pagination
                )
                notifications = result.items
            
            # Get unread count
            unread_count = self.notification_repo.get_unread_count(user_id)
            
            return {
                'notifications': [self._format_notification(n) for n in notifications],
                'unread_count': unread_count,
                'total_count': len(notifications)
            }
            
        except Exception as e:
            logger.error(f"Error getting user notifications: {str(e)}", exc_info=True)
            raise NotificationError(f"Failed to get notifications: {str(e)}")

    def mark_as_read(
        self,
        notification_id: UUID,
        user_id: UUID,
        read_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Mark notification as read with context tracking."""
        try:
            success = self.notification_repo.mark_as_read(
                notification_id,
                user_id,
                read_context
            )
            
            if success:
                # Update badge counts for mobile devices
                self.push_service.update_badge_count_for_user(user_id, decrement=1)
            
            return success
            
        except Exception as e:
            logger.error(f"Error marking notification as read: {str(e)}", exc_info=True)
            return False

    def mark_all_as_read(self, user_id: UUID) -> int:
        """Mark all unread notifications as read for user."""
        try:
            unread_notifications = self.notification_repo.find_unread_for_user(user_id)
            notification_ids = [n.id for n in unread_notifications]
            
            count = self.notification_repo.mark_bulk_as_read(notification_ids, user_id)
            
            if count > 0:
                # Reset badge count
                self.push_service.reset_badge_count_for_user(user_id)
            
            return count
            
        except Exception as e:
            logger.error(f"Error marking all as read: {str(e)}", exc_info=True)
            return 0

    def retry_failed_notification(self, notification_id: UUID) -> bool:
        """Retry a failed notification."""
        try:
            notification = self.notification_repo.find_by_id(notification_id)
            
            if not notification:
                return False
            
            if not notification.can_retry:
                logger.warning(f"Notification {notification_id} cannot be retried")
                return False
            
            # Increment retry count
            notification.retry_count += 1
            
            # Reset status
            notification.status = NotificationStatus.QUEUED
            notification.failed_at = None
            notification.failure_reason = None
            
            self.db_session.commit()
            
            # Dispatch notification
            self._dispatch_notification(notification)
            
            return True
            
        except Exception as e:
            logger.error(f"Error retrying notification: {str(e)}", exc_info=True)
            return False

    def cancel_scheduled_notification(self, notification_id: UUID) -> bool:
        """Cancel a scheduled notification."""
        try:
            notification = self.notification_repo.find_by_id(notification_id)
            
            if not notification:
                return False
            
            if notification.status not in [NotificationStatus.PENDING, NotificationStatus.QUEUED]:
                logger.warning(
                    f"Cannot cancel notification {notification_id} in status {notification.status}"
                )
                return False
            
            # Update status
            self.notification_repo.update_status(
                notification_id,
                NotificationStatus.CANCELLED,
                {'cancelled_at': datetime.utcnow().isoformat()}
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error cancelling notification: {str(e)}", exc_info=True)
            return False

    # Analytics and reporting
    def get_notification_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None,
        notification_types: Optional[List[NotificationType]] = None
    ) -> Dict[str, Any]:
        """Get comprehensive notification analytics."""
        try:
            # Basic statistics
            stats = self.notification_repo.get_delivery_statistics(
                start_date,
                end_date,
                hostel_id
            )
            
            # Engagement metrics
            engagement = self.notification_repo.get_engagement_metrics(
                start_date,
                end_date
            )
            
            # Channel-specific analytics
            channel_analytics = {}
            
            if not notification_types or NotificationType.EMAIL in notification_types:
                channel_analytics['email'] = self.email_service.get_engagement_analytics(
                    start_date,
                    end_date,
                    hostel_id
                )
            
            if not notification_types or NotificationType.SMS in notification_types:
                channel_analytics['sms'] = self.sms_service.get_cost_analytics(
                    start_date,
                    end_date,
                    hostel_id
                )
            
            if not notification_types or NotificationType.PUSH in notification_types:
                channel_analytics['push'] = self.push_service.get_delivery_analytics(
                    start_date,
                    end_date,
                    hostel_id=hostel_id
                )
            
            return {
                'period': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'statistics': stats,
                'engagement': engagement,
                'channel_analytics': channel_analytics
            }
            
        except Exception as e:
            logger.error(f"Error getting analytics: {str(e)}", exc_info=True)
            raise NotificationError(f"Failed to get analytics: {str(e)}")

    # Helper methods
    def _create_notification(
        self,
        channel: NotificationType,
        recipient_user_id: Optional[UUID],
        recipient_email: Optional[str],
        recipient_phone: Optional[str],
        subject: Optional[str],
        message_body: str,
        priority: Priority,
        scheduled_at: Optional[datetime],
        hostel_id: Optional[UUID],
        template_code: Optional[str],
        template_variables: Optional[Dict[str, Any]],
        metadata: Optional[Dict[str, Any]]
    ) -> Notification:
        """Create notification record."""
        notification_data = {
            'notification_type': channel,
            'recipient_user_id': recipient_user_id,
            'recipient_email': recipient_email,
            'recipient_phone': recipient_phone,
            'subject': subject,
            'message_body': message_body,
            'priority': priority,
            'status': NotificationStatus.PENDING,
            'scheduled_at': scheduled_at,
            'hostel_id': hostel_id,
            'template_code': template_code,
            'metadata': metadata or {}
        }
        
        return self.notification_repo.create_notification(
            notification_data,
            template_variables
        )

    def _dispatch_notification(self, notification: Notification) -> None:
        """Dispatch notification to appropriate channel service."""
        try:
            if notification.notification_type == NotificationType.EMAIL:
                self.email_service.send_email(notification)
            elif notification.notification_type == NotificationType.SMS:
                self.sms_service.send_sms(notification)
            elif notification.notification_type == NotificationType.PUSH:
                self.push_service.send_push(notification)
            elif notification.notification_type == NotificationType.IN_APP:
                self.in_app_service.create_in_app_notification(notification)
            else:
                raise NotificationError(f"Unsupported notification type: {notification.notification_type}")
                
        except Exception as e:
            logger.error(
                f"Error dispatching notification {notification.id}: {str(e)}",
                exc_info=True
            )
            
            # Update notification status
            self.notification_repo.update_status(
                notification.id,
                NotificationStatus.FAILED,
                {'reason': str(e)}
            )

    def _queue_notification(
        self,
        notification: Notification,
        scheduled_at: datetime
    ) -> None:
        """Queue notification for future delivery."""
        self.queue_repo.enqueue_notification(
            notification=notification,
            priority=notification.priority,
            scheduled_for=scheduled_at
        )

    def _render_template(
        self,
        template_code: str,
        variables: Dict[str, Any]
    ) -> Dict[str, str]:
        """Render notification template with variables."""
        return self.template_repo.render_template(
            template_code,
            variables,
            validate_variables=True
        )

    def _determine_channels(
        self,
        notification_type: Optional[NotificationType],
        channels: Optional[List[str]],
        user_preferences: Optional[Any]
    ) -> List[NotificationType]:
        """Determine which channels to use based on type, routing, and preferences."""
        # If specific type provided, use it
        if notification_type:
            return [notification_type]
        
        # If specific channels provided, use them
        if channels:
            return [NotificationType(ch) for ch in channels]
        
        # Default channels based on preferences
        default_channels = []
        
        if user_preferences:
            if user_preferences.email_enabled:
                default_channels.append(NotificationType.EMAIL)
            if user_preferences.push_enabled:
                default_channels.append(NotificationType.PUSH)
            if user_preferences.in_app_enabled:
                default_channels.append(NotificationType.IN_APP)
        else:
            # Fallback to email if no preferences
            default_channels = [NotificationType.EMAIL]
        
        return default_channels

    def _is_in_quiet_hours(
        self,
        preferences: Any,
        priority: Priority
    ) -> bool:
        """Check if current time is within user's quiet hours."""
        if not preferences.quiet_hours_enabled:
            return False
        
        if priority == Priority.URGENT and preferences.quiet_hours_allow_urgent:
            return False
        
        now = datetime.utcnow()
        current_time = now.time()
        current_weekday = now.weekday()
        is_weekend = current_weekday >= 5
        
        # Check if quiet hours apply today
        if is_weekend and not preferences.quiet_hours_weekends:
            return False
        if not is_weekend and not preferences.quiet_hours_weekdays:
            return False
        
        # Check time range
        if preferences.quiet_hours_start and preferences.quiet_hours_end:
            start = preferences.quiet_hours_start
            end = preferences.quiet_hours_end
            
            if start <= end:
                return start <= current_time <= end
            else:
                # Crosses midnight
                return current_time >= start or current_time <= end
        
        return False

    def _schedule_for_after_quiet_hours(
        self,
        preferences: Any,
        user_id: UUID,
        template_code: str,
        template_variables: Dict[str, Any],
        metadata: Dict[str, Any]
    ) -> Notification:
        """Schedule notification for after quiet hours end."""
        now = datetime.utcnow()
        
        # Calculate when quiet hours end
        end_time = preferences.quiet_hours_end
        scheduled_time = datetime.combine(now.date(), end_time)
        
        if scheduled_time <= now:
            # Quiet hours end tomorrow
            scheduled_time += timedelta(days=1)
        
        logger.info(
            f"Scheduling notification for user {user_id} after quiet hours at {scheduled_time}"
        )
        
        return self.send_notification(
            recipient_user_id=user_id,
            template_code=template_code,
            template_variables=template_variables,
            scheduled_at=scheduled_time,
            metadata=metadata,
            auto_route=False
        )

    def _format_notification(self, notification: Notification) -> Dict[str, Any]:
        """Format notification for API response."""
        return {
            'id': str(notification.id),
            'type': notification.notification_type.value,
            'subject': notification.subject,
            'message': notification.message_body,
            'priority': notification.priority.value,
            'status': notification.status.value,
            'read_at': notification.read_at.isoformat() if notification.read_at else None,
            'created_at': notification.created_at.isoformat(),
            'metadata': notification.metadata
        }
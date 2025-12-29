"""
Notification dispatcher service for multi-channel notifications.
"""

from typing import Optional, Dict, Any, List
from uuid import UUID
from datetime import datetime
from enum import Enum

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services.base.base_service import BaseService
from app.services.base.service_result import ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.notification.notification_repository import NotificationRepository
from app.repositories.notification.notification_queue_repository import NotificationQueueRepository
from app.schemas.notification.notification_base import NotificationCreate
from app.schemas.notification.notification_response import NotificationResponse


class NotificationPriority(str, Enum):
    """Notification priority levels."""
    
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationChannel(str, Enum):
    """Notification delivery channels."""
    
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class NotificationDispatcher(BaseService[object, NotificationRepository]):
    """
    Enqueue and manage notifications across multiple channels with:
    - Multi-channel support (email, SMS, push, in-app)
    - Priority-based queuing
    - Batch notifications
    - Template support
    - Delivery tracking
    - Retry mechanisms
    """

    def __init__(
        self,
        notification_repo: NotificationRepository,
        queue_repo: NotificationQueueRepository,
        db_session: Session,
        default_priority: NotificationPriority = NotificationPriority.NORMAL,
    ):
        """
        Initialize notification dispatcher.
        
        Args:
            notification_repo: Notification repository instance
            queue_repo: Notification queue repository instance
            db_session: SQLAlchemy database session
            default_priority: Default notification priority
        """
        super().__init__(notification_repo, db_session)
        self.notification_repo = notification_repo
        self.queue_repo = queue_repo
        self.default_priority = default_priority
        self._logger = get_logger(self.__class__.__name__)

    # -------------------------------------------------------------------------
    # Notification Dispatching
    # -------------------------------------------------------------------------

    def send(
        self,
        request: NotificationCreate,
        enqueue_only: bool = True,
        immediate: bool = False,
    ) -> ServiceResult[NotificationResponse]:
        """
        Send a notification.
        
        Args:
            request: Notification creation request
            enqueue_only: If True, only queue (don't send immediately)
            immediate: If True, attempt immediate delivery
            
        Returns:
            ServiceResult containing notification response or error
        """
        try:
            # Create notification record
            notif = self.notification_repo.create_notification(request)
            
            # Queue for processing
            if enqueue_only:
                priority = getattr(request, 'priority', self.default_priority)
                self.queue_repo.enqueue_notification(
                    notif.id,
                    notif.notification_type,
                    priority
                )
                
                self._logger.info(
                    f"Notification queued: {notif.notification_type} to {notif.recipient_id}",
                    extra={
                        "notification_id": str(notif.id),
                        "type": notif.notification_type,
                        "recipient_id": str(notif.recipient_id),
                        "priority": priority,
                    }
                )
            
            # Immediate delivery if requested
            if immediate and not enqueue_only:
                # This would integrate with actual delivery service
                # For now, just log
                self._logger.info(
                    f"Immediate delivery requested for notification {notif.id}"
                )
            
            self._commit()
            
            res = self.notification_repo.to_response(notif.id)
            return ServiceResult.success(
                res,
                message="Notification queued successfully" if enqueue_only else "Notification sent"
            )
            
        except Exception as e:
            self._rollback()
            return self._handle_exception(e, "send notification")

    def send_bulk(
        self,
        requests: List[NotificationCreate],
        batch_size: int = 100,
    ) -> ServiceResult[List[NotificationResponse]]:
        """
        Send multiple notifications in bulk.
        
        Args:
            requests: List of notification requests
            batch_size: Number of notifications to process per batch
            
        Returns:
            ServiceResult containing list of notification responses
        """
        try:
            responses = []
            failed = []
            
            # Process in batches
            for i in range(0, len(requests), batch_size):
                batch = requests[i:i + batch_size]
                
                with self.transaction():
                    for request in batch:
                        try:
                            notif = self.notification_repo.create_notification(request)
                            priority = getattr(request, 'priority', self.default_priority)
                            
                            self.queue_repo.enqueue_notification(
                                notif.id,
                                notif.notification_type,
                                priority
                            )
                            
                            res = self.notification_repo.to_response(notif.id)
                            responses.append(res)
                            
                        except Exception as e:
                            self._logger.error(
                                f"Failed to queue notification in bulk: {e}",
                                exc_info=True
                            )
                            failed.append({
                                "request": request,
                                "error": str(e)
                            })
            
            self._logger.info(
                f"Bulk notification dispatch: {len(responses)} successful, {len(failed)} failed",
                extra={
                    "total": len(requests),
                    "successful": len(responses),
                    "failed": len(failed),
                }
            )
            
            return ServiceResult.success(
                responses,
                message=f"Bulk dispatch complete: {len(responses)}/{len(requests)} queued",
                metadata={
                    "total": len(requests),
                    "successful": len(responses),
                    "failed": len(failed),
                    "failures": failed if failed else None,
                }
            )
            
        except Exception as e:
            self._rollback()
            return self._handle_exception(e, "send bulk notifications")

    def send_to_multiple_recipients(
        self,
        recipient_ids: List[UUID],
        notification_type: str,
        title: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        channels: Optional[List[NotificationChannel]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> ServiceResult[List[NotificationResponse]]:
        """
        Send the same notification to multiple recipients.
        
        Args:
            recipient_ids: List of recipient user IDs
            notification_type: Type of notification
            title: Notification title
            message: Notification message
            data: Additional notification data
            channels: Delivery channels
            priority: Notification priority
            
        Returns:
            ServiceResult containing list of notification responses
        """
        try:
            requests = []
            
            for recipient_id in recipient_ids:
                request = NotificationCreate(
                    recipient_id=recipient_id,
                    notification_type=notification_type,
                    title=title,
                    message=message,
                    data=data or {},
                    priority=priority,
                    channels=channels or [NotificationChannel.IN_APP],
                )
                requests.append(request)
            
            return self.send_bulk(requests)
            
        except Exception as e:
            return self._handle_exception(e, "send to multiple recipients")

    # -------------------------------------------------------------------------
    # Template-based Notifications
    # -------------------------------------------------------------------------

    def send_from_template(
        self,
        template_id: str,
        recipient_id: UUID,
        context: Dict[str, Any],
        channels: Optional[List[NotificationChannel]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
    ) -> ServiceResult[NotificationResponse]:
        """
        Send notification from template.
        
        Args:
            template_id: Notification template identifier
            recipient_id: Recipient user ID
            context: Template context variables
            channels: Delivery channels
            priority: Notification priority
            
        Returns:
            ServiceResult containing notification response
        """
        try:
            # This would integrate with template service
            # For now, create basic notification
            
            request = NotificationCreate(
                recipient_id=recipient_id,
                notification_type=template_id,
                title=f"Notification from template {template_id}",
                message="Template rendered content",  # Would be rendered from template
                data={
                    "template_id": template_id,
                    "context": context,
                },
                priority=priority,
                channels=channels or [NotificationChannel.IN_APP],
            )
            
            return self.send(request)
            
        except Exception as e:
            return self._handle_exception(e, "send from template")

    # -------------------------------------------------------------------------
    # Notification Management
    # -------------------------------------------------------------------------

    def get_user_notifications(
        self,
        user_id: UUID,
        unread_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> ServiceResult[List[NotificationResponse]]:
        """
        Get notifications for a user.
        
        Args:
            user_id: User ID
            unread_only: Return only unread notifications
            limit: Maximum number of notifications
            offset: Pagination offset
            
        Returns:
            ServiceResult containing list of notifications
        """
        try:
            notifications = self.notification_repo.get_user_notifications(
                user_id,
                unread_only=unread_only,
                limit=limit,
                offset=offset
            )
            
            responses = [
                self.notification_repo.to_response(n.id)
                for n in notifications
            ]
            
            return ServiceResult.success(
                responses,
                metadata={
                    "user_id": str(user_id),
                    "count": len(responses),
                    "unread_only": unread_only,
                }
            )
            
        except Exception as e:
            return self._handle_exception(e, "get user notifications", user_id)

    def mark_as_read(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Mark notification as read.
        
        Args:
            notification_id: Notification ID
            user_id: User ID (for verification)
            
        Returns:
            ServiceResult indicating success
        """
        try:
            success = self.notification_repo.mark_as_read(notification_id, user_id)
            
            if not success:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Notification not found or access denied",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            self._commit()
            
            return ServiceResult.success(True, message="Notification marked as read")
            
        except Exception as e:
            self._rollback()
            return self._handle_exception(e, "mark notification as read", notification_id)

    def mark_all_as_read(
        self,
        user_id: UUID,
    ) -> ServiceResult[int]:
        """
        Mark all notifications as read for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            ServiceResult containing count of marked notifications
        """
        try:
            count = self.notification_repo.mark_all_as_read(user_id)
            self._commit()
            
            self._logger.info(
                f"Marked {count} notifications as read for user {user_id}",
                extra={"user_id": str(user_id), "count": count}
            )
            
            return ServiceResult.success(
                count,
                message=f"{count} notifications marked as read"
            )
            
        except Exception as e:
            self._rollback()
            return self._handle_exception(e, "mark all as read", user_id)

    def delete_notification(
        self,
        notification_id: UUID,
        user_id: UUID,
    ) -> ServiceResult[bool]:
        """
        Delete a notification.
        
        Args:
            notification_id: Notification ID
            user_id: User ID (for verification)
            
        Returns:
            ServiceResult indicating success
        """
        try:
            success = self.notification_repo.delete_notification(notification_id, user_id)
            
            if not success:
                return ServiceResult.failure(
                    ServiceError(
                        code=ErrorCode.NOT_FOUND,
                        message="Notification not found or access denied",
                        severity=ErrorSeverity.WARNING,
                    )
                )
            
            self._commit()
            
            return ServiceResult.success(True, message="Notification deleted")
            
        except Exception as e:
            self._rollback()
            return self._handle_exception(e, "delete notification", notification_id)

    # -------------------------------------------------------------------------
    # Statistics & Monitoring
    # -------------------------------------------------------------------------

    def get_notification_stats(
        self,
        user_id: Optional[UUID] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get notification statistics.
        
        Args:
            user_id: Optional user ID to filter stats
            
        Returns:
            ServiceResult containing statistics dictionary
        """
        try:
            stats = self.notification_repo.get_stats(user_id)
            
            return ServiceResult.success(
                stats,
                metadata={"user_id": str(user_id) if user_id else None}
            )
            
        except Exception as e:
            return self._handle_exception(e, "get notification stats")
# app/services/notification/in_app_notification_service.py
"""
Enhanced In-App Notification Service

Covers:
- Creating in-app notifications with validation
- Listing notifications with pagination and filtering
- Marking notifications as read/unread with batch operations
- Getting summaries/unread counts with caching
- Real-time notification support
"""

from __future__ import annotations

import logging
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.notification import NotificationRepository
from app.schemas.notification import (
    NotificationCreate,
    NotificationUpdate,
    NotificationResponse,
    NotificationDetail,
    NotificationList,
    NotificationListItem,
    UnreadCount,
    MarkAsRead,
    BulkMarkAsRead,
)
from app.core1.exceptions import ValidationException, DatabaseException
from app.core1.logging import LoggingContext

logger = logging.getLogger(__name__)


class InAppNotificationService:
    """
    Enhanced high-level in-app notification service.

    Enhanced with:
    - Comprehensive validation
    - Performance optimizations
    - Batch operations
    - Real-time support hooks
    - Enhanced error handling
    """

    def __init__(self, notification_repo: NotificationRepository) -> None:
        self.notification_repo = notification_repo
        self._default_page_size = 20
        self._max_page_size = 100
        self._max_bulk_mark_size = 500

    def _validate_notification_create(self, request: NotificationCreate) -> None:
        """Validate notification creation request."""
        if not request.title or len(request.title.strip()) == 0:
            raise ValidationException("Notification title is required")
        
        if len(request.title) > 255:
            raise ValidationException("Notification title too long (max 255 characters)")
        
        if request.content and len(request.content) > 2000:
            raise ValidationException("Notification content too long (max 2000 characters)")
        
        if not request.user_id:
            raise ValidationException("User ID is required")
        
        if request.priority and request.priority not in ["low", "normal", "high", "urgent"]:
            raise ValidationException("Invalid priority. Must be: low, normal, high, urgent")

    def _validate_notification_update(self, request: NotificationUpdate) -> None:
        """Validate notification update request."""
        if request.title is not None and len(request.title.strip()) == 0:
            raise ValidationException("Notification title cannot be empty")
        
        if request.title and len(request.title) > 255:
            raise ValidationException("Notification title too long (max 255 characters)")
        
        if request.content and len(request.content) > 2000:
            raise ValidationException("Notification content too long (max 2000 characters)")
        
        if request.priority and request.priority not in ["low", "normal", "high", "urgent"]:
            raise ValidationException("Invalid priority. Must be: low, normal, high, urgent")

    def _validate_pagination(self, page: int, page_size: int) -> tuple[int, int]:
        """Validate and normalize pagination parameters."""
        if page < 1:
            page = 1
        
        if page_size < 1:
            page_size = self._default_page_size
        elif page_size > self._max_page_size:
            page_size = self._max_page_size
        
        return page, page_size

    # -------------------------------------------------------------------------
    # Creation / update with enhanced validation
    # -------------------------------------------------------------------------

    def create_notification(
        self,
        db: Session,
        request: NotificationCreate,
        send_realtime: bool = True,
    ) -> NotificationResponse:
        """
        Create a notification with enhanced validation and optional real-time delivery.

        Enhanced with:
        - Input validation
        - Real-time delivery hooks
        - Performance monitoring
        - Transaction safety

        Args:
            db: Database session
            request: Notification creation data
            send_realtime: Whether to trigger real-time delivery

        Returns:
            NotificationResponse: Created notification

        Raises:
            ValidationException: For invalid input data
            DatabaseException: For database operation failures
        """
        self._validate_notification_create(request)

        with LoggingContext(
            channel="notification_create",
            user_id=str(request.user_id),
            priority=request.priority
        ):
            try:
                logger.info(
                    f"Creating notification for user {request.user_id}, "
                    f"title: {request.title[:50]}{'...' if len(request.title) > 50 else ''}"
                )
                
                obj = self.notification_repo.create_notification(
                    db, data=request.model_dump(exclude_none=True)
                )
                
                notification = NotificationResponse.model_validate(obj)
                
                # Hook for real-time delivery (WebSocket, SSE, etc.)
                if send_realtime:
                    self._send_realtime_notification(notification)
                
                logger.info(f"Notification created successfully: {notification.id}")
                return notification
                
            except SQLAlchemyError as e:
                logger.error(f"Database error creating notification: {str(e)}")
                raise DatabaseException("Failed to create notification") from e
            except Exception as e:
                logger.error(f"Unexpected error creating notification: {str(e)}")
                raise

    def update_notification(
        self,
        db: Session,
        notification_id: UUID,
        request: NotificationUpdate,
    ) -> NotificationResponse:
        """
        Update a notification with enhanced validation.

        Enhanced with:
        - Input validation
        - Existence checking
        - Performance optimization

        Args:
            db: Database session
            notification_id: Notification identifier
            request: Update data

        Returns:
            NotificationResponse: Updated notification

        Raises:
            ValidationException: For invalid input or not found
            DatabaseException: For database operation failures
        """
        if not notification_id:
            raise ValidationException("Notification ID is required")
        
        self._validate_notification_update(request)

        with LoggingContext(channel="notification_update", notification_id=str(notification_id)):
            try:
                logger.debug(f"Updating notification {notification_id}")
                
                notif = self.notification_repo.get_by_id(db, notification_id)
                if not notif:
                    raise ValidationException("Notification not found")

                updated = self.notification_repo.update_notification(
                    db, notif, data=request.model_dump(exclude_none=True)
                )
                
                response = NotificationResponse.model_validate(updated)
                logger.debug(f"Notification updated successfully")
                
                return response
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error updating notification: {str(e)}")
                raise DatabaseException("Failed to update notification") from e
            except Exception as e:
                logger.error(f"Unexpected error updating notification: {str(e)}")
                raise

    # -------------------------------------------------------------------------
    # Enhanced listing with filtering
    # -------------------------------------------------------------------------

    def list_notifications_for_user(
        self,
        db: Session,
        user_id: UUID,
        page: int = 1,
        page_size: int = 20,
        priority_filter: Optional[str] = None,
        read_status: Optional[bool] = None,
        category_filter: Optional[str] = None,
        date_from: Optional[datetime] = None,
        date_to: Optional[datetime] = None,
    ) -> NotificationList:
        """
        List notifications with enhanced filtering and pagination.

        Enhanced with:
        - Advanced filtering options
        - Validation and normalization
        - Performance optimization

        Args:
            db: Database session
            user_id: User identifier
            page: Page number (1-based)
            page_size: Number of items per page
            priority_filter: Filter by priority
            read_status: Filter by read status (True=read, False=unread, None=all)
            category_filter: Filter by category
            date_from: Filter notifications from this date
            date_to: Filter notifications to this date

        Returns:
            NotificationList: Paginated notification list

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if not user_id:
            raise ValidationException("User ID is required")
        
        page, page_size = self._validate_pagination(page, page_size)
        
        if priority_filter and priority_filter not in ["low", "normal", "high", "urgent"]:
            raise ValidationException("Invalid priority filter")

        filters = {
            "priority": priority_filter,
            "read_status": read_status,
            "category": category_filter,
            "date_from": date_from,
            "date_to": date_to,
        }

        with LoggingContext(
            channel="notification_list",
            user_id=str(user_id),
            page=page,
            filters=str({k: v for k, v in filters.items() if v is not None})
        ):
            try:
                logger.debug(
                    f"Listing notifications for user {user_id}, "
                    f"page {page}, size {page_size}"
                )
                
                result = self.notification_repo.get_notifications_for_user(
                    db=db,
                    user_id=user_id,
                    page=page,
                    page_size=page_size,
                    filters=filters,
                )
                
                items = [NotificationListItem.model_validate(o) for o in result["items"]]
                
                notification_list = NotificationList(
                    user_id=user_id,
                    total_notifications=result["total"],
                    unread_count=result["unread"],
                    notifications=items,
                )
                
                logger.debug(
                    f"Listed {len(items)} notifications, "
                    f"total: {result['total']}, unread: {result['unread']}"
                )
                
                return notification_list
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error listing notifications: {str(e)}")
                raise DatabaseException("Failed to retrieve notifications") from e
            except Exception as e:
                logger.error(f"Unexpected error listing notifications: {str(e)}")
                raise

    def get_notification(
        self,
        db: Session,
        notification_id: UUID,
        user_id: Optional[UUID] = None,
        mark_as_read: bool = False,
    ) -> NotificationDetail:
        """
        Get notification details with optional auto-read marking.

        Enhanced with:
        - Auto-read marking option
        - Access validation
        - Performance optimization

        Args:
            db: Database session
            notification_id: Notification identifier
            user_id: User identifier for access validation
            mark_as_read: Whether to automatically mark as read

        Returns:
            NotificationDetail: Detailed notification

        Raises:
            ValidationException: For invalid ID or access denied
            DatabaseException: For database operation failures
        """
        if not notification_id:
            raise ValidationException("Notification ID is required")

        with LoggingContext(
            channel="notification_get",
            notification_id=str(notification_id),
            user_id=str(user_id) if user_id else None
        ):
            try:
                logger.debug(f"Retrieving notification {notification_id}")
                
                obj = self.notification_repo.get_full_notification(
                    db, notification_id, user_id
                )
                if not obj:
                    raise ValidationException("Notification not found")
                
                detail = NotificationDetail.model_validate(obj)
                
                # Auto-mark as read if requested and not already read
                if mark_as_read and user_id and not detail.read_at:
                    self.mark_as_read(
                        db=db,
                        user_id=user_id,
                        request=MarkAsRead(
                            notification_id=notification_id,
                            read_at=datetime.utcnow()
                        )
                    )
                    # Update the detail object
                    detail.read_at = datetime.utcnow()
                
                logger.debug("Notification retrieved successfully")
                return detail
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error retrieving notification: {str(e)}")
                raise DatabaseException("Failed to retrieve notification") from e
            except Exception as e:
                logger.error(f"Unexpected error retrieving notification: {str(e)}")
                raise

    # -------------------------------------------------------------------------
    # Enhanced read/unread operations
    # -------------------------------------------------------------------------

    def mark_as_read(
        self,
        db: Session,
        user_id: UUID,
        request: MarkAsRead,
    ) -> None:
        """
        Mark a single notification as read with validation.

        Enhanced with:
        - Input validation
        - User access validation
        - Performance optimization

        Args:
            db: Database session
            user_id: User identifier
            request: Mark as read request

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if not user_id:
            raise ValidationException("User ID is required")
        
        if not request.notification_id:
            raise ValidationException("Notification ID is required")

        with LoggingContext(
            channel="notification_read",
            user_id=str(user_id),
            notification_id=str(request.notification_id)
        ):
            try:
                logger.debug(
                    f"Marking notification {request.notification_id} as read "
                    f"for user {user_id}"
                )
                
                self.notification_repo.mark_as_read(
                    db=db,
                    notification_id=request.notification_id,
                    user_id=user_id,
                    read_at=request.read_at or datetime.utcnow(),
                )
                
                logger.debug("Notification marked as read successfully")
                
            except SQLAlchemyError as e:
                logger.error(f"Database error marking notification as read: {str(e)}")
                raise DatabaseException("Failed to mark notification as read") from e
            except Exception as e:
                logger.error(f"Unexpected error marking notification as read: {str(e)}")
                raise

    def mark_bulk_as_read(
        self,
        db: Session,
        user_id: UUID,
        request: BulkMarkAsRead,
    ) -> int:
        """
        Mark multiple notifications as read with enhanced batch processing.

        Enhanced with:
        - Batch size validation
        - Progress tracking
        - Performance optimization

        Args:
            db: Database session
            user_id: User identifier
            request: Bulk mark as read request

        Returns:
            int: Number of notifications marked as read

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if not user_id:
            raise ValidationException("User ID is required")
        
        if not request.notification_ids:
            raise ValidationException("Notification IDs list cannot be empty")
        
        if len(request.notification_ids) > self._max_bulk_mark_size:
            raise ValidationException(
                f"Cannot mark more than {self._max_bulk_mark_size} notifications at once"
            )

        with LoggingContext(
            channel="notification_bulk_read",
            user_id=str(user_id),
            count=len(request.notification_ids)
        ):
            try:
                logger.info(
                    f"Bulk marking {len(request.notification_ids)} notifications "
                    f"as read for user {user_id}"
                )
                
                marked_count = self.notification_repo.mark_bulk_as_read(
                    db=db,
                    notification_ids=request.notification_ids,
                    user_id=user_id,
                    read_at=request.read_at or datetime.utcnow(),
                )
                
                logger.info(f"Successfully marked {marked_count} notifications as read")
                return marked_count
                
            except SQLAlchemyError as e:
                logger.error(f"Database error bulk marking as read: {str(e)}")
                raise DatabaseException("Failed to bulk mark notifications as read") from e
            except Exception as e:
                logger.error(f"Unexpected error bulk marking as read: {str(e)}")
                raise

    def mark_all_as_read(
        self,
        db: Session,
        user_id: UUID,
        category_filter: Optional[str] = None,
    ) -> int:
        """
        Mark all unread notifications as read for a user.

        Args:
            db: Database session
            user_id: User identifier
            category_filter: Optional category filter

        Returns:
            int: Number of notifications marked as read

        Raises:
            ValidationException: For invalid user ID
            DatabaseException: For database operation failures
        """
        if not user_id:
            raise ValidationException("User ID is required")

        with LoggingContext(
            channel="notification_mark_all_read",
            user_id=str(user_id),
            category=category_filter
        ):
            try:
                logger.info(f"Marking all unread notifications as read for user {user_id}")
                
                marked_count = self.notification_repo.mark_all_as_read(
                    db=db,
                    user_id=user_id,
                    category_filter=category_filter,
                    read_at=datetime.utcnow(),
                )
                
                logger.info(f"Marked {marked_count} notifications as read")
                return marked_count
                
            except SQLAlchemyError as e:
                logger.error(f"Database error marking all as read: {str(e)}")
                raise DatabaseException("Failed to mark all notifications as read") from e
            except Exception as e:
                logger.error(f"Unexpected error marking all as read: {str(e)}")
                raise

    def get_unread_count(
        self,
        db: Session,
        user_id: UUID,
        category_filter: Optional[str] = None,
    ) -> UnreadCount:
        """
        Get unread notification count with optional category filtering.

        Enhanced with:
        - Category filtering
        - Performance optimization
        - Caching support

        Args:
            db: Database session
            user_id: User identifier
            category_filter: Optional category filter

        Returns:
            UnreadCount: Unread counts by category

        Raises:
            ValidationException: For invalid user ID
            DatabaseException: For database operation failures
        """
        if not user_id:
            raise ValidationException("User ID is required")

        with LoggingContext(
            channel="notification_unread_count",
            user_id=str(user_id),
            category=category_filter
        ):
            try:
                logger.debug(f"Getting unread count for user {user_id}")
                
                counts = self.notification_repo.get_unread_counts(
                    db, user_id, category_filter
                )
                
                unread_count = UnreadCount.model_validate(counts)
                logger.debug(f"Unread count: {unread_count.total}")
                
                return unread_count
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error getting unread count: {str(e)}")
                raise DatabaseException("Failed to get unread count") from e
            except Exception as e:
                logger.error(f"Unexpected error getting unread count: {str(e)}")
                raise

    # -------------------------------------------------------------------------
    # Additional utility methods
    # -------------------------------------------------------------------------

    def delete_notification(
        self,
        db: Session,
        notification_id: UUID,
        user_id: UUID,
        soft_delete: bool = True,
    ) -> bool:
        """
        Delete a notification (soft delete by default).

        Args:
            db: Database session
            notification_id: Notification identifier
            user_id: User identifier for access validation
            soft_delete: Whether to soft delete (default) or hard delete

        Returns:
            bool: True if deleted successfully

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if not notification_id or not user_id:
            raise ValidationException("Notification ID and User ID are required")

        with LoggingContext(
            channel="notification_delete",
            notification_id=str(notification_id),
            user_id=str(user_id)
        ):
            try:
                logger.info(f"Deleting notification {notification_id} for user {user_id}")
                
                success = self.notification_repo.delete_notification(
                    db=db,
                    notification_id=notification_id,
                    user_id=user_id,
                    soft_delete=soft_delete,
                )
                
                if success:
                    logger.info("Notification deleted successfully")
                else:
                    logger.warning("Notification not found or access denied")
                
                return success
                
            except SQLAlchemyError as e:
                logger.error(f"Database error deleting notification: {str(e)}")
                raise DatabaseException("Failed to delete notification") from e
            except Exception as e:
                logger.error(f"Unexpected error deleting notification: {str(e)}")
                raise

    def cleanup_old_notifications(
        self,
        db: Session,
        days_old: int = 30,
        batch_size: int = 1000,
    ) -> int:
        """
        Clean up old read notifications to maintain performance.

        Args:
            db: Database session
            days_old: Delete notifications older than this many days
            batch_size: Process in batches of this size

        Returns:
            int: Number of notifications cleaned up

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if days_old < 1:
            raise ValidationException("days_old must be at least 1")

        cutoff_date = datetime.utcnow() - timedelta(days=days_old)

        with LoggingContext(
            channel="notification_cleanup",
            days_old=days_old,
            cutoff_date=cutoff_date.isoformat()
        ):
            try:
                logger.info(f"Cleaning up notifications older than {days_old} days")
                
                cleaned_count = self.notification_repo.cleanup_old_notifications(
                    db=db,
                    cutoff_date=cutoff_date,
                    batch_size=batch_size,
                )
                
                logger.info(f"Cleaned up {cleaned_count} old notifications")
                return cleaned_count
                
            except SQLAlchemyError as e:
                logger.error(f"Database error during cleanup: {str(e)}")
                raise DatabaseException("Failed to cleanup old notifications") from e
            except Exception as e:
                logger.error(f"Unexpected error during cleanup: {str(e)}")
                raise

    def _send_realtime_notification(self, notification: NotificationResponse) -> None:
        """
        Hook for sending real-time notifications via WebSocket/SSE.

        This is a placeholder for integration with real-time systems.

        Args:
            notification: Notification to send in real-time
        """
        try:
            # TODO: Integrate with WebSocket/SSE system
            # Example: websocket_manager.send_to_user(notification.user_id, notification)
            logger.debug(f"Real-time notification hook called for {notification.id}")
        except Exception as e:
            # Don't fail the main operation if real-time delivery fails
            logger.warning(f"Failed to send real-time notification: {str(e)}")
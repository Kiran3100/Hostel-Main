"""
Broadcast (mass messaging) service with enhanced error handling and performance.
"""

from typing import Optional, Dict, Any, List, Tuple
from uuid import UUID
from datetime import datetime
import logging
from contextlib import contextmanager

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.services.base import BaseService, ServiceResult, ServiceError, ErrorCode, ErrorSeverity
from app.repositories.notification import (
    NotificationRepository,
    NotificationQueueRepository,
    NotificationRoutingRepository,
    NotificationPreferencesRepository,
)
from app.models.notification.notification import Notification as NotificationModel
from app.schemas.notification.notification_base import NotificationCreate
from app.schemas.notification.notification_response import NotificationResponse


logger = logging.getLogger(__name__)


class BroadcastService(BaseService[NotificationModel, NotificationRepository]):
    """
    Mass messaging service with intelligent routing, preference management, and batching.
    
    Features:
    - Batch processing with configurable commit intervals
    - User preference filtering
    - Automatic routing rule application
    - Comprehensive error tracking
    - Transaction safety with rollback on critical failures
    """

    # Constants for configuration
    DEFAULT_BATCH_SIZE = 1000
    MAX_BATCH_SIZE = 10000
    MIN_BATCH_SIZE = 10

    def __init__(
        self,
        repository: NotificationRepository,
        queue_repo: NotificationQueueRepository,
        routing_repo: NotificationRoutingRepository,
        preferences_repo: NotificationPreferencesRepository,
        db_session: Session,
    ):
        super().__init__(repository, db_session)
        self.queue_repo = queue_repo
        self.routing_repo = routing_repo
        self.preferences_repo = preferences_repo
        self._logger = logger

    def broadcast(
        self,
        requests: List[NotificationCreate],
        use_routing: bool = True,
        respect_preferences: bool = True,
        batch_size: int = DEFAULT_BATCH_SIZE,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Broadcast multiple notifications with routing rules and user preferences.
        
        Args:
            requests: List of notification creation requests
            use_routing: Apply routing rules to determine delivery channels
            respect_preferences: Filter out notifications based on user preferences
            batch_size: Number of notifications to process before committing
            
        Returns:
            ServiceResult containing broadcast statistics and error details
        """
        # Validate inputs
        if not requests:
            return ServiceResult.success(
                {"total": 0, "success": 0, "failed": 0, "skipped": 0, "errors": []},
                message="No notifications to broadcast",
            )

        # Validate and normalize batch size
        batch_size = self._validate_batch_size(batch_size)
        
        self._logger.info(
            f"Starting broadcast of {len(requests)} notifications "
            f"(routing={use_routing}, preferences={respect_preferences}, batch_size={batch_size})"
        )

        try:
            stats = self._process_broadcast(
                requests=requests,
                use_routing=use_routing,
                respect_preferences=respect_preferences,
                batch_size=batch_size,
            )
            
            self.db.commit()
            
            self._logger.info(
                f"Broadcast completed: {stats['success']} succeeded, "
                f"{stats['failed']} failed, {stats['skipped']} skipped"
            )
            
            return ServiceResult.success(stats, message="Broadcast completed")
            
        except SQLAlchemyError as e:
            self.db.rollback()
            self._logger.error(f"Database error during broadcast: {str(e)}", exc_info=True)
            return self._handle_exception(e, "broadcast notifications")
        except Exception as e:
            self.db.rollback()
            self._logger.error(f"Unexpected error during broadcast: {str(e)}", exc_info=True)
            return self._handle_exception(e, "broadcast notifications")

    def _process_broadcast(
        self,
        requests: List[NotificationCreate],
        use_routing: bool,
        respect_preferences: bool,
        batch_size: int,
    ) -> Dict[str, Any]:
        """
        Process broadcast requests with batching and error tracking.
        
        Returns:
            Dictionary containing processing statistics
        """
        success_count = 0
        failed_count = 0
        skipped_count = 0
        errors: List[Dict[str, Any]] = []
        processed_count = 0

        for idx, request in enumerate(requests, start=1):
            try:
                # Check user preferences
                if respect_preferences and request.user_id:
                    if not self._check_user_preferences(request):
                        skipped_count += 1
                        continue

                # Create and queue notification
                notification = self._create_and_queue_notification(
                    request=request,
                    use_routing=use_routing,
                )
                
                success_count += 1
                processed_count += 1

            except Exception as inner_e:
                failed_count += 1
                processed_count += 1
                error_detail = self._capture_error_detail(request, inner_e, idx)
                errors.append(error_detail)
                
                self._logger.warning(
                    f"Failed to process notification {idx}/{len(requests)}: {str(inner_e)}"
                )

            # Batch commit for performance
            if processed_count % batch_size == 0:
                try:
                    self.db.commit()
                    self._logger.debug(f"Batch commit at {processed_count}/{len(requests)}")
                except SQLAlchemyError as commit_error:
                    self._logger.error(f"Batch commit failed: {str(commit_error)}")
                    self.db.rollback()
                    raise

        return {
            "total": len(requests),
            "success": success_count,
            "failed": failed_count,
            "skipped": skipped_count,
            "errors": errors,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _check_user_preferences(self, request: NotificationCreate) -> bool:
        """
        Check if notification is enabled for user based on preferences.
        
        Args:
            request: Notification creation request
            
        Returns:
            True if notification should be sent, False otherwise
        """
        try:
            user_uuid = UUID(request.user_id) if isinstance(request.user_id, str) else request.user_id
            return self.preferences_repo.is_enabled_for_user(
                user_uuid,
                request.notification_type
            )
        except (ValueError, TypeError) as e:
            self._logger.warning(f"Invalid user_id format: {request.user_id}, error: {str(e)}")
            return False

    def _create_and_queue_notification(
        self,
        request: NotificationCreate,
        use_routing: bool,
    ) -> NotificationModel:
        """
        Create notification and add to appropriate queue.
        
        Args:
            request: Notification creation request
            use_routing: Whether to apply routing rules
            
        Returns:
            Created notification model
        """
        # Create notification
        notification = self.repository.create_notification(request)

        # Queue with or without routing
        if use_routing:
            route = self.routing_repo.compute_route(
                notification.id,
                notification.category,
                notification.priority
            )
            self.queue_repo.enqueue_routed(notification.id, route)
        else:
            self.queue_repo.enqueue_notification(
                notification.id,
                notification.notification_type,
                notification.priority
            )

        return notification

    def _capture_error_detail(
        self,
        request: NotificationCreate,
        error: Exception,
        index: int,
    ) -> Dict[str, Any]:
        """
        Capture detailed error information for failed notification.
        
        Args:
            request: Failed notification request
            error: Exception that occurred
            index: Position in broadcast list
            
        Returns:
            Dictionary containing error details
        """
        return {
            "index": index,
            "user_id": request.user_id,
            "notification_type": request.notification_type,
            "error": str(error),
            "error_type": type(error).__name__,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def _validate_batch_size(self, batch_size: int) -> int:
        """
        Validate and normalize batch size parameter.
        
        Args:
            batch_size: Requested batch size
            
        Returns:
            Validated batch size within acceptable range
        """
        if batch_size < self.MIN_BATCH_SIZE:
            self._logger.warning(
                f"Batch size {batch_size} below minimum, using {self.MIN_BATCH_SIZE}"
            )
            return self.MIN_BATCH_SIZE
        
        if batch_size > self.MAX_BATCH_SIZE:
            self._logger.warning(
                f"Batch size {batch_size} above maximum, using {self.MAX_BATCH_SIZE}"
            )
            return self.MAX_BATCH_SIZE
        
        return batch_size

    def get_broadcast_status(
        self,
        broadcast_id: Optional[UUID] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
    ) -> ServiceResult[Dict[str, Any]]:
        """
        Get status and statistics for broadcast operations.
        
        Args:
            broadcast_id: Specific broadcast identifier (if tracked)
            start_time: Filter broadcasts after this time
            end_time: Filter broadcasts before this time
            
        Returns:
            ServiceResult containing broadcast status information
        """
        try:
            # This would require a broadcast tracking table
            # Placeholder for future implementation
            status = {
                "message": "Broadcast status tracking not yet implemented",
                "broadcast_id": str(broadcast_id) if broadcast_id else None,
            }
            return ServiceResult.success(status)
        except Exception as e:
            return self._handle_exception(e, "get broadcast status")
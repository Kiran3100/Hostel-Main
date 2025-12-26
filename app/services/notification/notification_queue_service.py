# app/services/notification/notification_queue_service.py
"""
Enhanced Notification Queue Service

Manages the notification queue with improved:
- Performance through optimized queries
- Better error handling and retry logic
- Health monitoring and statistics
- Dead letter queue management
- Worker load balancing
"""

from __future__ import annotations

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.repositories.notification import NotificationQueueRepository
from app.schemas.notification import (
    QueueStatus,
    QueuedNotification,
    BatchProcessing,
    QueueStats,
    QueueHealth,
)
from app.core.exceptions import ValidationException, DatabaseException
from app.core.logging import LoggingContext

logger = logging.getLogger(__name__)


class NotificationQueueService:
    """
    Enhanced high-level service for managing notification queue lifecycle.

    Enhanced with:
    - Comprehensive validation
    - Performance optimizations
    - Health monitoring
    - Dead letter queue handling
    - Worker management
    """

    def __init__(self, queue_repo: NotificationQueueRepository) -> None:
        self.queue_repo = queue_repo
        self._max_retry_count = 3
        self._default_priority = "normal"
        self._valid_priorities = ["low", "normal", "high", "urgent"]
        self._max_dequeue_size = 100
        self._health_check_interval = 300  # 5 minutes

    def _validate_priority(self, priority: Optional[str]) -> str:
        """Validate and normalize priority."""
        if not priority:
            return self._default_priority
        
        if priority not in self._valid_priorities:
            raise ValidationException(
                f"Invalid priority '{priority}'. Must be one of: {', '.join(self._valid_priorities)}"
            )
        
        return priority

    def _validate_worker_id(self, worker_id: str) -> None:
        """Validate worker ID format."""
        if not worker_id or len(worker_id.strip()) == 0:
            raise ValidationException("Worker ID cannot be empty")
        
        if len(worker_id) > 100:
            raise ValidationException("Worker ID too long (max 100 characters)")

    def _validate_dequeue_params(self, max_items: int) -> int:
        """Validate and normalize dequeue parameters."""
        if max_items < 1:
            return 1
        elif max_items > self._max_dequeue_size:
            return self._max_dequeue_size
        
        return max_items

    # -------------------------------------------------------------------------
    # Enhanced queue operations
    # -------------------------------------------------------------------------

    def enqueue_notification(
        self,
        db: Session,
        notification_id: UUID,
        priority: Optional[str] = None,
        scheduled_for: Optional[datetime] = None,
        max_retries: Optional[int] = None,
    ) -> QueuedNotification:
        """
        Put a notification into the processing queue with enhanced options.

        Enhanced with:
        - Schedule for future delivery
        - Custom retry limits
        - Priority validation
        - Performance monitoring

        Args:
            db: Database session
            notification_id: Notification to queue
            priority: Queue priority (low, normal, high, urgent)
            scheduled_for: Optional future delivery time
            max_retries: Custom retry limit

        Returns:
            QueuedNotification: Queued notification details

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if not notification_id:
            raise ValidationException("Notification ID is required")
        
        validated_priority = self._validate_priority(priority)
        
        if max_retries is None:
            max_retries = self._max_retry_count
        elif max_retries < 0 or max_retries > 10:
            raise ValidationException("Max retries must be between 0 and 10")

        with LoggingContext(
            channel="queue_enqueue",
            notification_id=str(notification_id),
            priority=validated_priority
        ):
            try:
                logger.info(
                    f"Enqueuing notification {notification_id}, "
                    f"priority: {validated_priority}, "
                    f"scheduled_for: {scheduled_for}"
                )
                
                obj = self.queue_repo.enqueue(
                    db=db,
                    notification_id=notification_id,
                    priority=validated_priority,
                    scheduled_for=scheduled_for,
                    max_retries=max_retries,
                )
                
                queued = QueuedNotification.model_validate(obj)
                logger.info(f"Notification enqueued successfully: {queued.id}")
                
                return queued
                
            except SQLAlchemyError as e:
                logger.error(f"Database error enqueuing notification: {str(e)}")
                raise DatabaseException("Failed to enqueue notification") from e
            except Exception as e:
                logger.error(f"Unexpected error enqueuing notification: {str(e)}")
                raise

    def dequeue_for_worker(
        self,
        db: Session,
        worker_id: str,
        max_items: int = 10,
        priority_filter: Optional[str] = None,
        timeout_seconds: int = 30,
    ) -> List[QueuedNotification]:
        """
        Claim items from the queue for a specific worker with enhanced features.

        Enhanced with:
        - Priority filtering
        - Worker timeout handling
        - Load balancing
        - Performance optimization

        Args:
            db: Database session
            worker_id: Worker identifier
            max_items: Maximum items to dequeue
            priority_filter: Optional priority filter
            timeout_seconds: Worker timeout in seconds

        Returns:
            List[QueuedNotification]: Claimed notifications

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        self._validate_worker_id(worker_id)
        max_items = self._validate_dequeue_params(max_items)
        
        if priority_filter:
            self._validate_priority(priority_filter)

        with LoggingContext(
            channel="queue_dequeue",
            worker_id=worker_id,
            max_items=max_items,
            priority_filter=priority_filter
        ):
            try:
                logger.info(
                    f"Dequeuing up to {max_items} items for worker {worker_id}, "
                    f"priority_filter: {priority_filter}"
                )
                
                objs = self.queue_repo.dequeue_for_worker(
                    db=db,
                    worker_id=worker_id,
                    max_items=max_items,
                    priority_filter=priority_filter,
                    timeout_seconds=timeout_seconds,
                )
                
                notifications = [QueuedNotification.model_validate(o) for o in objs]
                logger.info(f"Dequeued {len(notifications)} notifications for worker {worker_id}")
                
                return notifications
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error dequeuing notifications: {str(e)}")
                raise DatabaseException("Failed to dequeue notifications") from e
            except Exception as e:
                logger.error(f"Unexpected error dequeuing notifications: {str(e)}")
                raise

    def mark_processed(
        self,
        db: Session,
        queue_id: UUID,
        processing_duration: Optional[float] = None,
        result_metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Mark a queue item as successfully processed with enhanced metadata.

        Enhanced with:
        - Processing duration tracking
        - Result metadata storage
        - Performance metrics

        Args:
            db: Database session
            queue_id: Queue item identifier
            processing_duration: Time taken to process (seconds)
            result_metadata: Additional result information

        Raises:
            ValidationException: For invalid queue ID
            DatabaseException: For database operation failures
        """
        if not queue_id:
            raise ValidationException("Queue ID is required")

        with LoggingContext(
            channel="queue_mark_processed",
            queue_id=str(queue_id),
            duration=processing_duration
        ):
            try:
                logger.info(
                    f"Marking queue item {queue_id} as processed, "
                    f"duration: {processing_duration}s"
                )
                
                self.queue_repo.mark_processed(
                    db=db,
                    queue_id=queue_id,
                    processing_duration=processing_duration,
                    result_metadata=result_metadata,
                )
                
                logger.info("Queue item marked as processed successfully")
                
            except SQLAlchemyError as e:
                logger.error(f"Database error marking as processed: {str(e)}")
                raise DatabaseException("Failed to mark queue item as processed") from e
            except Exception as e:
                logger.error(f"Unexpected error marking as processed: {str(e)}")
                raise

    def mark_failed(
        self,
        db: Session,
        queue_id: UUID,
        error_message: str,
        should_retry: bool = True,
        retry_delay_seconds: Optional[int] = None,
    ) -> bool:
        """
        Mark a queue item as failed with enhanced retry logic.

        Enhanced with:
        - Retry decision logic
        - Custom retry delays
        - Dead letter queue handling
        - Error categorization

        Args:
            db: Database session
            queue_id: Queue item identifier
            error_message: Error description
            should_retry: Whether to attempt retry
            retry_delay_seconds: Custom retry delay

        Returns:
            bool: True if item will be retried, False if moved to DLQ

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if not queue_id:
            raise ValidationException("Queue ID is required")
        
        if not error_message or len(error_message.strip()) == 0:
            raise ValidationException("Error message is required")

        with LoggingContext(
            channel="queue_mark_failed",
            queue_id=str(queue_id),
            should_retry=should_retry
        ):
            try:
                logger.warning(
                    f"Marking queue item {queue_id} as failed: {error_message[:100]}, "
                    f"will_retry: {should_retry}"
                )
                
                will_retry = self.queue_repo.mark_failed(
                    db=db,
                    queue_id=queue_id,
                    error_message=error_message,
                    should_retry=should_retry,
                    retry_delay_seconds=retry_delay_seconds,
                )
                
                if will_retry:
                    logger.info("Queue item scheduled for retry")
                else:
                    logger.info("Queue item moved to dead letter queue")
                
                return will_retry
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error marking as failed: {str(e)}")
                raise DatabaseException("Failed to mark queue item as failed") from e
            except Exception as e:
                logger.error(f"Unexpected error marking as failed: {str(e)}")
                raise

    # -------------------------------------------------------------------------
    # Enhanced monitoring and statistics
    # -------------------------------------------------------------------------

    def get_queue_status(
        self,
        db: Session,
        include_worker_info: bool = True,
    ) -> QueueStatus:
        """
        Get current queue status with enhanced details.

        Enhanced with:
        - Worker information
        - Performance metrics
        - Health indicators

        Args:
            db: Database session
            include_worker_info: Whether to include worker details

        Returns:
            QueueStatus: Current queue status

        Raises:
            DatabaseException: For database operation failures
        """
        with LoggingContext(channel="queue_status"):
            try:
                logger.debug("Retrieving queue status")
                
                data = self.queue_repo.get_queue_status(
                    db, include_worker_info=include_worker_info
                )
                
                status = QueueStatus.model_validate(data)
                logger.debug(f"Queue status: {status.pending_count} pending")
                
                return status
                
            except SQLAlchemyError as e:
                logger.error(f"Database error retrieving queue status: {str(e)}")
                raise DatabaseException("Failed to retrieve queue status") from e
            except Exception as e:
                logger.error(f"Unexpected error retrieving queue status: {str(e)}")
                raise

    def get_queue_stats(
        self,
        db: Session,
        time_range_hours: int = 24,
    ) -> QueueStats:
        """
        Get queue processing statistics with configurable time range.

        Enhanced with:
        - Configurable time ranges
        - Performance metrics
        - Trend analysis

        Args:
            db: Database session
            time_range_hours: Statistics time range in hours

        Returns:
            QueueStats: Processing statistics

        Raises:
            ValidationException: For invalid time range
            DatabaseException: For database operation failures
        """
        if time_range_hours < 1 or time_range_hours > 8760:  # 1 year max
            raise ValidationException("Time range must be between 1 and 8760 hours")

        with LoggingContext(
            channel="queue_stats",
            time_range_hours=time_range_hours
        ):
            try:
                logger.debug(f"Retrieving queue stats for {time_range_hours}h")
                
                data = self.queue_repo.get_queue_stats(
                    db, time_range_hours=time_range_hours
                )
                
                stats = QueueStats.model_validate(data)
                logger.debug(f"Queue stats: {stats.processed_count} processed")
                
                return stats
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error retrieving queue stats: {str(e)}")
                raise DatabaseException("Failed to retrieve queue statistics") from e
            except Exception as e:
                logger.error(f"Unexpected error retrieving queue stats: {str(e)}")
                raise

    def get_queue_health(
        self,
        db: Session,
    ) -> QueueHealth:
        """
        Get queue health status with comprehensive checks.

        Enhanced with:
        - Multiple health indicators
        - Performance thresholds
        - Alert conditions

        Returns:
            QueueHealth: Health status

        Raises:
            DatabaseException: For database operation failures
        """
        with LoggingContext(channel="queue_health"):
            try:
                logger.debug("Checking queue health")
                
                data = self.queue_repo.get_queue_health(db)
                
                health = QueueHealth.model_validate(data)
                logger.debug(f"Queue health: {health.overall_status}")
                
                return health
                
            except SQLAlchemyError as e:
                logger.error(f"Database error checking queue health: {str(e)}")
                raise DatabaseException("Failed to check queue health") from e
            except Exception as e:
                logger.error(f"Unexpected error checking queue health: {str(e)}")
                raise

    # -------------------------------------------------------------------------
    # Worker management
    # -------------------------------------------------------------------------

    def register_worker(
        self,
        db: Session,
        worker_id: str,
        worker_type: str,
        capabilities: List[str],
        max_concurrent: int = 5,
    ) -> Dict[str, Any]:
        """
        Register a worker with the queue system.

        Args:
            db: Database session
            worker_id: Worker identifier
            worker_type: Type of worker (email, sms, push, etc.)
            capabilities: List of capabilities (priority levels, etc.)
            max_concurrent: Maximum concurrent processing

        Returns:
            Dict[str, Any]: Worker registration result

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        self._validate_worker_id(worker_id)
        
        if not worker_type:
            raise ValidationException("Worker type is required")
        
        if max_concurrent < 1 or max_concurrent > 100:
            raise ValidationException("Max concurrent must be between 1 and 100")

        with LoggingContext(
            channel="worker_register",
            worker_id=worker_id,
            worker_type=worker_type
        ):
            try:
                logger.info(f"Registering worker {worker_id}, type: {worker_type}")
                
                result = self.queue_repo.register_worker(
                    db=db,
                    worker_id=worker_id,
                    worker_type=worker_type,
                    capabilities=capabilities,
                    max_concurrent=max_concurrent,
                )
                
                logger.info("Worker registered successfully")
                return result
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error registering worker: {str(e)}")
                raise DatabaseException("Failed to register worker") from e
            except Exception as e:
                logger.error(f"Unexpected error registering worker: {str(e)}")
                raise

    def heartbeat_worker(
        self,
        db: Session,
        worker_id: str,
        status: str = "active",
    ) -> None:
        """
        Update worker heartbeat to indicate it's alive.

        Args:
            db: Database session
            worker_id: Worker identifier
            status: Worker status (active, busy, idle)

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        self._validate_worker_id(worker_id)
        
        if status not in ["active", "busy", "idle", "stopping"]:
            raise ValidationException("Invalid worker status")

        with LoggingContext(channel="worker_heartbeat", worker_id=worker_id):
            try:
                self.queue_repo.update_worker_heartbeat(
                    db=db,
                    worker_id=worker_id,
                    status=status,
                )
                
            except SQLAlchemyError as e:
                logger.error(f"Database error updating heartbeat: {str(e)}")
                raise DatabaseException("Failed to update worker heartbeat") from e
            except Exception as e:
                logger.error(f"Unexpected error updating heartbeat: {str(e)}")
                raise

    def cleanup_stale_items(
        self,
        db: Session,
        timeout_minutes: int = 30,
        batch_size: int = 1000,
    ) -> int:
        """
        Clean up stale queue items (stuck in processing).

        Args:
            db: Database session
            timeout_minutes: Items stuck for longer than this are considered stale
            batch_size: Process in batches of this size

        Returns:
            int: Number of items cleaned up

        Raises:
            ValidationException: For invalid parameters
            DatabaseException: For database operation failures
        """
        if timeout_minutes < 5:
            raise ValidationException("Timeout must be at least 5 minutes")

        with LoggingContext(
            channel="queue_cleanup",
            timeout_minutes=timeout_minutes
        ):
            try:
                logger.info(f"Cleaning up stale queue items (timeout: {timeout_minutes}m)")
                
                cleaned_count = self.queue_repo.cleanup_stale_items(
                    db=db,
                    timeout_minutes=timeout_minutes,
                    batch_size=batch_size,
                )
                
                logger.info(f"Cleaned up {cleaned_count} stale queue items")
                return cleaned_count
                
            except ValidationException:
                raise
            except SQLAlchemyError as e:
                logger.error(f"Database error during cleanup: {str(e)}")
                raise DatabaseException("Failed to cleanup stale queue items") from e
            except Exception as e:
                logger.error(f"Unexpected error during cleanup: {str(e)}")
                raise
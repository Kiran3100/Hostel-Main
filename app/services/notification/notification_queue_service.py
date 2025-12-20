# --- File: C:\Hostel-Main\app\services\notification\notification_queue_service.py ---
"""
Notification Queue Service - Manages batch processing and priority queues.

Handles notification queuing, batch processing, retry logic,
worker management, and performance optimization.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
from collections import defaultdict

from sqlalchemy.orm import Session

from app.models.notification.notification_queue import (
    NotificationQueue,
    NotificationBatch
)
from app.models.notification.notification import Notification
from app.repositories.notification.notification_queue_repository import (
    NotificationQueueRepository
)
from app.repositories.notification.notification_repository import NotificationRepository
from app.schemas.common.enums import (
    NotificationType,
    NotificationStatus,
    Priority
)
from app.core.config import settings

logger = logging.getLogger(__name__)


class NotificationQueueService:
    """
    Service for notification queue and batch processing management.
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.queue_repo = NotificationQueueRepository(db_session)
        self.notification_repo = NotificationRepository(db_session)

    def enqueue_notification(
        self,
        notification: Notification,
        priority: Optional[Priority] = None,
        scheduled_for: Optional[datetime] = None,
        batch_id: Optional[UUID] = None
    ) -> NotificationQueue:
        """
        Add notification to processing queue.
        
        Args:
            notification: Notification to queue
            priority: Override priority
            scheduled_for: Schedule for future processing
            batch_id: Associate with batch
            
        Returns:
            NotificationQueue entry
        """
        try:
            queue_priority = priority or notification.priority
            
            queue_item = self.queue_repo.enqueue_notification(
                notification=notification,
                priority=queue_priority,
                scheduled_for=scheduled_for,
                batch_id=batch_id
            )
            
            logger.info(
                f"Notification {notification.id} queued with priority {queue_priority.value}"
            )
            
            return queue_item
            
        except Exception as e:
            logger.error(f"Error queuing notification: {str(e)}", exc_info=True)
            raise

    def process_queue(
        self,
        notification_type: Optional[NotificationType] = None,
        batch_size: int = 100,
        worker_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process notifications from queue.
        
        Args:
            notification_type: Process specific channel only
            batch_size: Number of notifications to process
            worker_id: Worker identifier
            
        Returns:
            Processing results
        """
        try:
            # Get next batch of notifications
            queue_items = self.queue_repo.dequeue_next_batch(
                notification_type=notification_type,
                batch_size=batch_size,
                worker_id=worker_id
            )
            
            if not queue_items:
                logger.debug("No notifications in queue to process")
                return {
                    'processed': 0,
                    'successful': 0,
                    'failed': 0
                }
            
            logger.info(f"Processing {len(queue_items)} notifications from queue")
            
            # Process each notification
            results = {
                'processed': 0,
                'successful': 0,
                'failed': 0,
                'errors': []
            }
            
            for queue_item in queue_items:
                start_time = datetime.utcnow()
                
                try:
                    # Get notification
                    notification = queue_item.notification
                    
                    # Process notification based on type
                    self._process_notification(notification)
                    
                    # Calculate processing duration
                    duration_ms = int(
                        (datetime.utcnow() - start_time).total_seconds() * 1000
                    )
                    
                    # Mark as complete
                    self.queue_repo.mark_processing_complete(
                        queue_item.id,
                        success=True,
                        processing_duration_ms=duration_ms
                    )
                    
                    results['successful'] += 1
                    
                except Exception as e:
                    logger.error(
                        f"Error processing notification {queue_item.notification_id}: {str(e)}",
                        exc_info=True
                    )
                    
                    # Calculate processing duration
                    duration_ms = int(
                        (datetime.utcnow() - start_time).total_seconds() * 1000
                    )
                    
                    # Mark as failed
                    self.queue_repo.mark_processing_complete(
                        queue_item.id,
                        success=False,
                        processing_duration_ms=duration_ms,
                        error_details={
                            'message': str(e),
                            'type': type(e).__name__
                        }
                    )
                    
                    results['failed'] += 1
                    results['errors'].append({
                        'notification_id': str(queue_item.notification_id),
                        'error': str(e)
                    })
                
                results['processed'] += 1
            
            logger.info(
                f"Queue processing complete: {results['successful']} successful, "
                f"{results['failed']} failed out of {results['processed']}"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing queue: {str(e)}", exc_info=True)
            raise

    def process_retries(
        self,
        batch_size: int = 50
    ) -> Dict[str, Any]:
        """
        Process failed notifications eligible for retry.
        
        Args:
            batch_size: Number of retries to process
            
        Returns:
            Retry processing results
        """
        try:
            from app.repositories.notification.notification_queue_repository import (
                RetryEligibleSpec
            )
            
            # Get retry-eligible items
            spec = RetryEligibleSpec()
            retry_items = self.queue_repo.find_by_specification(spec)[:batch_size]
            
            if not retry_items:
                logger.debug("No notifications eligible for retry")
                return {
                    'processed': 0,
                    'successful': 0,
                    'failed': 0
                }
            
            logger.info(f"Processing {len(retry_items)} retry notifications")
            
            results = {
                'processed': 0,
                'successful': 0,
                'failed': 0,
                'errors': []
            }
            
            for queue_item in retry_items:
                try:
                    # Reset status and increment retry count
                    queue_item.status = NotificationStatus.PROCESSING
                    queue_item.processing_started_at = datetime.utcnow()
                    self.db_session.commit()
                    
                    # Process notification
                    self._process_notification(queue_item.notification)
                    
                    # Mark as complete
                    self.queue_repo.mark_processing_complete(
                        queue_item.id,
                        success=True
                    )
                    
                    results['successful'] += 1
                    
                except Exception as e:
                    logger.error(
                        f"Error retrying notification {queue_item.notification_id}: {str(e)}"
                    )
                    
                    # Mark as failed
                    self.queue_repo.mark_processing_complete(
                        queue_item.id,
                        success=False,
                        error_details={
                            'message': str(e),
                            'type': type(e).__name__,
                            'retry_attempt': queue_item.retry_count
                        }
                    )
                    
                    results['failed'] += 1
                    results['errors'].append({
                        'notification_id': str(queue_item.notification_id),
                        'error': str(e),
                        'retry_count': queue_item.retry_count
                    })
                
                results['processed'] += 1
            
            logger.info(
                f"Retry processing complete: {results['successful']} successful, "
                f"{results['failed']} failed"
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error processing retries: {str(e)}", exc_info=True)
            raise

    def reset_stalled_items(
        self,
        stall_threshold_minutes: int = 30
    ) -> int:
        """
        Reset items that have been processing too long.
        
        Args:
            stall_threshold_minutes: Minutes before considering item stalled
            
        Returns:
            Number of items reset
        """
        try:
            reset_count = self.queue_repo.reset_stalled_items(stall_threshold_minutes)
            
            if reset_count > 0:
                logger.warning(f"Reset {reset_count} stalled queue items")
            
            return reset_count
            
        except Exception as e:
            logger.error(f"Error resetting stalled items: {str(e)}", exc_info=True)
            return 0

    def create_batch(
        self,
        batch_name: Optional[str],
        notification_type: NotificationType,
        total_notifications: int
    ) -> NotificationBatch:
        """Create new notification batch."""
        try:
            return self.queue_repo.create_batch(
                batch_name,
                notification_type,
                total_notifications
            )
        except Exception as e:
            logger.error(f"Error creating batch: {str(e)}", exc_info=True)
            raise

    def update_batch_progress(
        self,
        batch_id: UUID,
        processed_count: int,
        successful_count: int,
        failed_count: int
    ) -> bool:
        """Update batch processing progress."""
        try:
            return self.queue_repo.update_batch_progress(
                batch_id,
                processed_count,
                successful_count,
                failed_count
            )
        except Exception as e:
            logger.error(f"Error updating batch progress: {str(e)}", exc_info=True)
            return False

    def get_batch_status(
        self,
        batch_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get detailed batch status."""
        try:
            return self.queue_repo.get_batch_status(batch_id)
        except Exception as e:
            logger.error(f"Error getting batch status: {str(e)}", exc_info=True)
            return None

    def get_active_batches(self) -> List[Dict[str, Any]]:
        """Get currently active batches."""
        try:
            return self.queue_repo.get_active_batches()
        except Exception as e:
            logger.error(f"Error getting active batches: {str(e)}", exc_info=True)
            return []

    def get_queue_statistics(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics."""
        try:
            return self.queue_repo.get_queue_statistics()
        except Exception as e:
            logger.error(f"Error getting queue statistics: {str(e)}", exc_info=True)
            raise

    def get_processing_trends(
        self,
        hours: int = 24,
        group_by: str = 'hour'
    ) -> List[Dict[str, Any]]:
        """Get queue processing trends."""
        try:
            return self.queue_repo.get_processing_trends(hours, group_by)
        except Exception as e:
            logger.error(f"Error getting processing trends: {str(e)}", exc_info=True)
            raise

    def get_retry_analysis(self) -> Dict[str, Any]:
        """Analyze retry patterns and success rates."""
        try:
            return self.queue_repo.get_retry_analysis()
        except Exception as e:
            logger.error(f"Error getting retry analysis: {str(e)}", exc_info=True)
            raise

    def optimize_queue_performance(self) -> Dict[str, Any]:
        """Analyze and suggest queue optimizations."""
        try:
            return self.queue_repo.optimize_queue_performance()
        except Exception as e:
            logger.error(f"Error optimizing queue: {str(e)}", exc_info=True)
            raise

    def cleanup_completed_items(
        self,
        retention_hours: int = 24
    ) -> int:
        """Clean up old completed queue items."""
        try:
            cleaned = self.queue_repo.cleanup_completed_items(retention_hours)
            
            if cleaned > 0:
                logger.info(f"Cleaned up {cleaned} completed queue items")
            
            return cleaned
            
        except Exception as e:
            logger.error(f"Error cleaning up queue items: {str(e)}", exc_info=True)
            return 0

    # Helper methods
    def _process_notification(self, notification: Notification) -> None:
        """Process individual notification."""
        # Import here to avoid circular dependency
        from app.services.notification.notification_service import NotificationService
        
        service = NotificationService(self.db_session)
        service._dispatch_notification(notification)



# --- File: C:\Hostel-Main\app\repositories\notification\notification_queue_repository.py ---
"""
Notification Queue Repository for batch processing and priority management.

Handles queue operations, batch processing, retry logic, and performance
optimization with comprehensive monitoring and analytics.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from enum import Enum

from sqlalchemy import and_, or_, func, desc, asc, case, text
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql import select

from app.models.notification.notification_queue import (
    NotificationQueue,
    NotificationBatch
)
from app.models.notification.notification import Notification
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.specifications import Specification
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.schemas.common.enums import NotificationStatus, NotificationType, Priority


class PendingQueueItemsSpec(Specification):
    """Specification for queue items ready for processing."""
    
    def __init__(self, notification_type: Optional[NotificationType] = None):
        self.notification_type = notification_type
    
    def is_satisfied_by(self, query):
        conditions = [
            NotificationQueue.status == NotificationStatus.QUEUED,
            or_(
                NotificationQueue.scheduled_for.is_(None),
                NotificationQueue.scheduled_for <= datetime.utcnow()
            )
        ]
        
        if self.notification_type:
            conditions.append(NotificationQueue.notification_type == self.notification_type)
        
        return query.filter(and_(*conditions))


class RetryEligibleSpec(Specification):
    """Specification for items eligible for retry."""
    
    def is_satisfied_by(self, query):
        return query.filter(
            and_(
                NotificationQueue.status == NotificationStatus.FAILED,
                NotificationQueue.retry_count < NotificationQueue.max_retries,
                or_(
                    NotificationQueue.next_retry_at.is_(None),
                    NotificationQueue.next_retry_at <= datetime.utcnow()
                )
            )
        )


class NotificationQueueRepository(BaseRepository[NotificationQueue]):
    """
    Repository for notification queue management with batch processing and optimization.
    """

    def __init__(self, db_session: Session):
        super().__init__(NotificationQueue, db_session)

    # Core queue operations
    def enqueue_notification(
        self,
        notification: Notification,
        priority: Priority = Priority.MEDIUM,
        scheduled_for: Optional[datetime] = None,
        batch_id: Optional[UUID] = None
    ) -> NotificationQueue:
        """Add notification to processing queue."""
        queue_item = NotificationQueue(
            notification_id=notification.id,
            notification_type=notification.notification_type,
            priority=priority,
            scheduled_for=scheduled_for,
            batch_id=batch_id
        )
        
        # Update notification status
        notification.status = NotificationStatus.QUEUED
        
        return self.create(queue_item)

    def dequeue_next_batch(
        self,
        notification_type: Optional[NotificationType] = None,
        batch_size: int = 100,
        worker_id: Optional[str] = None
    ) -> List[NotificationQueue]:
        """Get next batch of notifications for processing."""
        query = self.db_session.query(NotificationQueue).filter(
            and_(
                NotificationQueue.status == NotificationStatus.QUEUED,
                or_(
                    NotificationQueue.scheduled_for.is_(None),
                    NotificationQueue.scheduled_for <= datetime.utcnow()
                )
            )
        ).order_by(
            desc(NotificationQueue.priority),
            asc(NotificationQueue.queued_at)
        )
        
        if notification_type:
            query = query.filter(NotificationQueue.notification_type == notification_type)
        
        # Lock items for processing
        items = query.limit(batch_size).all()
        
        if items and worker_id:
            item_ids = [item.id for item in items]
            self.db_session.query(NotificationQueue).filter(
                NotificationQueue.id.in_(item_ids)
            ).update({
                'status': NotificationStatus.PROCESSING,
                'processing_started_at': datetime.utcnow(),
                'worker_id': worker_id
            }, synchronize_session=False)
            
            self.db_session.commit()
        
        return items

    def mark_processing_complete(
        self,
        queue_item_id: UUID,
        success: bool,
        processing_duration_ms: Optional[int] = None,
        error_details: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Mark queue item processing as complete."""
        queue_item = self.find_by_id(queue_item_id)
        if not queue_item:
            return False
        
        now = datetime.utcnow()
        
        if success:
            queue_item.status = NotificationStatus.COMPLETED
            queue_item.processing_completed_at = now
        else:
            queue_item.status = NotificationStatus.FAILED
            queue_item.retry_count += 1
            
            if error_details:
                queue_item.last_error = error_details.get('message')
                queue_item.error_details = error_details
            
            # Schedule retry if eligible
            if queue_item.retry_count < queue_item.max_retries:
                retry_delay = self._calculate_retry_delay(queue_item.retry_count)
                queue_item.next_retry_at = now + retry_delay
                queue_item.status = NotificationStatus.QUEUED
        
        if processing_duration_ms:
            queue_item.processing_duration_ms = processing_duration_ms
        
        queue_item.processing_completed_at = now
        
        self.db_session.commit()
        return True

    def find_stalled_items(
        self,
        stall_threshold_minutes: int = 30
    ) -> List[NotificationQueue]:
        """Find items that have been processing too long."""
        threshold = datetime.utcnow() - timedelta(minutes=stall_threshold_minutes)
        
        return self.db_session.query(NotificationQueue).filter(
            and_(
                NotificationQueue.status == NotificationStatus.PROCESSING,
                NotificationQueue.processing_started_at < threshold
            )
        ).all()

    def reset_stalled_items(
        self,
        stall_threshold_minutes: int = 30
    ) -> int:
        """Reset stalled items back to queued status."""
        threshold = datetime.utcnow() - timedelta(minutes=stall_threshold_minutes)
        
        updated_count = self.db_session.query(NotificationQueue).filter(
            and_(
                NotificationQueue.status == NotificationStatus.PROCESSING,
                NotificationQueue.processing_started_at < threshold
            )
        ).update({
            'status': NotificationStatus.QUEUED,
            'processing_started_at': None,
            'worker_id': None
        }, synchronize_session=False)
        
        self.db_session.commit()
        return updated_count

    # Batch processing
    def create_batch(
        self,
        batch_name: Optional[str],
        notification_type: NotificationType,
        total_notifications: int
    ) -> NotificationBatch:
        """Create new notification batch."""
        batch = NotificationBatch(
            batch_name=batch_name,
            notification_type=notification_type,
            total_notifications=total_notifications
        )
        
        return self.create(batch)

    def update_batch_progress(
        self,
        batch_id: UUID,
        processed_count: int,
        successful_count: int,
        failed_count: int
    ) -> bool:
        """Update batch processing progress."""
        batch = self.db_session.query(NotificationBatch).filter(
            NotificationBatch.id == batch_id
        ).first()
        
        if not batch:
            return False
        
        batch.processed = processed_count
        batch.successful = successful_count
        batch.failed = failed_count
        
        # Update status
        if processed_count == 0:
            batch.status = 'queued'
        elif processed_count < batch.total_notifications:
            batch.status = 'processing'
            if not batch.started_at:
                batch.started_at = datetime.utcnow()
        else:
            batch.status = 'completed'
            batch.completed_at = datetime.utcnow()
        
        # Calculate throughput
        if batch.started_at and processed_count > 0:
            elapsed_minutes = (datetime.utcnow() - batch.started_at).total_seconds() / 60
            batch.current_throughput = processed_count / elapsed_minutes if elapsed_minutes > 0 else 0
        
        # Estimate completion
        if batch.current_throughput and batch.current_throughput > 0:
            remaining_items = batch.total_notifications - processed_count
            remaining_minutes = remaining_items / batch.current_throughput
            batch.estimated_completion = datetime.utcnow() + timedelta(minutes=remaining_minutes)
        
        self.db_session.commit()
        return True

    def get_batch_status(self, batch_id: UUID) -> Optional[Dict[str, Any]]:
        """Get detailed batch status."""
        batch = self.db_session.query(NotificationBatch).filter(
            NotificationBatch.id == batch_id
        ).first()
        
        if not batch:
            return None
        
        return {
            'id': str(batch.id),
            'batch_name': batch.batch_name,
            'notification_type': batch.notification_type.value,
            'status': batch.status,
            'total_notifications': batch.total_notifications,
            'processed': batch.processed,
            'successful': batch.successful,
            'failed': batch.failed,
            'progress_percentage': batch.progress_percentage,
            'success_rate': batch.success_rate,
            'current_throughput': float(batch.current_throughput or 0),
            'estimated_completion': batch.estimated_completion.isoformat() if batch.estimated_completion else None,
            'started_at': batch.started_at.isoformat() if batch.started_at else None,
            'completed_at': batch.completed_at.isoformat() if batch.completed_at else None
        }

    # Queue analytics and monitoring
    def get_queue_statistics(self) -> Dict[str, Any]:
        """Get comprehensive queue statistics."""
        stats = self.db_session.query(
            NotificationQueue.status,
            NotificationQueue.notification_type,
            func.count().label('count'),
            func.avg(NotificationQueue.processing_duration_ms).label('avg_processing_time'),
            func.min(NotificationQueue.queued_at).label('oldest_queued')
        ).group_by(
            NotificationQueue.status,
            NotificationQueue.notification_type
        ).all()
        
        # Priority distribution
        priority_stats = self.db_session.query(
            NotificationQueue.priority,
            func.count().label('count')
        ).filter(
            NotificationQueue.status == NotificationStatus.QUEUED
        ).group_by(NotificationQueue.priority).all()
        
        # Worker performance
        worker_stats = self.db_session.query(
            NotificationQueue.worker_id,
            func.count().label('processed_count'),
            func.avg(NotificationQueue.processing_duration_ms).label('avg_processing_time'),
            func.sum(
                case([(NotificationQueue.status == NotificationStatus.COMPLETED, 1)], else_=0)
            ).label('successful_count')
        ).filter(
            and_(
                NotificationQueue.worker_id.isnot(None),
                NotificationQueue.processing_completed_at >= datetime.utcnow() - timedelta(hours=24)
            )
        ).group_by(NotificationQueue.worker_id).all()
        
        return {
            'queue_by_status': [
                {
                    'status': stat.status.value,
                    'notification_type': stat.notification_type.value,
                    'count': stat.count,
                    'avg_processing_time_ms': float(stat.avg_processing_time or 0),
                    'oldest_queued': stat.oldest_queued.isoformat() if stat.oldest_queued else None
                }
                for stat in stats
            ],
            'priority_distribution': [
                {
                    'priority': stat.priority.value,
                    'count': stat.count
                }
                for stat in priority_stats
            ],
            'worker_performance': [
                {
                    'worker_id': stat.worker_id,
                    'processed_count': stat.processed_count,
                    'successful_count': stat.successful_count,
                    'success_rate': (stat.successful_count / stat.processed_count * 100) if stat.processed_count > 0 else 0,
                    'avg_processing_time_ms': float(stat.avg_processing_time or 0)
                }
                for stat in worker_stats
            ]
        }

    def get_processing_trends(
        self,
        hours: int = 24,
        group_by: str = 'hour'
    ) -> List[Dict[str, Any]]:
        """Get queue processing trends."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        if group_by == 'hour':
            date_trunc = func.date_trunc('hour', NotificationQueue.processing_completed_at)
        else:  # minute
            date_trunc = func.date_trunc('minute', NotificationQueue.processing_completed_at)
        
        trends = self.db_session.query(
            date_trunc.label('period'),
            NotificationQueue.notification_type,
            func.count().label('processed'),
            func.sum(
                case([(NotificationQueue.status == NotificationStatus.COMPLETED, 1)], else_=0)
            ).label('successful'),
            func.avg(NotificationQueue.processing_duration_ms).label('avg_processing_time')
        ).filter(
            and_(
                NotificationQueue.processing_completed_at >= start_time,
                NotificationQueue.processing_completed_at <= end_time
            )
        ).group_by(
            date_trunc,
            NotificationQueue.notification_type
        ).order_by(date_trunc).all()
        
        return [
            {
                'period': trend.period.isoformat(),
                'notification_type': trend.notification_type.value,
                'processed': trend.processed,
                'successful': trend.successful,
                'failed': trend.processed - trend.successful,
                'success_rate': (trend.successful / trend.processed * 100) if trend.processed > 0 else 0,
                'avg_processing_time_ms': float(trend.avg_processing_time or 0)
            }
            for trend in trends
        ]

    def get_retry_analysis(self) -> Dict[str, Any]:
        """Analyze retry patterns and success rates."""
        retry_stats = self.db_session.query(
            NotificationQueue.retry_count,
            func.count().label('total_items'),
            func.sum(
                case([(NotificationQueue.status == NotificationStatus.COMPLETED, 1)], else_=0)
            ).label('eventually_successful')
        ).filter(
            NotificationQueue.retry_count > 0
        ).group_by(NotificationQueue.retry_count).all()
        
        # Error patterns
        error_patterns = self.db_session.query(
            NotificationQueue.last_error,
            func.count().label('occurrence_count')
        ).filter(
            and_(
                NotificationQueue.status == NotificationStatus.FAILED,
                NotificationQueue.last_error.isnot(None)
            )
        ).group_by(NotificationQueue.last_error).order_by(desc('occurrence_count')).limit(10).all()
        
        return {
            'retry_success_rates': [
                {
                    'retry_attempt': stat.retry_count,
                    'total_items': stat.total_items,
                    'eventually_successful': stat.eventually_successful,
                    'success_rate': (stat.eventually_successful / stat.total_items * 100) if stat.total_items > 0 else 0
                }
                for stat in retry_stats
            ],
            'common_errors': [
                {
                    'error_message': stat.last_error,
                    'occurrence_count': stat.occurrence_count
                }
                for stat in error_patterns
            ]
        }

    # Maintenance and optimization
    def cleanup_completed_items(
        self,
        retention_hours: int = 24,
        batch_size: int = 1000
    ) -> int:
        """Clean up old completed queue items."""
        cutoff_time = datetime.utcnow() - timedelta(hours=retention_hours)
        
        deleted_count = 0
        while True:
            items_to_delete = self.db_session.query(NotificationQueue.id).filter(
                and_(
                    NotificationQueue.status == NotificationStatus.COMPLETED,
                    NotificationQueue.processing_completed_at < cutoff_time
                )
            ).limit(batch_size).all()
            
            if not items_to_delete:
                break
            
            item_ids = [item.id for item in items_to_delete]
            batch_deleted = self.db_session.query(NotificationQueue).filter(
                NotificationQueue.id.in_(item_ids)
            ).delete(synchronize_session=False)
            
            deleted_count += batch_deleted
            self.db_session.commit()
        
        return deleted_count

    def optimize_queue_performance(self) -> Dict[str, Any]:
        """Analyze and suggest queue performance optimizations."""
        # Analyze processing times by type
        processing_stats = self.db_session.query(
            NotificationQueue.notification_type,
            func.avg(NotificationQueue.processing_duration_ms).label('avg_time'),
            func.percentile_cont(0.95).within_group(
                NotificationQueue.processing_duration_ms
            ).label('p95_time'),
            func.count().label('sample_size')
        ).filter(
            and_(
                NotificationQueue.processing_duration_ms.isnot(None),
                NotificationQueue.processing_completed_at >= datetime.utcnow() - timedelta(days=7)
            )
        ).group_by(NotificationQueue.notification_type).all()
        
        # Queue depth analysis
        current_queue_depth = self.db_session.query(
            NotificationQueue.notification_type,
            func.count().label('queued_count'),
            func.min(NotificationQueue.queued_at).label('oldest_item')
        ).filter(
            NotificationQueue.status == NotificationStatus.QUEUED
        ).group_by(NotificationQueue.notification_type).all()
        
        recommendations = []
        
        for stat in processing_stats:
            avg_time = float(stat.avg_time or 0)
            p95_time = float(stat.p95_time or 0)
            
            if avg_time > 5000:  # 5 seconds
                recommendations.append(
                    f"{stat.notification_type.value}: Consider optimizing processing (avg: {avg_time:.0f}ms)"
                )
            
            if p95_time > 10000:  # 10 seconds
                recommendations.append(
                    f"{stat.notification_type.value}: High P95 processing time ({p95_time:.0f}ms) - investigate bottlenecks"
                )
        
        for queue_stat in current_queue_depth:
            if queue_stat.queued_count > 1000:
                recommendations.append(
                    f"{queue_stat.notification_type.value}: Large queue depth ({queue_stat.queued_count}) - consider adding workers"
                )
        
        return {
            'processing_performance': [
                {
                    'notification_type': stat.notification_type.value,
                    'avg_processing_time_ms': float(stat.avg_time or 0),
                    'p95_processing_time_ms': float(stat.p95_time or 0),
                    'sample_size': stat.sample_size
                }
                for stat in processing_stats
            ],
            'queue_depths': [
                {
                    'notification_type': stat.notification_type.value,
                    'queued_count': stat.queued_count,
                    'oldest_item_age_minutes': (datetime.utcnow() - stat.oldest_item).total_seconds() / 60 if stat.oldest_item else 0
                }
                for stat in current_queue_depth
            ],
            'recommendations': recommendations
        }

    # Helper methods
    def _calculate_retry_delay(self, retry_count: int) -> timedelta:
        """Calculate exponential backoff retry delay."""
        base_delay_seconds = 60  # 1 minute
        max_delay_seconds = 3600  # 1 hour
        
        delay_seconds = min(base_delay_seconds * (2 ** retry_count), max_delay_seconds)
        return timedelta(seconds=delay_seconds)

    def get_active_batches(self) -> List[Dict[str, Any]]:
        """Get currently active batches."""
        batches = self.db_session.query(NotificationBatch).filter(
            NotificationBatch.status.in_(['queued', 'processing'])
        ).order_by(NotificationBatch.created_at).all()
        
        return [
            {
                'id': str(batch.id),
                'batch_name': batch.batch_name,
                'notification_type': batch.notification_type.value,
                'status': batch.status,
                'progress_percentage': batch.progress_percentage,
                'current_throughput': float(batch.current_throughput or 0),
                'estimated_completion': batch.estimated_completion.isoformat() if batch.estimated_completion else None
            }
            for batch in batches
        ]
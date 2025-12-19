# --- File: C:\Hostel-Main\app\repositories\notification\notification_repository.py ---
"""
Core Notification Repository with comprehensive management capabilities.

Handles notification lifecycle, status tracking, delivery optimization,
and performance analytics across all notification channels.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, desc, asc, case, text
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql import select

from app.models.notification.notification import (
    Notification, 
    NotificationStatusHistory, 
    NotificationReadReceipt
)
from app.models.notification.email_notification import EmailNotification
from app.models.notification.sms_notification import SMSNotification
from app.models.notification.push_notification import PushNotification
from app.models.user.user import User
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.query_builder import QueryBuilder
from app.repositories.base.specifications import Specification
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.schemas.common.enums import (
    NotificationStatus, 
    NotificationType, 
    Priority
)


class PendingNotificationsSpec(Specification):
    """Specification for pending notifications ready for processing."""
    
    def __init__(self, notification_type: Optional[NotificationType] = None):
        self.notification_type = notification_type
    
    def is_satisfied_by(self, query):
        conditions = [
            Notification.status.in_([
                NotificationStatus.PENDING,
                NotificationStatus.QUEUED,
                NotificationStatus.PROCESSING
            ]),
            or_(
                Notification.scheduled_at.is_(None),
                Notification.scheduled_at <= datetime.utcnow()
            )
        ]
        
        if self.notification_type:
            conditions.append(Notification.notification_type == self.notification_type)
        
        return query.filter(and_(*conditions))


class UnreadNotificationsSpec(Specification):
    """Specification for unread user notifications."""
    
    def __init__(self, user_id: UUID):
        self.user_id = user_id
    
    def is_satisfied_by(self, query):
        return query.filter(
            and_(
                Notification.recipient_user_id == self.user_id,
                Notification.read_at.is_(None),
                Notification.status.in_([
                    NotificationStatus.DELIVERED,
                    NotificationStatus.SENT,
                    NotificationStatus.COMPLETED
                ])
            )
        )


class NotificationRepository(BaseRepository[Notification]):
    """
    Comprehensive notification repository with advanced querying and analytics.
    """

    def __init__(self, db_session: Session):
        super().__init__(Notification, db_session)

    # Core notification operations
    def create_notification(
        self,
        notification_data: Dict[str, Any],
        template_variables: Optional[Dict[str, Any]] = None
    ) -> Notification:
        """Create notification with template processing."""
        notification = Notification(**notification_data)
        
        if template_variables:
            notification.metadata = notification.metadata or {}
            notification.metadata['template_variables'] = template_variables
        
        return self.create(notification)

    def find_by_user(
        self, 
        user_id: UUID, 
        notification_types: Optional[List[NotificationType]] = None,
        pagination: Optional[PaginationParams] = None
    ) -> PaginatedResult[Notification]:
        """Get notifications for a user with optional filtering."""
        query = self.db_session.query(Notification).filter(
            Notification.recipient_user_id == user_id
        ).options(
            selectinload(Notification.email_details),
            selectinload(Notification.sms_details),
            selectinload(Notification.push_details)
        )
        
        if notification_types:
            query = query.filter(Notification.notification_type.in_(notification_types))
        
        query = query.order_by(desc(Notification.created_at))
        
        if pagination:
            return self.paginate_query(query, pagination)
        
        return PaginatedResult(
            items=query.all(),
            total_count=query.count(),
            page=1,
            page_size=len(query.all())
        )

    def find_unread_for_user(self, user_id: UUID) -> List[Notification]:
        """Get all unread notifications for a user."""
        spec = UnreadNotificationsSpec(user_id)
        return self.find_by_specification(spec)

    def get_unread_count(self, user_id: UUID) -> int:
        """Get count of unread notifications for user."""
        return self.db_session.query(func.count(Notification.id)).filter(
            and_(
                Notification.recipient_user_id == user_id,
                Notification.read_at.is_(None),
                Notification.status.in_([
                    NotificationStatus.DELIVERED,
                    NotificationStatus.SENT,
                    NotificationStatus.COMPLETED
                ])
            )
        ).scalar()

    def find_scheduled_notifications(
        self, 
        cutoff_time: Optional[datetime] = None
    ) -> List[Notification]:
        """Find notifications scheduled for delivery."""
        if cutoff_time is None:
            cutoff_time = datetime.utcnow()
        
        return self.db_session.query(Notification).filter(
            and_(
                Notification.status == NotificationStatus.PENDING,
                Notification.scheduled_at <= cutoff_time
            )
        ).order_by(asc(Notification.scheduled_at), desc(Notification.priority)).all()

    def find_failed_notifications(
        self, 
        retry_eligible: bool = True
    ) -> List[Notification]:
        """Find failed notifications, optionally only retry-eligible ones."""
        query = self.db_session.query(Notification).filter(
            Notification.status == NotificationStatus.FAILED
        )
        
        if retry_eligible:
            query = query.filter(
                Notification.retry_count < Notification.max_retries
            )
        
        return query.order_by(desc(Notification.failed_at)).all()

    # Status management
    def update_status(
        self, 
        notification_id: UUID, 
        status: NotificationStatus,
        details: Optional[Dict[str, Any]] = None,
        changed_by: Optional[UUID] = None
    ) -> bool:
        """Update notification status with history tracking."""
        notification = self.find_by_id(notification_id)
        if not notification:
            return False
        
        old_status = notification.status
        notification.status = status
        
        # Update timestamps based on status
        now = datetime.utcnow()
        if status == NotificationStatus.SENT:
            notification.sent_at = now
        elif status == NotificationStatus.DELIVERED:
            notification.delivered_at = now
        elif status == NotificationStatus.FAILED:
            notification.failed_at = now
        
        # Update failure details
        if details:
            if status == NotificationStatus.FAILED:
                notification.failure_reason = details.get('reason')
            
            notification.metadata = notification.metadata or {}
            notification.metadata.update(details)
        
        # Create status history entry
        self._create_status_history(
            notification_id, old_status, status, changed_by, details
        )
        
        self.db_session.commit()
        return True

    def mark_as_read(
        self, 
        notification_id: UUID, 
        user_id: UUID,
        read_context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Mark notification as read with context tracking."""
        notification = self.find_by_id(notification_id)
        if not notification or notification.recipient_user_id != user_id:
            return False
        
        if notification.read_at is None:
            notification.read_at = datetime.utcnow()
            
            # Create read receipt
            read_receipt = NotificationReadReceipt(
                notification_id=notification_id,
                user_id=user_id,
                read_at=notification.read_at
            )
            
            if read_context:
                for key, value in read_context.items():
                    if hasattr(read_receipt, key):
                        setattr(read_receipt, key, value)
            
            # Calculate time to read
            if notification.delivered_at:
                read_receipt.time_to_read_seconds = int(
                    (notification.read_at - notification.delivered_at).total_seconds()
                )
            
            self.db_session.add(read_receipt)
            self.db_session.commit()
            return True
        
        return False

    def mark_bulk_as_read(
        self, 
        notification_ids: List[UUID], 
        user_id: UUID
    ) -> int:
        """Mark multiple notifications as read."""
        now = datetime.utcnow()
        
        # Update notifications
        updated_count = self.db_session.query(Notification).filter(
            and_(
                Notification.id.in_(notification_ids),
                Notification.recipient_user_id == user_id,
                Notification.read_at.is_(None)
            )
        ).update(
            {Notification.read_at: now},
            synchronize_session=False
        )
        
        # Create read receipts
        if updated_count > 0:
            notifications = self.db_session.query(Notification).filter(
                and_(
                    Notification.id.in_(notification_ids),
                    Notification.recipient_user_id == user_id,
                    Notification.read_at == now
                )
            ).all()
            
            read_receipts = []
            for notification in notifications:
                receipt = NotificationReadReceipt(
                    notification_id=notification.id,
                    user_id=user_id,
                    read_at=now,
                    read_method='bulk_read'
                )
                
                if notification.delivered_at:
                    receipt.time_to_read_seconds = int(
                        (now - notification.delivered_at).total_seconds()
                    )
                
                read_receipts.append(receipt)
            
            self.db_session.add_all(read_receipts)
        
        self.db_session.commit()
        return updated_count

    # Analytics and reporting
    def get_delivery_statistics(
        self, 
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get delivery statistics for a time period."""
        query = self.db_session.query(
            Notification.notification_type,
            Notification.status,
            func.count().label('count')
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_id:
            query = query.filter(Notification.hostel_id == hostel_id)
        
        results = query.group_by(
            Notification.notification_type,
            Notification.status
        ).all()
        
        # Process results into structured format
        stats = {}
        for result in results:
            channel = result.notification_type.value
            status = result.status.value
            count = result.count
            
            if channel not in stats:
                stats[channel] = {}
            stats[channel][status] = count
        
        return {
            'period': {'start': start_date, 'end': end_date},
            'by_channel': stats,
            'total_sent': sum(
                stats.get(channel, {}).get('SENT', 0) + 
                stats.get(channel, {}).get('DELIVERED', 0)
                for channel in stats.keys()
            )
        }

    def get_engagement_metrics(
        self, 
        start_date: datetime,
        end_date: datetime,
        user_ids: Optional[List[UUID]] = None
    ) -> Dict[str, Any]:
        """Get engagement metrics for notifications."""
        query = self.db_session.query(Notification).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date,
                Notification.status.in_([
                    NotificationStatus.DELIVERED,
                    NotificationStatus.SENT,
                    NotificationStatus.COMPLETED
                ])
            )
        )
        
        if user_ids:
            query = query.filter(Notification.recipient_user_id.in_(user_ids))
        
        notifications = query.all()
        
        total_notifications = len(notifications)
        read_notifications = len([n for n in notifications if n.read_at])
        clicked_notifications = len([n for n in notifications if n.clicked_at])
        
        return {
            'total_notifications': total_notifications,
            'read_notifications': read_notifications,
            'clicked_notifications': clicked_notifications,
            'read_rate': (read_notifications / total_notifications * 100) if total_notifications > 0 else 0,
            'click_rate': (clicked_notifications / total_notifications * 100) if total_notifications > 0 else 0,
            'average_time_to_read': self._calculate_average_time_to_read(notifications)
        }

    def get_performance_trends(
        self, 
        days: int = 30,
        hostel_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Get performance trends over time."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        # Daily aggregation query
        query = self.db_session.query(
            func.date(Notification.created_at).label('date'),
            Notification.notification_type,
            func.count().label('total'),
            func.sum(
                case([(Notification.status == NotificationStatus.DELIVERED, 1)], else_=0)
            ).label('delivered'),
            func.sum(
                case([(Notification.read_at.isnot(None), 1)], else_=0)
            ).label('read')
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_id:
            query = query.filter(Notification.hostel_id == hostel_id)
        
        results = query.group_by(
            func.date(Notification.created_at),
            Notification.notification_type
        ).order_by(func.date(Notification.created_at)).all()
        
        # Process into trend data
        trends = []
        for result in results:
            trends.append({
                'date': result.date.isoformat(),
                'channel': result.notification_type.value,
                'total': result.total,
                'delivered': result.delivered,
                'read': result.read,
                'delivery_rate': (result.delivered / result.total * 100) if result.total > 0 else 0,
                'read_rate': (result.read / result.delivered * 100) if result.delivered > 0 else 0
            })
        
        return trends

    # Maintenance and cleanup
    def cleanup_old_notifications(
        self, 
        retention_days: int = 365,
        batch_size: int = 1000
    ) -> int:
        """Clean up old notifications beyond retention period."""
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        deleted_count = 0
        
        while True:
            # Find batch of old notifications
            old_notifications = self.db_session.query(Notification.id).filter(
                and_(
                    Notification.created_at < cutoff_date,
                    Notification.status.in_([
                        NotificationStatus.DELIVERED,
                        NotificationStatus.COMPLETED,
                        NotificationStatus.FAILED
                    ])
                )
            ).limit(batch_size).all()
            
            if not old_notifications:
                break
            
            notification_ids = [n.id for n in old_notifications]
            
            # Delete related records first
            self.db_session.query(NotificationStatusHistory).filter(
                NotificationStatusHistory.notification_id.in_(notification_ids)
            ).delete(synchronize_session=False)
            
            self.db_session.query(NotificationReadReceipt).filter(
                NotificationReadReceipt.notification_id.in_(notification_ids)
            ).delete(synchronize_session=False)
            
            # Delete notifications
            batch_deleted = self.db_session.query(Notification).filter(
                Notification.id.in_(notification_ids)
            ).delete(synchronize_session=False)
            
            deleted_count += batch_deleted
            self.db_session.commit()
        
        return deleted_count

    def find_orphaned_notifications(self) -> List[Notification]:
        """Find notifications without valid recipients."""
        return self.db_session.query(Notification).filter(
            and_(
                Notification.recipient_user_id.is_(None),
                Notification.recipient_email.is_(None),
                Notification.recipient_phone.is_(None)
            )
        ).all()

    # Helper methods
    def _create_status_history(
        self,
        notification_id: UUID,
        from_status: NotificationStatus,
        to_status: NotificationStatus,
        changed_by: Optional[UUID] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> NotificationStatusHistory:
        """Create status history entry."""
        history = NotificationStatusHistory(
            notification_id=notification_id,
            from_status=from_status,
            to_status=to_status,
            changed_by=changed_by,
            metadata=metadata or {}
        )
        self.db_session.add(history)
        return history

    def _calculate_average_time_to_read(self, notifications: List[Notification]) -> Optional[float]:
        """Calculate average time to read for notifications."""
        read_times = []
        for notification in notifications:
            if notification.read_at and notification.delivered_at:
                time_diff = notification.read_at - notification.delivered_at
                read_times.append(time_diff.total_seconds())
        
        return sum(read_times) / len(read_times) if read_times else None
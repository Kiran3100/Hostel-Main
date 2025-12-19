# --- File: C:\Hostel-Main\app\repositories\notification\push_notification_repository.py ---
"""
Push Notification Repository with device targeting and engagement tracking.

Handles push notification delivery across platforms (iOS, Android, Web)
with advanced targeting, badge management, and performance analytics.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID

from sqlalchemy import and_, or_, func, desc, asc, case, text
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql import select

from app.models.notification.push_notification import PushNotification
from app.models.notification.notification import Notification
from app.models.notification.device_token import DeviceToken
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.specifications import Specification
from app.repositories.base.pagination import PaginationParams, PaginatedResult
from app.schemas.common.enums import DeviceType, NotificationStatus


class DeliveredPushSpec(Specification):
    """Specification for successfully delivered push notifications."""
    
    def is_satisfied_by(self, query):
        return query.filter(PushNotification.delivered == True)


class HighEngagementPushSpec(Specification):
    """Specification for push notifications with high engagement."""
    
    def is_satisfied_by(self, query):
        return query.filter(PushNotification.tapped == True)


class PushNotificationRepository(BaseRepository[PushNotification]):
    """
    Repository for push notification management with device targeting and analytics.
    """

    def __init__(self, db_session: Session):
        super().__init__(PushNotification, db_session)

    # Core push notification operations
    def create_push_with_targeting(
        self,
        notification: Notification,
        push_data: Dict[str, Any],
        device_token_id: Optional[UUID] = None
    ) -> PushNotification:
        """Create push notification with device targeting."""
        push_notification = PushNotification(
            notification_id=notification.id,
            device_token_id=device_token_id,
            **push_data
        )
        
        return self.create(push_notification)

    def find_by_notification_id(self, notification_id: UUID) -> Optional[PushNotification]:
        """Find push notification by notification ID."""
        return self.db_session.query(PushNotification).filter(
            PushNotification.notification_id == notification_id
        ).options(
            joinedload(PushNotification.notification),
            joinedload(PushNotification.device_token)
        ).first()

    def find_by_provider_message_id(
        self, 
        provider_message_id: str
    ) -> Optional[PushNotification]:
        """Find push notification by provider message ID."""
        return self.db_session.query(PushNotification).filter(
            PushNotification.provider_message_id == provider_message_id
        ).first()

    def find_for_device_tokens(
        self,
        device_token_ids: List[UUID],
        limit: int = 1000
    ) -> List[PushNotification]:
        """Find push notifications for specific device tokens."""
        return self.db_session.query(PushNotification).filter(
            PushNotification.device_token_id.in_(device_token_ids)
        ).limit(limit).all()

    # Delivery and engagement tracking
    def update_delivery_status(
        self,
        push_id: UUID,
        delivered: bool,
        delivery_status: str,
        provider_response: Optional[Dict[str, Any]] = None,
        error_details: Optional[Dict[str, str]] = None
    ) -> bool:
        """Update push notification delivery status."""
        push = self.find_by_id(push_id)
        if not push:
            return False
        
        push.delivered = delivered
        push.delivery_status = delivery_status
        
        if provider_response:
            push.provider_response = provider_response
        
        if error_details:
            push.error_code = error_details.get('code')
            push.error_message = error_details.get('message')
        
        # Update related notification status
        if push.notification:
            if delivered:
                push.notification.status = NotificationStatus.DELIVERED
                if not push.notification.delivered_at:
                    push.notification.delivered_at = datetime.utcnow()
            elif error_details:
                push.notification.status = NotificationStatus.FAILED
                push.notification.failed_at = datetime.utcnow()
                push.notification.failure_reason = error_details.get('message')
        
        self.db_session.commit()
        return True

    def track_push_tap(
        self,
        push_id: UUID,
        action_taken: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Track push notification tap/interaction."""
        push = self.find_by_id(push_id)
        if not push:
            return False
        
        now = datetime.utcnow()
        
        if not push.tapped:
            push.tapped = True
            push.tapped_at = now
        
        if action_taken:
            push.action_taken = action_taken
        
        # Update notification interaction
        if push.notification and not push.notification.clicked_at:
            push.notification.clicked_at = now
            push.notification.read_at = now
        
        self.db_session.commit()
        return True

    def bulk_update_delivery_status(
        self,
        status_updates: List[Dict[str, Any]]
    ) -> int:
        """Bulk update delivery status for multiple push notifications."""
        updated_count = 0
        
        for update in status_updates:
            if self.update_delivery_status(**update):
                updated_count += 1
        
        return updated_count

    # Badge management
    def update_badge_counts(
        self,
        user_device_badges: Dict[UUID, int]
    ) -> int:
        """Update badge counts for multiple users."""
        updated_count = 0
        
        for user_id, badge_count in user_device_badges.items():
            # Update all iOS devices for the user
            count = self.db_session.query(DeviceToken).filter(
                and_(
                    DeviceToken.user_id == user_id,
                    DeviceToken.device_type == DeviceType.IOS.value,
                    DeviceToken.is_active == True
                )
            ).update(
                {DeviceToken.current_badge_count: badge_count},
                synchronize_session=False
            )
            updated_count += count
        
        self.db_session.commit()
        return updated_count

    def increment_badge_for_users(
        self,
        user_ids: List[UUID],
        increment: int = 1
    ) -> int:
        """Increment badge count for multiple users."""
        updated_count = self.db_session.query(DeviceToken).filter(
            and_(
                DeviceToken.user_id.in_(user_ids),
                DeviceToken.device_type == DeviceType.IOS.value,
                DeviceToken.is_active == True,
                DeviceToken.token_invalid == False
            )
        ).update(
            {DeviceToken.current_badge_count: DeviceToken.current_badge_count + increment},
            synchronize_session=False
        )
        
        self.db_session.commit()
        return updated_count

    # Analytics and reporting
    def get_delivery_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        device_type: Optional[DeviceType] = None,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get comprehensive push notification delivery analytics."""
        base_query = self.db_session.query(PushNotification).join(
            Notification, PushNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if device_type:
            base_query = base_query.join(
                DeviceToken, PushNotification.device_token_id == DeviceToken.id
            ).filter(DeviceToken.device_type == device_type.value)
        
        if hostel_id:
            base_query = base_query.filter(Notification.hostel_id == hostel_id)
        
        # Basic metrics
        total_push = base_query.count()
        delivered_push = base_query.filter(PushNotification.delivered == True).count()
        tapped_push = base_query.filter(PushNotification.tapped == True).count()
        failed_push = base_query.filter(PushNotification.error_code.isnot(None)).count()
        
        # Platform breakdown
        platform_stats = self.db_session.query(
            DeviceToken.device_type,
            func.count().label('total'),
            func.sum(case([(PushNotification.delivered == True, 1)], else_=0)).label('delivered'),
            func.sum(case([(PushNotification.tapped == True, 1)], else_=0)).label('tapped'),
            func.sum(case([(PushNotification.error_code.isnot(None), 1)], else_=0)).label('failed')
        ).join(
            PushNotification, DeviceToken.id == PushNotification.device_token_id
        ).join(
            Notification, PushNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        ).group_by(DeviceToken.device_type).all()
        
        # Calculate rates
        delivery_rate = (delivered_push / total_push * 100) if total_push > 0 else 0
        tap_rate = (tapped_push / delivered_push * 100) if delivered_push > 0 else 0
        failure_rate = (failed_push / total_push * 100) if total_push > 0 else 0
        
        return {
            'total_push': total_push,
            'delivered': delivered_push,
            'tapped': tapped_push,
            'failed': failed_push,
            'delivery_rate': round(delivery_rate, 2),
            'tap_rate': round(tap_rate, 2),
            'failure_rate': round(failure_rate, 2),
            'platform_breakdown': [
                {
                    'platform': stat.device_type,
                    'total': stat.total,
                    'delivered': stat.delivered,
                    'tapped': stat.tapped,
                    'failed': stat.failed,
                    'delivery_rate': (stat.delivered / stat.total * 100) if stat.total > 0 else 0,
                    'tap_rate': (stat.tapped / stat.delivered * 100) if stat.delivered > 0 else 0
                }
                for stat in platform_stats
            ]
        }

    def get_engagement_trends(
        self,
        days: int = 30,
        group_by: str = 'day'
    ) -> List[Dict[str, Any]]:
        """Get push notification engagement trends."""
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        if group_by == 'hour':
            date_trunc = func.date_trunc('hour', Notification.created_at)
        elif group_by == 'day':
            date_trunc = func.date_trunc('day', Notification.created_at)
        else:  # week
            date_trunc = func.date_trunc('week', Notification.created_at)
        
        results = self.db_session.query(
            date_trunc.label('period'),
            func.count().label('total_sent'),
            func.sum(case([(PushNotification.delivered == True, 1)], else_=0)).label('delivered'),
            func.sum(case([(PushNotification.tapped == True, 1)], else_=0)).label('tapped'),
            func.avg(
                func.extract('epoch',
                    PushNotification.tapped_at - Notification.delivered_at
                )
            ).label('avg_time_to_tap')
        ).join(
            Notification, PushNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        ).group_by(date_trunc).order_by(date_trunc).all()
        
        trends = []
        for result in results:
            delivered = result.delivered or 0
            total = result.total_sent or 1
            
            trends.append({
                'period': result.period.isoformat(),
                'total_sent': result.total_sent,
                'delivered': delivered,
                'tapped': result.tapped or 0,
                'delivery_rate': (delivered / total * 100),
                'tap_rate': ((result.tapped or 0) / delivered * 100) if delivered > 0 else 0,
                'avg_time_to_tap_seconds': result.avg_time_to_tap or 0
            })
        
        return trends

    def get_action_analytics(self) -> List[Dict[str, Any]]:
        """Analyze push notification action button usage."""
        action_stats = self.db_session.query(
            PushNotification.action_taken,
            func.count().label('count')
        ).filter(
            and_(
                PushNotification.action_taken.isnot(None),
                PushNotification.tapped == True
            )
        ).group_by(
            PushNotification.action_taken
        ).order_by(desc('count')).all()
        
        total_taps = self.db_session.query(func.count(PushNotification.id)).filter(
            PushNotification.tapped == True
        ).scalar()
        
        return [
            {
                'action': stat.action_taken,
                'count': stat.count,
                'percentage': (stat.count / total_taps * 100) if total_taps > 0 else 0
            }
            for stat in action_stats
        ]

    # Device and platform analytics
    def get_device_performance(self) -> Dict[str, Any]:
        """Analyze performance by device type and platform."""
        device_stats = self.db_session.query(
            DeviceToken.device_type,
            DeviceToken.os_version,
            func.count().label('total_notifications'),
            func.sum(case([(PushNotification.delivered == True, 1)], else_=0)).label('delivered'),
            func.sum(case([(PushNotification.tapped == True, 1)], else_=0)).label('tapped'),
            func.sum(case([(PushNotification.error_code.isnot(None), 1)], else_=0)).label('failed')
        ).join(
            PushNotification, DeviceToken.id == PushNotification.device_token_id
        ).group_by(
            DeviceToken.device_type,
            DeviceToken.os_version
        ).all()
        
        return {
            'device_performance': [
                {
                    'device_type': stat.device_type,
                    'os_version': stat.os_version,
                    'total_notifications': stat.total_notifications,
                    'delivered': stat.delivered,
                    'tapped': stat.tapped,
                    'failed': stat.failed,
                    'delivery_rate': (stat.delivered / stat.total_notifications * 100) if stat.total_notifications > 0 else 0,
                    'tap_rate': (stat.tapped / stat.delivered * 100) if stat.delivered > 0 else 0
                }
                for stat in device_stats
            ]
        }

    def get_optimal_timing_analysis(self) -> Dict[str, Any]:
        """Analyze optimal timing for push notifications."""
        # Hour of day analysis
        hourly_stats = self.db_session.query(
            func.extract('hour', Notification.created_at).label('hour'),
            func.count().label('total_sent'),
            func.sum(case([(PushNotification.tapped == True, 1)], else_=0)).label('tapped'),
            func.avg(
                func.extract('epoch',
                    PushNotification.tapped_at - Notification.delivered_at
                )
            ).label('avg_time_to_tap')
        ).join(
            Notification, PushNotification.notification_id == Notification.id
        ).filter(
            PushNotification.delivered == True
        ).group_by(
            func.extract('hour', Notification.created_at)
        ).order_by('hour').all()
        
        # Day of week analysis
        daily_stats = self.db_session.query(
            func.extract('dow', Notification.created_at).label('day_of_week'),
            func.count().label('total_sent'),
            func.sum(case([(PushNotification.tapped == True, 1)], else_=0)).label('tapped')
        ).join(
            Notification, PushNotification.notification_id == Notification.id
        ).filter(
            PushNotification.delivered == True
        ).group_by(
            func.extract('dow', Notification.created_at)
        ).order_by('day_of_week').all()
        
        return {
            'hourly_performance': [
                {
                    'hour': int(stat.hour),
                    'total_sent': stat.total_sent,
                    'tapped': stat.tapped,
                    'tap_rate': (stat.tapped / stat.total_sent * 100) if stat.total_sent > 0 else 0,
                    'avg_time_to_tap': stat.avg_time_to_tap or 0
                }
                for stat in hourly_stats
            ],
            'daily_performance': [
                {
                    'day_of_week': int(stat.day_of_week),
                    'total_sent': stat.total_sent,
                    'tapped': stat.tapped,
                    'tap_rate': (stat.tapped / stat.total_sent * 100) if stat.total_sent > 0 else 0
                }
                for stat in daily_stats
            ]
        }

    # Maintenance and optimization
    def cleanup_old_push_data(
        self,
        retention_days: int = 180,
        batch_size: int = 1000
    ) -> int:
        """Clean up old push notification data."""
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        old_push_ids = self.db_session.query(PushNotification.id).join(
            Notification, PushNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at < cutoff_date,
                Notification.status.in_([
                    NotificationStatus.DELIVERED,
                    NotificationStatus.FAILED,
                    NotificationStatus.COMPLETED
                ])
            )
        ).limit(batch_size).all()
        
        if not old_push_ids:
            return 0
        
        push_ids = [push.id for push in old_push_ids]
        
        deleted_count = self.db_session.query(PushNotification).filter(
            PushNotification.id.in_(push_ids)
        ).delete(synchronize_session=False)
        
        self.db_session.commit()
        return deleted_count

    def find_failed_deliveries_for_retry(
        self,
        error_codes: List[str],
        hours_since_failure: int = 1
    ) -> List[PushNotification]:
        """Find failed push notifications eligible for retry."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_since_failure)
        
        return self.db_session.query(PushNotification).join(
            Notification, PushNotification.notification_id == Notification.id
        ).filter(
            and_(
                PushNotification.error_code.in_(error_codes),
                Notification.failed_at >= cutoff_time,
                Notification.retry_count < Notification.max_retries
            )
        ).all()

    def get_provider_error_analysis(self) -> List[Dict[str, Any]]:
        """Analyze push notification errors by provider."""
        error_stats = self.db_session.query(
            PushNotification.error_code,
            PushNotification.error_message,
            DeviceToken.device_type,
            func.count().label('error_count'),
            func.max(Notification.failed_at).label('last_occurrence')
        ).join(
            Notification, PushNotification.notification_id == Notification.id
        ).join(
            DeviceToken, PushNotification.device_token_id == DeviceToken.id
        ).filter(
            PushNotification.error_code.isnot(None)
        ).group_by(
            PushNotification.error_code,
            PushNotification.error_message,
            DeviceToken.device_type
        ).order_by(desc('error_count')).all()
        
        return [
            {
                'error_code': stat.error_code,
                'error_message': stat.error_message,
                'device_type': stat.device_type,
                'error_count': stat.error_count,
                'last_occurrence': stat.last_occurrence.isoformat() if stat.last_occurrence else None
            }
            for stat in error_stats
        ]
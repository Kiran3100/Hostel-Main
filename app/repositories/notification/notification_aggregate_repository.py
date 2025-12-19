# --- File: C:\Hostel-Main\app\repositories\notification\notification_aggregate_repository.py ---
"""
Notification Aggregate Repository for cross-module analytics and reporting.

Provides comprehensive notification analytics, performance metrics, and insights
across all notification channels with advanced reporting capabilities.
"""

from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from decimal import Decimal

from sqlalchemy import and_, or_, func, desc, asc, case, text, distinct
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql import select

from app.models.notification.notification import Notification, NotificationReadReceipt
from app.models.notification.email_notification import EmailNotification, EmailClickEvent
from app.models.notification.sms_notification import SMSNotification
from app.models.notification.push_notification import PushNotification
from app.models.notification.notification_template import NotificationTemplate
from app.models.notification.notification_queue import NotificationQueue, NotificationBatch
from app.models.notification.device_token import DeviceToken
from app.models.user.user import User
from app.models.hostel.hostel import Hostel
from app.repositories.base.base_repository import BaseRepository
from app.schemas.common.enums import NotificationStatus, NotificationType, Priority


class NotificationAggregateRepository:
    """
    Aggregate repository for cross-notification analytics and reporting.
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session

    # Executive dashboard metrics
    def get_executive_dashboard(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_ids: Optional[List[UUID]] = None
    ) -> Dict[str, Any]:
        """Get high-level executive dashboard metrics."""
        base_query = self.db_session.query(Notification).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_ids:
            base_query = base_query.filter(Notification.hostel_id.in_(hostel_ids))
        
        # Overall statistics
        total_notifications = base_query.count()
        delivered_notifications = base_query.filter(
            Notification.status.in_([NotificationStatus.DELIVERED, NotificationStatus.COMPLETED])
        ).count()
        read_notifications = base_query.filter(
            Notification.read_at.isnot(None)
        ).count()
        
        # Channel breakdown
        channel_stats = base_query.with_entities(
            Notification.notification_type,
            func.count().label('total'),
            func.sum(
                case([(Notification.status.in_([NotificationStatus.DELIVERED, NotificationStatus.COMPLETED]), 1)], else_=0)
            ).label('delivered'),
            func.sum(
                case([(Notification.read_at.isnot(None), 1)], else_=0)
            ).label('read')
        ).group_by(Notification.notification_type).all()
        
        # Cost analysis (SMS costs)
        sms_cost_query = self.db_session.query(
            func.sum(SMSNotification.cost * SMSNotification.segments_count).label('total_sms_cost')
        ).join(Notification, SMSNotification.notification_id == Notification.id).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_ids:
            sms_cost_query = sms_cost_query.filter(Notification.hostel_id.in_(hostel_ids))
        
        total_sms_cost = sms_cost_query.scalar() or 0
        
        # Performance metrics
        avg_delivery_time = base_query.filter(
            and_(
                Notification.sent_at.isnot(None),
                Notification.delivered_at.isnot(None)
            )
        ).with_entities(
            func.avg(
                func.extract('epoch', Notification.delivered_at - Notification.sent_at)
            )
        ).scalar() or 0
        
        return {
            'summary': {
                'total_notifications': total_notifications,
                'delivered_notifications': delivered_notifications,
                'read_notifications': read_notifications,
                'delivery_rate': (delivered_notifications / total_notifications * 100) if total_notifications > 0 else 0,
                'read_rate': (read_notifications / delivered_notifications * 100) if delivered_notifications > 0 else 0,
                'total_sms_cost': float(total_sms_cost),
                'avg_delivery_time_seconds': avg_delivery_time
            },
            'channel_performance': [
                {
                    'channel': stat.notification_type.value,
                    'total': stat.total,
                    'delivered': stat.delivered,
                    'read': stat.read,
                    'delivery_rate': (stat.delivered / stat.total * 100) if stat.total > 0 else 0,
                    'read_rate': (stat.read / stat.delivered * 100) if stat.delivered > 0 else 0
                }
                for stat in channel_stats
            ]
        }

    def get_comprehensive_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None,
        group_by: str = 'day'
    ) -> Dict[str, Any]:
        """Get comprehensive notification analytics across all channels."""
        # Time series data
        if group_by == 'hour':
            date_trunc = func.date_trunc('hour', Notification.created_at)
        elif group_by == 'day':
            date_trunc = func.date_trunc('day', Notification.created_at)
        elif group_by == 'week':
            date_trunc = func.date_trunc('week', Notification.created_at)
        else:  # month
            date_trunc = func.date_trunc('month', Notification.created_at)
        
        base_query = self.db_session.query(Notification).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_id:
            base_query = base_query.filter(Notification.hostel_id == hostel_id)
        
        # Time series analytics
        time_series = base_query.with_entities(
            date_trunc.label('period'),
            Notification.notification_type,
            func.count().label('total_sent'),
            func.sum(
                case([(Notification.status.in_([NotificationStatus.DELIVERED, NotificationStatus.COMPLETED]), 1)], else_=0)
            ).label('delivered'),
            func.sum(
                case([(Notification.read_at.isnot(None), 1)], else_=0)
            ).label('read'),
            func.sum(
                case([(Notification.clicked_at.isnot(None), 1)], else_=0)
            ).label('clicked')
        ).group_by(
            date_trunc,
            Notification.notification_type
        ).order_by(date_trunc).all()
        
        # Email specific analytics
        email_analytics = self._get_email_analytics(start_date, end_date, hostel_id)
        
        # SMS specific analytics
        sms_analytics = self._get_sms_analytics(start_date, end_date, hostel_id)
        
        # Push specific analytics
        push_analytics = self._get_push_analytics(start_date, end_date, hostel_id)
        
        # User engagement patterns
        user_engagement = self._get_user_engagement_patterns(start_date, end_date, hostel_id)
        
        # Template performance
        template_performance = self._get_template_performance(start_date, end_date, hostel_id)
        
        return {
            'time_series': [
                {
                    'period': ts.period.isoformat(),
                    'channel': ts.notification_type.value,
                    'total_sent': ts.total_sent,
                    'delivered': ts.delivered,
                    'read': ts.read,
                    'clicked': ts.clicked,
                    'delivery_rate': (ts.delivered / ts.total_sent * 100) if ts.total_sent > 0 else 0,
                    'read_rate': (ts.read / ts.delivered * 100) if ts.delivered > 0 else 0,
                    'click_rate': (ts.clicked / ts.delivered * 100) if ts.delivered > 0 else 0
                }
                for ts in time_series
            ],
            'email_analytics': email_analytics,
            'sms_analytics': sms_analytics,
            'push_analytics': push_analytics,
            'user_engagement': user_engagement,
            'template_performance': template_performance
        }

    def get_performance_benchmarks(
        self,
        comparison_period_days: int = 30,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get performance benchmarks and comparisons."""
        end_date = datetime.utcnow()
        current_start = end_date - timedelta(days=comparison_period_days)
        previous_start = current_start - timedelta(days=comparison_period_days)
        
        def get_period_metrics(start: datetime, end: datetime) -> Dict[str, Any]:
            query = self.db_session.query(Notification).filter(
                and_(
                    Notification.created_at >= start,
                    Notification.created_at <= end
                )
            )
            
            if hostel_id:
                query = query.filter(Notification.hostel_id == hostel_id)
            
            total = query.count()
            delivered = query.filter(
                Notification.status.in_([NotificationStatus.DELIVERED, NotificationStatus.COMPLETED])
            ).count()
            read = query.filter(Notification.read_at.isnot(None)).count()
            
            # Average delivery time
            avg_delivery = query.filter(
                and_(
                    Notification.sent_at.isnot(None),
                    Notification.delivered_at.isnot(None)
                )
            ).with_entities(
                func.avg(func.extract('epoch', Notification.delivered_at - Notification.sent_at))
            ).scalar() or 0
            
            return {
                'total': total,
                'delivered': delivered,
                'read': read,
                'delivery_rate': (delivered / total * 100) if total > 0 else 0,
                'read_rate': (read / delivered * 100) if delivered > 0 else 0,
                'avg_delivery_time': avg_delivery
            }
        
        current_metrics = get_period_metrics(current_start, end_date)
        previous_metrics = get_period_metrics(previous_start, current_start)
        
        # Calculate changes
        def calculate_change(current: float, previous: float) -> Dict[str, Any]:
            if previous == 0:
                return {'value': current, 'change_percent': 0, 'trend': 'stable'}
            
            change_percent = ((current - previous) / previous) * 100
            trend = 'up' if change_percent > 5 else 'down' if change_percent < -5 else 'stable'
            
            return {
                'value': current,
                'change_percent': round(change_percent, 2),
                'trend': trend
            }
        
        return {
            'current_period': current_metrics,
            'previous_period': previous_metrics,
            'comparisons': {
                'delivery_rate': calculate_change(
                    current_metrics['delivery_rate'],
                    previous_metrics['delivery_rate']
                ),
                'read_rate': calculate_change(
                    current_metrics['read_rate'],
                    previous_metrics['read_rate']
                ),
                'volume': calculate_change(
                    current_metrics['total'],
                    previous_metrics['total']
                ),
                'avg_delivery_time': calculate_change(
                    current_metrics['avg_delivery_time'],
                    previous_metrics['avg_delivery_time']
                )
            }
        }

    def get_user_segmentation_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Analyze user segments based on notification engagement."""
        base_query = self.db_session.query(
            Notification.recipient_user_id,
            func.count().label('notifications_received'),
            func.sum(case([(Notification.read_at.isnot(None), 1)], else_=0)).label('notifications_read'),
            func.sum(case([(Notification.clicked_at.isnot(None), 1)], else_=0)).label('notifications_clicked'),
            func.max(Notification.read_at).label('last_engagement')
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date,
                Notification.recipient_user_id.isnot(None)
            )
        )
        
        if hostel_id:
            base_query = base_query.filter(Notification.hostel_id == hostel_id)
        
        user_stats = base_query.group_by(Notification.recipient_user_id).all()
        
        # Segment users
        highly_engaged = []
        moderately_engaged = []
        low_engaged = []
        inactive = []
        
        for stat in user_stats:
            read_rate = (stat.notifications_read / stat.notifications_received * 100) if stat.notifications_received > 0 else 0
            
            if read_rate >= 80 and stat.notifications_clicked > 0:
                highly_engaged.append(stat.recipient_user_id)
            elif read_rate >= 50:
                moderately_engaged.append(stat.recipient_user_id)
            elif read_rate >= 20:
                low_engaged.append(stat.recipient_user_id)
            else:
                inactive.append(stat.recipient_user_id)
        
        return {
            'segment_counts': {
                'highly_engaged': len(highly_engaged),
                'moderately_engaged': len(moderately_engaged),
                'low_engaged': len(low_engaged),
                'inactive': len(inactive),
                'total_users': len(user_stats)
            },
            'engagement_distribution': [
                {'segment': 'Highly Engaged (80%+ read, clicks)', 'count': len(highly_engaged), 'percentage': len(highly_engaged) / len(user_stats) * 100 if user_stats else 0},
                {'segment': 'Moderately Engaged (50%+ read)', 'count': len(moderately_engaged), 'percentage': len(moderately_engaged) / len(user_stats) * 100 if user_stats else 0},
                {'segment': 'Low Engaged (20%+ read)', 'count': len(low_engaged), 'percentage': len(low_engaged) / len(user_stats) * 100 if user_stats else 0},
                {'segment': 'Inactive (<20% read)', 'count': len(inactive), 'percentage': len(inactive) / len(user_stats) * 100 if user_stats else 0}
            ]
        }

    def get_cost_analysis_report(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_ids: Optional[List[UUID]] = None
    ) -> Dict[str, Any]:
        """Generate comprehensive cost analysis report."""
        # SMS costs
        sms_cost_query = self.db_session.query(
            func.sum(SMSNotification.cost * SMSNotification.segments_count).label('total_cost'),
            func.count().label('total_sms'),
            func.sum(SMSNotification.segments_count).label('total_segments'),
            func.avg(SMSNotification.cost).label('avg_cost_per_segment')
        ).join(
            Notification, SMSNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_ids:
            sms_cost_query = sms_cost_query.filter(Notification.hostel_id.in_(hostel_ids))
        
        sms_costs = sms_cost_query.first()
        
        # Email costs (estimated based on volume and provider rates)
        email_volume = self.db_session.query(func.count()).select_from(EmailNotification).join(
            Notification, EmailNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_ids:
            email_volume = email_volume.filter(Notification.hostel_id.in_(hostel_ids))
        
        email_count = email_volume.scalar()
        
        # Push notification costs (minimal, mostly infrastructure)
        push_volume = self.db_session.query(func.count()).select_from(PushNotification).join(
            Notification, PushNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_ids:
            push_volume = push_volume.filter(Notification.hostel_id.in_(hostel_ids))
        
        push_count = push_volume.scalar()
        
        # Estimated costs (you'd configure these based on your providers)
        EMAIL_COST_PER_1000 = 0.10  # $0.10 per 1000 emails
        PUSH_COST_PER_1000 = 0.05   # $0.05 per 1000 push notifications
        
        estimated_email_cost = (email_count / 1000) * EMAIL_COST_PER_1000
        estimated_push_cost = (push_count / 1000) * PUSH_COST_PER_1000
        
        total_estimated_cost = float(sms_costs.total_cost or 0) + estimated_email_cost + estimated_push_cost
        
        return {
            'sms_costs': {
                'total_cost': float(sms_costs.total_cost or 0),
                'total_messages': sms_costs.total_sms or 0,
                'total_segments': sms_costs.total_segments or 0,
                'avg_cost_per_segment': float(sms_costs.avg_cost_per_segment or 0),
                'avg_cost_per_message': float((sms_costs.total_cost or 0) / (sms_costs.total_sms or 1))
            },
            'email_costs': {
                'estimated_cost': estimated_email_cost,
                'total_emails': email_count,
                'cost_per_email': estimated_email_cost / email_count if email_count > 0 else 0
            },
            'push_costs': {
                'estimated_cost': estimated_push_cost,
                'total_notifications': push_count,
                'cost_per_notification': estimated_push_cost / push_count if push_count > 0 else 0
            },
            'total_estimated_cost': total_estimated_cost,
            'cost_per_delivered_notification': total_estimated_cost / (sms_costs.total_sms + email_count + push_count) if (sms_costs.total_sms + email_count + push_count) > 0 else 0
        }

    # Helper methods for specific analytics
    def _get_email_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get email-specific analytics."""
        query = self.db_session.query(EmailNotification).join(
            Notification, EmailNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_id:
            query = query.filter(Notification.hostel_id == hostel_id)
        
        stats = query.with_entities(
            func.count().label('total_emails'),
            func.sum(case([(EmailNotification.opened == True, 1)], else_=0)).label('opened'),
            func.sum(case([(EmailNotification.clicked == True, 1)], else_=0)).label('clicked'),
            func.sum(case([(EmailNotification.bounced == True, 1)], else_=0)).label('bounced'),
            func.avg(EmailNotification.open_count).label('avg_opens_per_email')
        ).first()
        
        return {
            'total_emails': stats.total_emails or 0,
            'opened': stats.opened or 0,
            'clicked': stats.clicked or 0,
            'bounced': stats.bounced or 0,
            'open_rate': (stats.opened / stats.total_emails * 100) if stats.total_emails > 0 else 0,
            'click_rate': (stats.clicked / stats.total_emails * 100) if stats.total_emails > 0 else 0,
            'bounce_rate': (stats.bounced / stats.total_emails * 100) if stats.total_emails > 0 else 0,
            'avg_opens_per_email': float(stats.avg_opens_per_email or 0)
        }

    def _get_sms_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get SMS-specific analytics."""
        query = self.db_session.query(SMSNotification).join(
            Notification, SMSNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_id:
            query = query.filter(Notification.hostel_id == hostel_id)
        
        stats = query.with_entities(
            func.count().label('total_sms'),
            func.sum(case([(SMSNotification.delivered == True, 1)], else_=0)).label('delivered'),
            func.sum(SMSNotification.segments_count).label('total_segments'),
            func.sum(SMSNotification.cost * SMSNotification.segments_count).label('total_cost'),
            func.avg(SMSNotification.character_count).label('avg_characters')
        ).first()
        
        return {
            'total_sms': stats.total_sms or 0,
            'delivered': stats.delivered or 0,
            'total_segments': stats.total_segments or 0,
            'total_cost': float(stats.total_cost or 0),
            'delivery_rate': (stats.delivered / stats.total_sms * 100) if stats.total_sms > 0 else 0,
            'avg_characters': float(stats.avg_characters or 0),
            'avg_segments_per_sms': (stats.total_segments / stats.total_sms) if stats.total_sms > 0 else 0
        }

    def _get_push_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get push notification-specific analytics."""
        query = self.db_session.query(PushNotification).join(
            Notification, PushNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_id:
            query = query.filter(Notification.hostel_id == hostel_id)
        
        stats = query.with_entities(
            func.count().label('total_push'),
            func.sum(case([(PushNotification.delivered == True, 1)], else_=0)).label('delivered'),
            func.sum(case([(PushNotification.tapped == True, 1)], else_=0)).label('tapped')
        ).first()
        
        return {
            'total_push': stats.total_push or 0,
            'delivered': stats.delivered or 0,
            'tapped': stats.tapped or 0,
            'delivery_rate': (stats.delivered / stats.total_push * 100) if stats.total_push > 0 else 0,
            'tap_rate': (stats.tapped / stats.delivered * 100) if stats.delivered > 0 else 0
        }

    def _get_user_engagement_patterns(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get user engagement patterns."""
        # Hour of day analysis
        hourly_engagement = self.db_session.query(
            func.extract('hour', Notification.read_at).label('hour'),
            func.count().label('read_count')
        ).filter(
            and_(
                Notification.read_at >= start_date,
                Notification.read_at <= end_date,
                Notification.read_at.isnot(None)
            )
        )
        
        if hostel_id:
            hourly_engagement = hourly_engagement.filter(Notification.hostel_id == hostel_id)
        
        hourly_stats = hourly_engagement.group_by(
            func.extract('hour', Notification.read_at)
        ).all()
        
        return {
            'hourly_engagement': [
                {'hour': int(stat.hour), 'read_count': stat.read_count}
                for stat in hourly_stats
            ]
        }

    def _get_template_performance(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> List[Dict[str, Any]]:
        """Get template performance metrics."""
        query = self.db_session.query(
            NotificationTemplate.template_code,
            NotificationTemplate.template_name,
            func.count().label('usage_count'),
            func.sum(case([(Notification.read_at.isnot(None), 1)], else_=0)).label('read_count'),
            func.sum(case([(Notification.clicked_at.isnot(None), 1)], else_=0)).label('click_count')
        ).join(
            Notification, NotificationTemplate.id == Notification.template_id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_id:
            query = query.filter(Notification.hostel_id == hostel_id)
        
        template_stats = query.group_by(
            NotificationTemplate.template_code,
            NotificationTemplate.template_name
        ).order_by(desc('usage_count')).limit(10).all()
        
        return [
            {
                'template_code': stat.template_code,
                'template_name': stat.template_name,
                'usage_count': stat.usage_count,
                'read_count': stat.read_count,
                'click_count': stat.click_count,
                'read_rate': (stat.read_count / stat.usage_count * 100) if stat.usage_count > 0 else 0,
                'click_rate': (stat.click_count / stat.usage_count * 100) if stat.usage_count > 0 else 0
            }
            for stat in template_stats
        ]

    def export_analytics_data(
        self,
        start_date: datetime,
        end_date: datetime,
        format: str = 'csv',
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Export analytics data for external analysis."""
        analytics_data = self.get_comprehensive_analytics(
            start_date, end_date, hostel_id, 'day'
        )
        
        # Format for export
        export_data = {
            'metadata': {
                'export_date': datetime.utcnow().isoformat(),
                'period_start': start_date.isoformat(),
                'period_end': end_date.isoformat(),
                'hostel_id': str(hostel_id) if hostel_id else 'all',
                'format': format
            },
            'data': analytics_data
        }
        
        return export_data
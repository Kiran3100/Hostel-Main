# --- File: C:\Hostel-Main\app\repositories\notification\sms_notification_repository.py ---
"""
SMS Notification Repository with delivery tracking and cost analytics.

Handles SMS-specific operations including delivery confirmation, cost tracking,
DLT compliance, and provider performance monitoring.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from decimal import Decimal

from sqlalchemy import and_, or_, func, desc, asc, case, text
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.sql import select

from app.models.notification.sms_notification import SMSNotification
from app.models.notification.notification import Notification
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.specifications import Specification
from app.repositories.base.pagination import PaginationParams, PaginatedResult


class DeliveredSMSSpec(Specification):
    """Specification for successfully delivered SMS."""
    
    def is_satisfied_by(self, query):
        return query.filter(SMSNotification.delivered == True)


class HighCostSMSSpec(Specification):
    """Specification for high-cost SMS messages."""
    
    def __init__(self, min_cost: Decimal):
        self.min_cost = min_cost
    
    def is_satisfied_by(self, query):
        return query.filter(SMSNotification.cost >= self.min_cost)


class SMSNotificationRepository(BaseRepository[SMSNotification]):
    """
    Repository for SMS notification management with cost and delivery tracking.
    """

    def __init__(self, db_session: Session):
        super().__init__(SMSNotification, db_session)

    # Core SMS operations
    def create_sms_with_details(
        self,
        notification: Notification,
        sms_data: Dict[str, Any]
    ) -> SMSNotification:
        """Create SMS notification with automatic segment calculation."""
        # Calculate segments based on message length
        message_text = sms_data.get('message_text', '')
        character_count = len(message_text)
        
        # Standard SMS segment calculation (160 chars for GSM-7, 70 for Unicode)
        encoding = sms_data.get('encoding', 'GSM-7')
        if encoding == 'Unicode':
            segment_length = 67  # 70 chars minus UDH for concatenated SMS
            sms_data['segments_count'] = (character_count + segment_length - 1) // segment_length
        else:
            segment_length = 153  # 160 chars minus UDH for concatenated SMS
            sms_data['segments_count'] = (character_count + segment_length - 1) // segment_length
        
        sms_data['character_count'] = character_count
        
        sms_notification = SMSNotification(
            notification_id=notification.id,
            **sms_data
        )
        
        return self.create(sms_notification)

    def find_by_notification_id(self, notification_id: UUID) -> Optional[SMSNotification]:
        """Find SMS by notification ID."""
        return self.db_session.query(SMSNotification).filter(
            SMSNotification.notification_id == notification_id
        ).options(
            joinedload(SMSNotification.notification)
        ).first()

    def find_by_provider_message_id(
        self,
        provider_name: str,
        provider_message_id: str
    ) -> Optional[SMSNotification]:
        """Find SMS by provider message ID."""
        return self.db_session.query(SMSNotification).filter(
            and_(
                SMSNotification.provider_name == provider_name,
                SMSNotification.provider_message_id == provider_message_id
            )
        ).first()

    def find_pending_delivery_reports(self, limit: int = 1000) -> List[SMSNotification]:
        """Find SMS messages pending delivery confirmation."""
        return self.db_session.query(SMSNotification).join(
            Notification, SMSNotification.notification_id == Notification.id
        ).filter(
            and_(
                SMSNotification.delivered == False,
                SMSNotification.error_code.is_(None),
                Notification.status.in_(['SENT', 'PROCESSING'])
            )
        ).limit(limit).all()

    # Delivery tracking
    def update_delivery_status(
        self,
        sms_id: UUID,
        delivered: bool,
        delivery_status: str,
        provider_response: Optional[Dict[str, Any]] = None,
        error_details: Optional[Dict[str, str]] = None
    ) -> bool:
        """Update SMS delivery status."""
        sms = self.find_by_id(sms_id)
        if not sms:
            return False
        
        sms.delivered = delivered
        sms.delivery_status = delivery_status
        
        if provider_response:
            sms.provider_response = provider_response
        
        if error_details:
            sms.error_code = error_details.get('code')
            sms.error_message = error_details.get('message')
        
        # Update related notification status
        if sms.notification:
            if delivered:
                sms.notification.status = NotificationStatus.DELIVERED
                if not sms.notification.delivered_at:
                    sms.notification.delivered_at = datetime.utcnow()
            elif error_details:
                sms.notification.status = NotificationStatus.FAILED
                sms.notification.failed_at = datetime.utcnow()
                sms.notification.failure_reason = error_details.get('message')
        
        self.db_session.commit()
        return True

    def bulk_update_delivery_status(
        self,
        status_updates: List[Dict[str, Any]]
    ) -> int:
        """Bulk update delivery status for multiple SMS."""
        updated_count = 0
        
        for update in status_updates:
            if self.update_delivery_status(**update):
                updated_count += 1
        
        return updated_count

    # Cost tracking and analytics
    def get_cost_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get comprehensive SMS cost analytics."""
        base_query = self.db_session.query(SMSNotification).join(
            Notification, SMSNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_id:
            base_query = base_query.filter(Notification.hostel_id == hostel_id)
        
        # Cost calculations
        cost_stats = base_query.with_entities(
            func.count().label('total_sms'),
            func.sum(SMSNotification.segments_count).label('total_segments'),
            func.sum(SMSNotification.cost * SMSNotification.segments_count).label('total_cost'),
            func.avg(SMSNotification.cost).label('avg_cost_per_segment'),
            func.sum(case([(SMSNotification.delivered == True, 1)], else_=0)).label('delivered_count')
        ).first()
        
        # Provider breakdown
        provider_stats = base_query.with_entities(
            SMSNotification.provider_name,
            func.count().label('count'),
            func.sum(SMSNotification.cost * SMSNotification.segments_count).label('provider_cost'),
            func.sum(case([(SMSNotification.delivered == True, 1)], else_=0)).label('delivered')
        ).group_by(SMSNotification.provider_name).all()
        
        total_cost = float(cost_stats.total_cost or 0)
        total_sms = cost_stats.total_sms or 1
        delivered_count = cost_stats.delivered_count or 0
        
        return {
            'total_sms': total_sms,
            'total_segments': cost_stats.total_segments or 0,
            'total_cost': total_cost,
            'average_cost_per_sms': total_cost / total_sms,
            'average_cost_per_segment': float(cost_stats.avg_cost_per_segment or 0),
            'delivery_rate': (delivered_count / total_sms * 100),
            'cost_per_delivery': total_cost / delivered_count if delivered_count > 0 else 0,
            'provider_breakdown': [
                {
                    'provider': stat.provider_name,
                    'count': stat.count,
                    'cost': float(stat.provider_cost or 0),
                    'delivery_rate': (stat.delivered / stat.count * 100) if stat.count > 0 else 0
                }
                for stat in provider_stats
            ]
        }

    def get_delivery_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        group_by: str = 'day'
    ) -> List[Dict[str, Any]]:
        """Get delivery performance analytics over time."""
        if group_by == 'hour':
            date_trunc = func.date_trunc('hour', Notification.created_at)
        elif group_by == 'day':
            date_trunc = func.date_trunc('day', Notification.created_at)
        else:  # week
            date_trunc = func.date_trunc('week', Notification.created_at)
        
        results = self.db_session.query(
            date_trunc.label('period'),
            func.count().label('total_sent'),
            func.sum(case([(SMSNotification.delivered == True, 1)], else_=0)).label('delivered'),
            func.sum(case([(SMSNotification.error_code.isnot(None), 1)], else_=0)).label('failed'),
            func.sum(SMSNotification.segments_count).label('total_segments'),
            func.sum(SMSNotification.cost * SMSNotification.segments_count).label('total_cost')
        ).join(
            Notification, SMSNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        ).group_by(date_trunc).order_by(date_trunc).all()
        
        analytics = []
        for result in results:
            total = result.total_sent or 1
            delivered = result.delivered or 0
            
            analytics.append({
                'period': result.period.isoformat(),
                'total_sent': result.total_sent,
                'delivered': delivered,
                'failed': result.failed or 0,
                'delivery_rate': (delivered / total * 100),
                'total_segments': result.total_segments or 0,
                'total_cost': float(result.total_cost or 0),
                'cost_per_sms': float(result.total_cost or 0) / total
            })
        
        return analytics

    def get_provider_performance(self) -> List[Dict[str, Any]]:
        """Analyze performance by SMS provider."""
        stats = self.db_session.query(
            SMSNotification.provider_name,
            func.count().label('total_messages'),
            func.sum(case([(SMSNotification.delivered == True, 1)], else_=0)).label('delivered'),
            func.sum(case([(SMSNotification.error_code.isnot(None), 1)], else_=0)).label('failed'),
            func.avg(SMSNotification.cost).label('avg_cost'),
            func.avg(
                func.extract('epoch',
                    func.coalesce(Notification.delivered_at, Notification.failed_at) - 
                    Notification.sent_at
                )
            ).label('avg_delivery_time')
        ).join(
            Notification, SMSNotification.notification_id == Notification.id
        ).filter(
            Notification.sent_at.isnot(None)
        ).group_by(SMSNotification.provider_name).all()
        
        return [
            {
                'provider_name': stat.provider_name,
                'total_messages': stat.total_messages,
                'delivered': stat.delivered,
                'failed': stat.failed,
                'delivery_rate': (stat.delivered / stat.total_messages * 100) if stat.total_messages > 0 else 0,
                'failure_rate': (stat.failed / stat.total_messages * 100) if stat.total_messages > 0 else 0,
                'average_cost': float(stat.avg_cost or 0),
                'average_delivery_time_seconds': stat.avg_delivery_time or 0
            }
            for stat in stats
        ]

    # DLT compliance (India-specific)
    def find_messages_by_dlt_template(
        self,
        dlt_template_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[SMSNotification]:
        """Find messages by DLT template for compliance tracking."""
        query = self.db_session.query(SMSNotification).filter(
            SMSNotification.dlt_template_id == dlt_template_id
        )
        
        if start_date and end_date:
            query = query.join(
                Notification, SMSNotification.notification_id == Notification.id
            ).filter(
                and_(
                    Notification.created_at >= start_date,
                    Notification.created_at <= end_date
                )
            )
        
        return query.all()

    def get_dlt_compliance_report(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> Dict[str, Any]:
        """Generate DLT compliance report."""
        total_sms = self.db_session.query(func.count(SMSNotification.id)).join(
            Notification, SMSNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        ).scalar()
        
        dlt_compliant = self.db_session.query(func.count(SMSNotification.id)).join(
            Notification, SMSNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date,
                SMSNotification.dlt_template_id.isnot(None)
            )
        ).scalar()
        
        # Template usage stats
        template_stats = self.db_session.query(
            SMSNotification.dlt_template_id,
            func.count().label('usage_count')
        ).join(
            Notification, SMSNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date,
                SMSNotification.dlt_template_id.isnot(None)
            )
        ).group_by(SMSNotification.dlt_template_id).all()
        
        compliance_rate = (dlt_compliant / total_sms * 100) if total_sms > 0 else 0
        
        return {
            'total_sms': total_sms,
            'dlt_compliant': dlt_compliant,
            'non_compliant': total_sms - dlt_compliant,
            'compliance_rate': round(compliance_rate, 2),
            'template_usage': [
                {
                    'template_id': stat.dlt_template_id,
                    'usage_count': stat.usage_count
                }
                for stat in template_stats
            ]
        }

    # Segment and encoding analytics
    def get_segment_analytics(self) -> Dict[str, Any]:
        """Analyze SMS segmentation patterns."""
        segment_stats = self.db_session.query(
            SMSNotification.segments_count,
            SMSNotification.encoding,
            func.count().label('message_count'),
            func.avg(SMSNotification.character_count).label('avg_characters'),
            func.sum(SMSNotification.cost * SMSNotification.segments_count).label('total_cost')
        ).group_by(
            SMSNotification.segments_count,
            SMSNotification.encoding
        ).order_by(SMSNotification.segments_count).all()
        
        return {
            'segment_distribution': [
                {
                    'segments': stat.segments_count,
                    'encoding': stat.encoding,
                    'message_count': stat.message_count,
                    'average_characters': round(stat.avg_characters or 0, 1),
                    'total_cost': float(stat.total_cost or 0)
                }
                for stat in segment_stats
            ],
            'encoding_summary': self._get_encoding_summary()
        }

    def _get_encoding_summary(self) -> Dict[str, Any]:
        """Get encoding usage summary."""
        encoding_stats = self.db_session.query(
            SMSNotification.encoding,
            func.count().label('count'),
            func.avg(SMSNotification.character_count).label('avg_chars'),
            func.avg(SMSNotification.segments_count).label('avg_segments')
        ).group_by(SMSNotification.encoding).all()
        
        return {
            stat.encoding: {
                'count': stat.count,
                'average_characters': round(stat.avg_chars or 0, 1),
                'average_segments': round(stat.avg_segments or 0, 1)
            }
            for stat in encoding_stats
        }

    # Maintenance and optimization
    def cleanup_old_sms_data(
        self,
        retention_days: int = 365,
        batch_size: int = 1000
    ) -> int:
        """Clean up old SMS data beyond retention period."""
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        old_sms_ids = self.db_session.query(SMSNotification.id).join(
            Notification, SMSNotification.notification_id == Notification.id
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
        
        if not old_sms_ids:
            return 0
        
        sms_ids = [sms.id for sms in old_sms_ids]
        
        deleted_count = self.db_session.query(SMSNotification).filter(
            SMSNotification.id.in_(sms_ids)
        ).delete(synchronize_session=False)
        
        self.db_session.commit()
        return deleted_count

    def find_high_cost_messages(
        self,
        cost_threshold: Decimal,
        days: int = 30
    ) -> List[SMSNotification]:
        """Find unusually expensive SMS messages for review."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        return self.db_session.query(SMSNotification).join(
            Notification, SMSNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= cutoff_date,
                SMSNotification.cost * SMSNotification.segments_count >= cost_threshold
            )
        ).order_by(desc(SMSNotification.cost * SMSNotification.segments_count)).all()
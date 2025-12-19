# --- File: C:\Hostel-Main\app\repositories\notification\email_notification_repository.py ---
"""
Email Notification Repository with engagement tracking and analytics.

Handles email-specific operations including delivery tracking, engagement analytics,
bounce handling, and attachment management.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Tuple
from uuid import UUID
from decimal import Decimal

from sqlalchemy import and_, or_, func, desc, asc, case, text
from sqlalchemy.orm import Session, joinedload, selectinload
from sqlalchemy.sql import select

from app.models.notification.email_notification import (
    EmailNotification,
    EmailAttachment,
    EmailClickEvent
)
from app.models.notification.notification import Notification
from app.repositories.base.base_repository import BaseRepository
from app.repositories.base.specifications import Specification
from app.repositories.base.pagination import PaginationParams, PaginatedResult


class HighEngagementEmailsSpec(Specification):
    """Specification for emails with high engagement rates."""
    
    def __init__(self, min_open_rate: float = 0.8):
        self.min_open_rate = min_open_rate
    
    def is_satisfied_by(self, query):
        return query.filter(EmailNotification.opened == True)


class BouncedEmailsSpec(Specification):
    """Specification for bounced emails requiring cleanup."""
    
    def __init__(self, bounce_types: Optional[List[str]] = None):
        self.bounce_types = bounce_types or ['hard', 'complaint']
    
    def is_satisfied_by(self, query):
        return query.filter(
            and_(
                EmailNotification.bounced == True,
                EmailNotification.bounce_type.in_(self.bounce_types)
            )
        )


class EmailNotificationRepository(BaseRepository[EmailNotification]):
    """
    Repository for email notification management with engagement tracking.
    """

    def __init__(self, db_session: Session):
        super().__init__(EmailNotification, db_session)

    # Core email operations
    def create_email_with_details(
        self,
        notification: Notification,
        email_data: Dict[str, Any],
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> EmailNotification:
        """Create email notification with attachments."""
        email_notification = EmailNotification(
            notification_id=notification.id,
            **email_data
        )
        
        email_notification = self.create(email_notification)
        
        # Add attachments if provided
        if attachments:
            for attachment_data in attachments:
                attachment = EmailAttachment(
                    email_id=email_notification.id,
                    **attachment_data
                )
                self.db_session.add(attachment)
        
        self.db_session.commit()
        return email_notification

    def find_by_notification_id(self, notification_id: UUID) -> Optional[EmailNotification]:
        """Find email by notification ID."""
        return self.db_session.query(EmailNotification).filter(
            EmailNotification.notification_id == notification_id
        ).options(
            joinedload(EmailNotification.attachments),
            joinedload(EmailNotification.notification)
        ).first()

    def find_by_provider_message_id(self, provider_message_id: str) -> Optional[EmailNotification]:
        """Find email by provider message ID."""
        return self.db_session.query(EmailNotification).filter(
            EmailNotification.provider_message_id == provider_message_id
        ).first()

    def find_emails_by_status(
        self,
        delivery_status: str,
        limit: int = 100
    ) -> List[EmailNotification]:
        """Find emails by delivery status."""
        return self.db_session.query(EmailNotification).filter(
            EmailNotification.delivery_status == delivery_status
        ).limit(limit).all()

    # Engagement tracking
    def track_email_open(
        self,
        email_id: UUID,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Track email open event."""
        email = self.find_by_id(email_id)
        if not email:
            return False
        
        now = datetime.utcnow()
        
        if not email.opened:
            email.opened = True
            email.first_opened_at = now
        
        email.last_opened_at = now
        email.open_count += 1
        
        # Update notification read status
        if email.notification and not email.notification.read_at:
            email.notification.read_at = now
        
        self.db_session.commit()
        return True

    def track_email_click(
        self,
        email_id: UUID,
        url: str,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Track email link click."""
        email = self.find_by_id(email_id)
        if not email:
            return False
        
        now = datetime.utcnow()
        
        # Update email click status
        if not email.clicked:
            email.clicked = True
            email.first_clicked_at = now
        
        email.last_clicked_at = now
        email.click_count += 1
        
        # Add to clicked links if not already present
        if url not in email.clicked_links:
            email.clicked_links = email.clicked_links + [url]
        
        # Create click event record
        click_event = EmailClickEvent(
            email_id=email_id,
            url=url,
            clicked_at=now
        )
        
        if context:
            for key, value in context.items():
                if hasattr(click_event, key):
                    setattr(click_event, key, value)
        
        # Update notification click status
        if email.notification and not email.notification.clicked_at:
            email.notification.clicked_at = now
        
        self.db_session.add(click_event)
        self.db_session.commit()
        return True

    def track_email_bounce(
        self,
        email_id: UUID,
        bounce_type: str,
        bounce_reason: str,
        provider_response: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Track email bounce."""
        email = self.find_by_id(email_id)
        if not email:
            return False
        
        email.bounced = True
        email.bounce_type = bounce_type
        email.bounce_reason = bounce_reason
        email.delivery_status = 'bounced'
        
        if provider_response:
            email.provider_response = provider_response
        
        self.db_session.commit()
        return True

    def track_spam_report(
        self,
        email_id: UUID,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Track spam report."""
        email = self.find_by_id(email_id)
        if not email:
            return False
        
        email.marked_as_spam = True
        email.spam_reported_at = datetime.utcnow()
        
        self.db_session.commit()
        return True

    # Analytics and reporting
    def get_engagement_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get comprehensive email engagement analytics."""
        base_query = self.db_session.query(EmailNotification).join(
            Notification, EmailNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        )
        
        if hostel_id:
            base_query = base_query.filter(Notification.hostel_id == hostel_id)
        
        # Basic metrics
        total_emails = base_query.count()
        delivered_emails = base_query.filter(
            EmailNotification.delivery_status == 'delivered'
        ).count()
        opened_emails = base_query.filter(EmailNotification.opened == True).count()
        clicked_emails = base_query.filter(EmailNotification.clicked == True).count()
        bounced_emails = base_query.filter(EmailNotification.bounced == True).count()
        spam_reported = base_query.filter(EmailNotification.marked_as_spam == True).count()
        
        # Calculate rates
        delivery_rate = (delivered_emails / total_emails * 100) if total_emails > 0 else 0
        open_rate = (opened_emails / delivered_emails * 100) if delivered_emails > 0 else 0
        click_rate = (clicked_emails / delivered_emails * 100) if delivered_emails > 0 else 0
        bounce_rate = (bounced_emails / total_emails * 100) if total_emails > 0 else 0
        spam_rate = (spam_reported / delivered_emails * 100) if delivered_emails > 0 else 0
        
        return {
            'total_emails': total_emails,
            'delivered_emails': delivered_emails,
            'opened_emails': opened_emails,
            'clicked_emails': clicked_emails,
            'bounced_emails': bounced_emails,
            'spam_reported': spam_reported,
            'delivery_rate': round(delivery_rate, 2),
            'open_rate': round(open_rate, 2),
            'click_rate': round(click_rate, 2),
            'bounce_rate': round(bounce_rate, 2),
            'spam_rate': round(spam_rate, 2)
        }

    def get_click_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get top clicked URLs analytics."""
        click_stats = self.db_session.query(
            EmailClickEvent.url,
            func.count().label('click_count'),
            func.count(func.distinct(EmailClickEvent.email_id)).label('unique_emails')
        ).join(
            EmailNotification, EmailClickEvent.email_id == EmailNotification.id
        ).join(
            Notification, EmailNotification.notification_id == Notification.id
        ).filter(
            and_(
                EmailClickEvent.clicked_at >= start_date,
                EmailClickEvent.clicked_at <= end_date
            )
        ).group_by(
            EmailClickEvent.url
        ).order_by(
            desc('click_count')
        ).limit(limit).all()
        
        return [
            {
                'url': stat.url,
                'total_clicks': stat.click_count,
                'unique_clicks': stat.unique_emails
            }
            for stat in click_stats
        ]

    def get_delivery_performance(
        self,
        start_date: datetime,
        end_date: datetime,
        group_by: str = 'day'
    ) -> List[Dict[str, Any]]:
        """Get delivery performance trends."""
        if group_by == 'hour':
            date_trunc = func.date_trunc('hour', Notification.created_at)
        elif group_by == 'day':
            date_trunc = func.date_trunc('day', Notification.created_at)
        else:  # week
            date_trunc = func.date_trunc('week', Notification.created_at)
        
        results = self.db_session.query(
            date_trunc.label('period'),
            func.count().label('total_sent'),
            func.sum(
                case([(EmailNotification.delivery_status == 'delivered', 1)], else_=0)
            ).label('delivered'),
            func.sum(
                case([(EmailNotification.opened == True, 1)], else_=0)
            ).label('opened'),
            func.sum(
                case([(EmailNotification.clicked == True, 1)], else_=0)
            ).label('clicked'),
            func.sum(
                case([(EmailNotification.bounced == True, 1)], else_=0)
            ).label('bounced')
        ).join(
            Notification, EmailNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= start_date,
                Notification.created_at <= end_date
            )
        ).group_by(
            date_trunc
        ).order_by(
            date_trunc
        ).all()
        
        trends = []
        for result in results:
            delivered = result.delivered or 0
            total = result.total_sent or 1  # Avoid division by zero
            
            trends.append({
                'period': result.period.isoformat(),
                'total_sent': result.total_sent,
                'delivered': delivered,
                'opened': result.opened or 0,
                'clicked': result.clicked or 0,
                'bounced': result.bounced or 0,
                'delivery_rate': (delivered / total * 100),
                'open_rate': ((result.opened or 0) / delivered * 100) if delivered > 0 else 0,
                'click_rate': ((result.clicked or 0) / delivered * 100) if delivered > 0 else 0
            })
        
        return trends

    # Attachment management
    def add_attachment(
        self,
        email_id: UUID,
        attachment_data: Dict[str, Any]
    ) -> EmailAttachment:
        """Add attachment to email."""
        attachment = EmailAttachment(
            email_id=email_id,
            **attachment_data
        )
        return self.db_session.add(attachment)

    def get_attachment_statistics(self) -> Dict[str, Any]:
        """Get attachment usage statistics."""
        stats = self.db_session.query(
            func.count(EmailAttachment.id).label('total_attachments'),
            func.sum(EmailAttachment.size_bytes).label('total_size'),
            func.avg(EmailAttachment.size_bytes).label('avg_size'),
            func.sum(EmailAttachment.download_count).label('total_downloads')
        ).first()
        
        return {
            'total_attachments': stats.total_attachments or 0,
            'total_size_bytes': int(stats.total_size or 0),
            'average_size_bytes': int(stats.avg_size or 0),
            'total_downloads': stats.total_downloads or 0
        }

    # Maintenance and cleanup
    def cleanup_bounced_emails(
        self,
        hard_bounce_days: int = 30,
        batch_size: int = 1000
    ) -> int:
        """Clean up hard bounced emails older than specified days."""
        cutoff_date = datetime.utcnow() - timedelta(days=hard_bounce_days)
        
        # Find emails to clean up
        emails_to_cleanup = self.db_session.query(EmailNotification.id).join(
            Notification, EmailNotification.notification_id == Notification.id
        ).filter(
            and_(
                EmailNotification.bounced == True,
                EmailNotification.bounce_type == 'hard',
                Notification.created_at < cutoff_date
            )
        ).limit(batch_size).all()
        
        if not emails_to_cleanup:
            return 0
        
        email_ids = [email.id for email in emails_to_cleanup]
        
        # Delete click events
        self.db_session.query(EmailClickEvent).filter(
            EmailClickEvent.email_id.in_(email_ids)
        ).delete(synchronize_session=False)
        
        # Delete attachments
        self.db_session.query(EmailAttachment).filter(
            EmailAttachment.email_id.in_(email_ids)
        ).delete(synchronize_session=False)
        
        # Mark emails for cleanup (soft delete)
        deleted_count = self.db_session.query(EmailNotification).filter(
            EmailNotification.id.in_(email_ids)
        ).delete(synchronize_session=False)
        
        self.db_session.commit()
        return deleted_count

    def find_unengaged_recipients(
        self,
        days: int = 90,
        min_emails: int = 5
    ) -> List[str]:
        """Find email addresses with consistently low engagement."""
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        results = self.db_session.query(
            Notification.recipient_email,
            func.count().label('total_emails'),
            func.sum(case([(EmailNotification.opened == True, 1)], else_=0)).label('opened_emails'),
            func.sum(case([(EmailNotification.clicked == True, 1)], else_=0)).label('clicked_emails')
        ).join(
            Notification, EmailNotification.notification_id == Notification.id
        ).filter(
            and_(
                Notification.created_at >= cutoff_date,
                Notification.recipient_email.isnot(None)
            )
        ).group_by(
            Notification.recipient_email
        ).having(
            and_(
                func.count() >= min_emails,
                func.sum(case([(EmailNotification.opened == True, 1)], else_=0)) == 0
            )
        ).all()
        
        return [result.recipient_email for result in results]

    def get_provider_performance(self) -> List[Dict[str, Any]]:
        """Analyze performance by email provider."""
        # This could analyze different email service providers
        # if multiple providers are used
        stats = self.db_session.query(
            EmailNotification.delivery_status,
            func.count().label('count'),
            func.avg(
                func.extract('epoch', 
                    EmailNotification.first_opened_at - Notification.sent_at
                )
            ).label('avg_time_to_open')
        ).join(
            Notification, EmailNotification.notification_id == Notification.id
        ).filter(
            Notification.sent_at.isnot(None)
        ).group_by(
            EmailNotification.delivery_status
        ).all()
        
        return [
            {
                'delivery_status': stat.delivery_status,
                'count': stat.count,
                'avg_time_to_open_seconds': stat.avg_time_to_open
            }
            for stat in stats
        ]
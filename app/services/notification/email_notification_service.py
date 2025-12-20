# --- File: C:\Hostel-Main\app\services\notification\email_notification_service.py ---
"""
Email Notification Service - Handles email delivery, tracking, and analytics.

Integrates with email service providers (SendGrid, AWS SES, etc.) and manages
email-specific features like attachments, tracking, and bounce handling.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from uuid import UUID
import logging
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

from sqlalchemy.orm import Session

from app.models.notification.notification import Notification
from app.models.notification.email_notification import (
    EmailNotification,
    EmailAttachment,
    EmailClickEvent
)
from app.repositories.notification.email_notification_repository import (
    EmailNotificationRepository
)
from app.repositories.notification.notification_repository import NotificationRepository
from app.schemas.common.enums import NotificationStatus
from app.core.config import settings
from app.core.exceptions import EmailDeliveryError

logger = logging.getLogger(__name__)


class EmailNotificationService:
    """
    Service for email notification delivery and tracking.
    """

    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.email_repo = EmailNotificationRepository(db_session)
        self.notification_repo = NotificationRepository(db_session)
        
        # Initialize email provider based on configuration
        self.email_provider = self._initialize_email_provider()

    def send_email(
        self,
        notification: Notification,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        track_opens: bool = True,
        track_clicks: bool = True,
        reply_to: Optional[str] = None
    ) -> EmailNotification:
        """
        Send email notification with tracking and attachments.
        
        Args:
            notification: Base notification object
            cc_emails: CC recipients
            bcc_emails: BCC recipients
            attachments: List of attachment data
            track_opens: Enable open tracking
            track_clicks: Enable click tracking
            reply_to: Reply-to email address
            
        Returns:
            EmailNotification object with delivery details
        """
        try:
            # Validate email address
            recipient_email = notification.recipient_email
            if not recipient_email:
                # Try to get email from user
                if notification.recipient_user and notification.recipient_user.email:
                    recipient_email = notification.recipient_user.email
                else:
                    raise EmailDeliveryError("No recipient email address")
            
            if not self._validate_email(recipient_email):
                raise EmailDeliveryError(f"Invalid email address: {recipient_email}")
            
            # Prepare email content
            html_body = self._prepare_html_body(
                notification.message_body,
                track_opens,
                track_clicks,
                notification.id
            )
            
            text_body = self._html_to_text(notification.message_body)
            
            # Create email notification record
            email_data = {
                'cc_emails': cc_emails or [],
                'bcc_emails': bcc_emails or [],
                'body_html': html_body,
                'body_text': text_body,
                'reply_to': reply_to or settings.DEFAULT_REPLY_TO_EMAIL,
                'from_name': settings.EMAIL_FROM_NAME,
                'from_email': settings.EMAIL_FROM_ADDRESS,
                'track_opens': track_opens,
                'track_clicks': track_clicks
            }
            
            email_notification = self.email_repo.create_email_with_details(
                notification=notification,
                email_data=email_data,
                attachments=attachments
            )
            
            # Send via email provider
            provider_response = self._send_via_provider(
                to_email=recipient_email,
                cc_emails=cc_emails,
                bcc_emails=bcc_emails,
                subject=notification.subject,
                html_body=html_body,
                text_body=text_body,
                reply_to=reply_to,
                attachments=attachments,
                tracking_id=str(notification.id)
            )
            
            # Update email notification with provider response
            email_notification.provider_message_id = provider_response.get('message_id')
            email_notification.provider_response = provider_response
            email_notification.delivery_status = 'sent'
            
            # Update notification status
            notification.status = NotificationStatus.SENT
            notification.sent_at = datetime.utcnow()
            
            self.db_session.commit()
            
            logger.info(
                f"Email sent successfully: {notification.id} to {recipient_email}"
            )
            
            return email_notification
            
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}", exc_info=True)
            
            # Update notification as failed
            notification.status = NotificationStatus.FAILED
            notification.failed_at = datetime.utcnow()
            notification.failure_reason = str(e)
            
            self.db_session.commit()
            
            raise EmailDeliveryError(f"Failed to send email: {str(e)}")

    def track_email_open(
        self,
        email_id: UUID,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None
    ) -> bool:
        """Track email open event."""
        try:
            context = {
                'ip_address': ip_address,
                'user_agent': user_agent,
                'opened_at': datetime.utcnow().isoformat()
            }
            
            return self.email_repo.track_email_open(email_id, context)
            
        except Exception as e:
            logger.error(f"Error tracking email open: {str(e)}")
            return False

    def track_email_click(
        self,
        email_id: UUID,
        url: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        device_type: Optional[str] = None
    ) -> bool:
        """Track email link click event."""
        try:
            context = {
                'ip_address': ip_address,
                'user_agent': user_agent,
                'device_type': device_type
            }
            
            return self.email_repo.track_email_click(email_id, url, context)
            
        except Exception as e:
            logger.error(f"Error tracking email click: {str(e)}")
            return False

    def handle_bounce(
        self,
        provider_message_id: str,
        bounce_type: str,
        bounce_reason: str,
        provider_response: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Handle email bounce notification from provider."""
        try:
            # Find email by provider message ID
            email = self.email_repo.find_by_provider_message_id(provider_message_id)
            
            if not email:
                logger.warning(
                    f"Email not found for provider message ID: {provider_message_id}"
                )
                return False
            
            # Track bounce
            success = self.email_repo.track_email_bounce(
                email.id,
                bounce_type,
                bounce_reason,
                provider_response
            )
            
            if success:
                logger.info(
                    f"Bounce tracked for email {email.id}: {bounce_type} - {bounce_reason}"
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error handling bounce: {str(e)}", exc_info=True)
            return False

    def handle_spam_report(
        self,
        provider_message_id: str,
        reporter_email: Optional[str] = None
    ) -> bool:
        """Handle spam report notification from provider."""
        try:
            email = self.email_repo.find_by_provider_message_id(provider_message_id)
            
            if not email:
                logger.warning(
                    f"Email not found for spam report: {provider_message_id}"
                )
                return False
            
            context = {
                'reporter_email': reporter_email,
                'reported_at': datetime.utcnow().isoformat()
            }
            
            success = self.email_repo.track_spam_report(email.id, context)
            
            if success:
                logger.warning(
                    f"Spam report tracked for email {email.id} from {reporter_email}"
                )
            
            return success
            
        except Exception as e:
            logger.error(f"Error handling spam report: {str(e)}", exc_info=True)
            return False

    def get_engagement_analytics(
        self,
        start_date: datetime,
        end_date: datetime,
        hostel_id: Optional[UUID] = None
    ) -> Dict[str, Any]:
        """Get email engagement analytics."""
        try:
            return self.email_repo.get_engagement_analytics(
                start_date,
                end_date,
                hostel_id
            )
        except Exception as e:
            logger.error(f"Error getting engagement analytics: {str(e)}", exc_info=True)
            raise

    def get_top_clicked_links(
        self,
        start_date: datetime,
        end_date: datetime,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get most clicked links in emails."""
        try:
            return self.email_repo.get_click_analytics(start_date, end_date, limit)
        except Exception as e:
            logger.error(f"Error getting click analytics: {str(e)}", exc_info=True)
            raise

    def cleanup_bounced_emails(
        self,
        hard_bounce_days: int = 30
    ) -> int:
        """Clean up hard bounced emails."""
        try:
            return self.email_repo.cleanup_bounced_emails(hard_bounce_days)
        except Exception as e:
            logger.error(f"Error cleaning up bounced emails: {str(e)}", exc_info=True)
            return 0

    def find_unengaged_recipients(
        self,
        days: int = 90,
        min_emails: int = 5
    ) -> List[str]:
        """Find email addresses with low engagement."""
        try:
            return self.email_repo.find_unengaged_recipients(days, min_emails)
        except Exception as e:
            logger.error(f"Error finding unengaged recipients: {str(e)}", exc_info=True)
            return []

    # Helper methods
    def _initialize_email_provider(self):
        """Initialize email service provider based on configuration."""
        provider_type = getattr(settings, 'EMAIL_PROVIDER', 'smtp')
        
        if provider_type == 'sendgrid':
            from app.integrations.email.sendgrid_provider import SendGridProvider
            return SendGridProvider()
        elif provider_type == 'ses':
            from app.integrations.email.ses_provider import SESProvider
            return SESProvider()
        elif provider_type == 'mailgun':
            from app.integrations.email.mailgun_provider import MailgunProvider
            return MailgunProvider()
        else:
            from app.integrations.email.smtp_provider import SMTPProvider
            return SMTPProvider()

    def _send_via_provider(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
        cc_emails: Optional[List[str]] = None,
        bcc_emails: Optional[List[str]] = None,
        reply_to: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        tracking_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send email via configured provider."""
        return self.email_provider.send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body,
            cc_emails=cc_emails,
            bcc_emails=bcc_emails,
            reply_to=reply_to,
            attachments=attachments,
            custom_args={'notification_id': tracking_id} if tracking_id else None
        )

    def _prepare_html_body(
        self,
        body: str,
        track_opens: bool,
        track_clicks: bool,
        notification_id: UUID
    ) -> str:
        """Prepare HTML body with tracking pixels and link tracking."""
        html_body = body
        
        # Add open tracking pixel
        if track_opens:
            tracking_pixel = f'<img src="{settings.APP_URL}/api/notifications/track/open/{notification_id}" width="1" height="1" />'
            html_body += tracking_pixel
        
        # Add click tracking to links
        if track_clicks:
            html_body = self._add_click_tracking(html_body, notification_id)
        
        return html_body

    def _add_click_tracking(self, html: str, notification_id: UUID) -> str:
        """Add click tracking to all links in HTML."""
        # Simple regex to find links - in production, use proper HTML parser
        link_pattern = r'href=["\']([^"\']+)["\']'
        
        def replace_link(match):
            original_url = match.group(1)
            if original_url.startswith(('http://', 'https://', 'mailto:')):
                tracked_url = f"{settings.APP_URL}/api/notifications/track/click/{notification_id}?url={original_url}"
                return f'href="{tracked_url}"'
            return match.group(0)
        
        return re.sub(link_pattern, replace_link, html)

    def _html_to_text(self, html: str) -> str:
        """Convert HTML to plain text."""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', html)
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        return text.strip()

    def _validate_email(self, email: str) -> bool:
        """Validate email address format."""
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None



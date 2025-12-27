"""
Notification System

Comprehensive notification management with multiple channels (email, SMS, push),
templates, scheduling, and delivery tracking.
"""

import asyncio
import json
import smtplib
import ssl
from typing import Any, Dict, List, Optional, Union
from datetime import datetime, timedelta
from enum import Enum
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.utils import formataddr
from pathlib import Path
import aiofiles
import jinja2
from jinja2 import Environment, FileSystemLoader, select_autoescape

from .config import settings
from .exceptions import NotificationError, EmailDeliveryError, SMSDeliveryError
from .logging import get_logger
from .background_tasks import background_task, TaskPriority

logger = get_logger(__name__)


class NotificationChannel(str, Enum):
    """Notification delivery channels"""
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"
    WEBHOOK = "webhook"


class NotificationPriority(str, Enum):
    """Notification priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class NotificationStatus(str, Enum):
    """Notification delivery status"""
    PENDING = "pending"
    SENT = "sent"
    DELIVERED = "delivered"
    FAILED = "failed"
    BOUNCED = "bounced"
    CANCELLED = "cancelled"


class Notification:
    """Notification data container"""
    
    def __init__(
        self,
        id: str,
        recipient: str,
        channel: NotificationChannel,
        subject: str,
        content: str,
        template: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        scheduled_at: Optional[datetime] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.id = id
        self.recipient = recipient
        self.channel = channel
        self.subject = subject
        self.content = content
        self.template = template
        self.context = context or {}
        self.priority = priority
        self.scheduled_at = scheduled_at
        self.attachments = attachments or []
        self.metadata = metadata or {}
        self.created_at = datetime.utcnow()
        self.status = NotificationStatus.PENDING
        self.attempts = 0
        self.last_attempt_at: Optional[datetime] = None
        self.delivered_at: Optional[datetime] = None
        self.error_message: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "id": self.id,
            "recipient": self.recipient,
            "channel": self.channel.value,
            "subject": self.subject,
            "content": self.content,
            "template": self.template,
            "context": self.context,
            "priority": self.priority.value,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "attachments": self.attachments,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "status": self.status.value,
            "attempts": self.attempts,
            "last_attempt_at": self.last_attempt_at.isoformat() if self.last_attempt_at else None,
            "delivered_at": self.delivered_at.isoformat() if self.delivered_at else None,
            "error_message": self.error_message
        }


class EmailProvider:
    """Email delivery provider"""
    
    def __init__(self):
        self.smtp_server = settings.notifications.SMTP_HOST
        self.smtp_port = settings.notifications.SMTP_PORT
        self.username = settings.notifications.SMTP_USERNAME
        self.password = settings.notifications.SMTP_PASSWORD
        self.use_tls = settings.notifications.SMTP_USE_TLS
        self.from_address = settings.notifications.EMAIL_FROM_ADDRESS
        self.from_name = settings.notifications.EMAIL_FROM_NAME
    
    async def send_email(self, notification: Notification) -> bool:
        """Send email notification"""
        try:
            if not all([self.smtp_server, self.username, self.password]):
                raise EmailDeliveryError("Email configuration incomplete")
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = notification.subject
            msg['From'] = formataddr((self.from_name, self.from_address))
            msg['To'] = notification.recipient
            
            # Add content
            if notification.content:
                # Assume HTML content if contains HTML tags
                if '<' in notification.content and '>' in notification.content:
                    html_part = MIMEText(notification.content, 'html', 'utf-8')
                    msg.attach(html_part)
                else:
                    text_part = MIMEText(notification.content, 'plain', 'utf-8')
                    msg.attach(text_part)
            
            # Add attachments
            for attachment in notification.attachments:
                await self._add_attachment(msg, attachment)
            
            # Send email
            await self._send_smtp_message(msg)
            
            logger.info(f"Email sent successfully to {notification.recipient}")
            return True
            
        except Exception as e:
            error_msg = f"Email delivery failed: {str(e)}"
            logger.error(error_msg)
            raise EmailDeliveryError(error_msg)
    
    async def _add_attachment(self, msg: MIMEMultipart, attachment: Dict[str, Any]):
        """Add attachment to email message"""
        try:
            file_path = attachment.get('path')
            filename = attachment.get('filename') or Path(file_path).name
            content_type = attachment.get('content_type', 'application/octet-stream')
            
            if file_path and Path(file_path).exists():
                async with aiofiles.open(file_path, 'rb') as f:
                    file_data = await f.read()
                
                part = MIMEBase(*content_type.split('/'))
                part.set_payload(file_data)
                
                # Encode file in ASCII characters to send by email
                from email import encoders
                encoders.encode_base64(part)
                
                part.add_header(
                    'Content-Disposition',
                    f'attachment; filename= {filename}'
                )
                
                msg.attach(part)
                
        except Exception as e:
            logger.warning(f"Failed to add attachment {attachment}: {str(e)}")
    
    async def _send_smtp_message(self, msg: MIMEMultipart):
        """Send message via SMTP"""
        try:
            # Create SMTP connection
            if self.use_tls:
                context = ssl.create_default_context()
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.starttls(context=context)
                    server.login(self.username, self.password)
                    server.send_message(msg)
            else:
                with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                    server.login(self.username, self.password)
                    server.send_message(msg)
                    
        except smtplib.SMTPException as e:
            raise EmailDeliveryError(f"SMTP error: {str(e)}")


class SMSProvider:
    """SMS delivery provider"""
    
    def __init__(self):
        self.provider = settings.notifications.SMS_PROVIDER
        self.api_key = settings.notifications.SMS_API_KEY
        self.api_secret = settings.notifications.SMS_API_SECRET
        
        if self.provider == "twilio":
            self._init_twilio()
        elif self.provider == "aws_sns":
            self._init_aws_sns()
    
    def _init_twilio(self):
        """Initialize Twilio SMS provider"""
        try:
            from twilio.rest import Client
            self.client = Client(self.api_key, self.api_secret)
        except ImportError:
            logger.error("Twilio SDK not installed")
            self.client = None
    
    def _init_aws_sns(self):
        """Initialize AWS SNS provider"""
        try:
            import boto3
            self.client = boto3.client(
                'sns',
                aws_access_key_id=self.api_key,
                aws_secret_access_key=self.api_secret
            )
        except ImportError:
            logger.error("AWS SDK not installed")
            self.client = None
    
    async def send_sms(self, notification: Notification) -> bool:
        """Send SMS notification"""
        try:
            if not self.client:
                raise SMSDeliveryError("SMS provider not configured")
            
            if self.provider == "twilio":
                return await self._send_twilio_sms(notification)
            elif self.provider == "aws_sns":
                return await self._send_aws_sms(notification)
            else:
                raise SMSDeliveryError(f"Unsupported SMS provider: {self.provider}")
                
        except Exception as e:
            error_msg = f"SMS delivery failed: {str(e)}"
            logger.error(error_msg)
            raise SMSDeliveryError(error_msg)
    
    async def _send_twilio_sms(self, notification: Notification) -> bool:
        """Send SMS via Twilio"""
        try:
            message = self.client.messages.create(
                body=notification.content,
                from_='+1234567890',  # Configure your Twilio number
                to=notification.recipient
            )
            
            logger.info(f"SMS sent successfully to {notification.recipient} (SID: {message.sid})")
            return True
            
        except Exception as e:
            raise SMSDeliveryError(f"Twilio SMS failed: {str(e)}")
    
    async def _send_aws_sms(self, notification: Notification) -> bool:
        """Send SMS via AWS SNS"""
        try:
            response = self.client.publish(
                PhoneNumber=notification.recipient,
                Message=notification.content
            )
            
            logger.info(f"SMS sent successfully to {notification.recipient} (MessageId: {response['MessageId']})")
            return True
            
        except Exception as e:
            raise SMSDeliveryError(f"AWS SNS SMS failed: {str(e)}")


class PushNotificationProvider:
    """Push notification provider"""
    
    def __init__(self):
        self.credentials_file = settings.notifications.FIREBASE_CREDENTIALS_FILE
        self.fcm_client = None
        
        if self.credentials_file:
            self._init_firebase()
    
    def _init_firebase(self):
        """Initialize Firebase Cloud Messaging"""
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging
            
            if not firebase_admin._apps:
                cred = credentials.Certificate(self.credentials_file)
                firebase_admin.initialize_app(cred)
            
            self.fcm_client = messaging
            
        except ImportError:
            logger.error("Firebase Admin SDK not installed")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {str(e)}")
    
    async def send_push(self, notification: Notification) -> bool:
        """Send push notification"""
        try:
            if not self.fcm_client:
                raise NotificationError("Push notification provider not configured")
            
            # Create message
            message = self.fcm_client.Message(
                data=notification.metadata,
                token=notification.recipient,
                notification=self.fcm_client.Notification(
                    title=notification.subject,
                    body=notification.content
                )
            )
            
            # Send message
            response = self.fcm_client.send(message)
            
            logger.info(f"Push notification sent successfully (response: {response})")
            return True
            
        except Exception as e:
            error_msg = f"Push notification failed: {str(e)}"
            logger.error(error_msg)
            raise NotificationError(error_msg)


class TemplateEngine:
    """Notification template engine"""
    
    def __init__(self):
        template_dir = Path(settings.notifications.EMAIL_TEMPLATE_DIR)
        
        if template_dir.exists():
            self.env = Environment(
                loader=FileSystemLoader(str(template_dir)),
                autoescape=select_autoescape(['html', 'xml'])
            )
        else:
            self.env = Environment(loader=DictLoader({}))
        
        # Load default templates
        self._load_default_templates()
    
    def _load_default_templates(self):
        """Load default notification templates"""
        default_templates = {
            'admin_created': {
                'subject': 'Welcome to Hostel Management System',
                'content': '''
                <h2>Welcome {{admin_name}}!</h2>
                <p>Your admin account has been created successfully.</p>
                <p><strong>Email:</strong> {{email}}</p>
                <p><strong>Role:</strong> {{role}}</p>
                <p>Please use the link below to set your password:</p>
                <p><a href="{{reset_link}}">Set Password</a></p>
                '''
            },
            'override_requested': {
                'subject': 'Override Request - {{override_title}}',
                'content': '''
                <h3>Override Request Submitted</h3>
                <p><strong>Title:</strong> {{override_title}}</p>
                <p><strong>Requested by:</strong> {{requester_name}}</p>
                <p><strong>Hostel:</strong> {{hostel_name}}</p>
                <p><strong>Urgency:</strong> {{urgency}}</p>
                <p><strong>Description:</strong></p>
                <p>{{description}}</p>
                <p><a href="{{review_link}}">Review Override</a></p>
                '''
            },
            'assignment_created': {
                'subject': 'Hostel Assignment - {{hostel_name}}',
                'content': '''
                <h3>New Hostel Assignment</h3>
                <p>You have been assigned to manage <strong>{{hostel_name}}</strong>.</p>
                <p><strong>Role:</strong> {{role}}</p>
                <p><strong>Assigned by:</strong> {{assigned_by}}</p>
                <p><a href="{{dashboard_link}}">Access Dashboard</a></p>
                '''
            }
        }
        
        # Store templates in environment
        for template_name, template_data in default_templates.items():
            self.env.get_or_select_template = lambda name: self.env.from_string(
                default_templates.get(name, {}).get('content', '')
            )
    
    def render_template(
        self,
        template_name: str,
        context: Dict[str, Any]
    ) -> Dict[str, str]:
        """Render notification template"""
        try:
            # Try to load template file first
            try:
                template = self.env.get_template(f"{template_name}.html")
                content = template.render(**context)
                
                # Try to load subject template
                try:
                    subject_template = self.env.get_template(f"{template_name}_subject.txt")
                    subject = subject_template.render(**context)
                except:
                    subject = context.get('subject', f"Notification: {template_name}")
                
                return {'subject': subject, 'content': content}
                
            except jinja2.TemplateNotFound:
                # Fallback to default templates
                if template_name in ['admin_created', 'override_requested', 'assignment_created']:
                    template_data = self._get_default_template(template_name)
                    
                    subject = jinja2.Template(template_data['subject']).render(**context)
                    content = jinja2.Template(template_data['content']).render(**context)
                    
                    return {'subject': subject, 'content': content}
                else:
                    raise jinja2.TemplateNotFound(f"Template '{template_name}' not found")
                    
        except Exception as e:
            logger.error(f"Template rendering failed for {template_name}: {str(e)}")
            raise NotificationError(f"Template rendering failed: {str(e)}")
    
    def _get_default_template(self, template_name: str) -> Dict[str, str]:
        """Get default template data"""
        default_templates = {
            'admin_created': {
                'subject': 'Welcome to Hostel Management System',
                'content': '''
                <h2>Welcome {{admin_name}}!</h2>
                <p>Your admin account has been created successfully.</p>
                <p><strong>Email:</strong> {{email}}</p>
                <p><strong>Role:</strong> {{role}}</p>
                <p>Please use the link below to set your password:</p>
                <p><a href="{{reset_link}}">Set Password</a></p>
                '''
            },
            'override_requested': {
                'subject': 'Override Request - {{override_title}}',
                'content': '''
                <h3>Override Request Submitted</h3>
                <p><strong>Title:</strong> {{override_title}}</p>
                <p><strong>Requested by:</strong> {{requester_name}}</p>
                <p><strong>Hostel:</strong> {{hostel_name}}</p>
                <p><strong>Urgency:</strong> {{urgency}}</p>
                <p><strong>Description:</strong></p>
                <p>{{description}}</p>
                <p><a href="{{review_link}}">Review Override</a></p>
                '''
            },
            'assignment_created': {
                'subject': 'Hostel Assignment - {{hostel_name}}',
                'content': '''
                <h3>New Hostel Assignment</h3>
                <p>You have been assigned to manage <strong>{{hostel_name}}</strong>.</p>
                <p><strong>Role:</strong> {{role}}</p>
                <p><strong>Assigned by:</strong> {{assigned_by}}</p>
                <p><a href="{{dashboard_link}}">Access Dashboard</a></p>
                '''
            }
        }
        
        return default_templates.get(template_name, {
            'subject': 'Notification',
            'content': 'You have a new notification.'
        })


class NotificationManager:
    """Main notification management system"""
    
    def __init__(self):
        self.email_provider = EmailProvider()
        self.sms_provider = SMSProvider()
        self.push_provider = PushNotificationProvider()
        self.template_engine = TemplateEngine()
        self._initialized = False
    
    async def initialize(self):
        """Initialize notification system"""
        if self._initialized:
            return
        
        try:
            # Validate configuration
            if not settings.notifications.SMTP_HOST:
                logger.warning("Email notifications not configured")
            
            if not settings.notifications.SMS_PROVIDER:
                logger.warning("SMS notifications not configured")
            
            if not settings.notifications.FIREBASE_CREDENTIALS_FILE:
                logger.warning("Push notifications not configured")
            
            self._initialized = True
            logger.info("Notification manager initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize notification manager: {str(e)}")
            raise NotificationError(f"Notification initialization failed: {str(e)}")
    
    async def send_notification(
        self,
        recipient: str,
        channel: NotificationChannel,
        subject: Optional[str] = None,
        content: Optional[str] = None,
        template: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        scheduled_at: Optional[datetime] = None,
        attachments: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """Send notification via specified channel"""
        if not self._initialized:
            await self.initialize()
        
        # Generate notification ID
        import uuid
        notification_id = str(uuid.uuid4())
        
        try:
            # Render template if provided
            if template and context:
                rendered = self.template_engine.render_template(template, context)
                subject = subject or rendered['subject']
                content = content or rendered['content']
            
            # Create notification object
            notification = Notification(
                id=notification_id,
                recipient=recipient,
                channel=channel,
                subject=subject or "Notification",
                content=content or "",
                template=template,
                context=context,
                priority=priority,
                scheduled_at=scheduled_at,
                attachments=attachments
            )
            
            # Send immediately or schedule
            if scheduled_at and scheduled_at > datetime.utcnow():
                await self._schedule_notification(notification)
            else:
                await self._send_notification_now(notification)
            
            return notification_id
            
        except Exception as e:
            logger.error(f"Failed to send notification: {str(e)}")
            raise NotificationError(f"Notification send failed: {str(e)}")
    
    async def _send_notification_now(self, notification: Notification):
        """Send notification immediately"""
        try:
            notification.attempts += 1
            notification.last_attempt_at = datetime.utcnow()
            
            success = False
            
            if notification.channel == NotificationChannel.EMAIL:
                success = await self.email_provider.send_email(notification)
            elif notification.channel == NotificationChannel.SMS:
                success = await self.sms_provider.send_sms(notification)
            elif notification.channel == NotificationChannel.PUSH:
                success = await self.push_provider.send_push(notification)
            else:
                raise NotificationError(f"Unsupported notification channel: {notification.channel}")
            
            if success:
                notification.status = NotificationStatus.SENT
                notification.delivered_at = datetime.utcnow()
            else:
                notification.status = NotificationStatus.FAILED
                
        except Exception as e:
            notification.status = NotificationStatus.FAILED
            notification.error_message = str(e)
            raise
    
    async def _schedule_notification(self, notification: Notification):
        """Schedule notification for later delivery"""
        try:
            # Use background task system to schedule
            from .background_tasks import enqueue_task
            
            delay = notification.scheduled_at - datetime.utcnow()
            
            await enqueue_task(
                'send_scheduled_notification',
                notification.to_dict(),
                delay=delay,
                priority=TaskPriority.HIGH if notification.priority == NotificationPriority.URGENT else TaskPriority.NORMAL
            )
            
            logger.info(f"Notification {notification.id} scheduled for {notification.scheduled_at}")
            
        except Exception as e:
            logger.error(f"Failed to schedule notification: {str(e)}")
            raise


# Global notification manager
notification_manager = NotificationManager()


@background_task(name="send_scheduled_notification", priority=TaskPriority.NORMAL)
async def send_scheduled_notification(notification_data: Dict[str, Any]):
    """Background task to send scheduled notifications"""
    try:
        # Recreate notification object
        notification = Notification(
            id=notification_data['id'],
            recipient=notification_data['recipient'],
            channel=NotificationChannel(notification_data['channel']),
            subject=notification_data['subject'],
            content=notification_data['content'],
            template=notification_data.get('template'),
            context=notification_data.get('context', {}),
            priority=NotificationPriority(notification_data['priority']),
            attachments=notification_data.get('attachments', [])
        )
        
        await notification_manager._send_notification_now(notification)
        
        logger.info(f"Scheduled notification {notification.id} sent successfully")
        
    except Exception as e:
        logger.error(f"Failed to send scheduled notification: {str(e)}")
        raise


async def send_notification(
    recipient: str,
    channel: Union[NotificationChannel, str],
    subject: Optional[str] = None,
    content: Optional[str] = None,
    template: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None,
    priority: Union[NotificationPriority, str] = NotificationPriority.NORMAL,
    scheduled_at: Optional[datetime] = None,
    attachments: Optional[List[Dict[str, Any]]] = None
) -> str:
    """Convenience function to send notification"""
    
    # Convert string enums to enum objects
    if isinstance(channel, str):
        channel = NotificationChannel(channel)
    if isinstance(priority, str):
        priority = NotificationPriority(priority)
    
    return await notification_manager.send_notification(
        recipient=recipient,
        channel=channel,
        subject=subject,
        content=content,
        template=template,
        context=context,
        priority=priority,
        scheduled_at=scheduled_at,
        attachments=attachments
    )


async def send_override_notification(
    override_id: str,
    notification_type: str,
    extra_data: Optional[Dict[str, Any]] = None
):
    """Send override-related notifications"""
    try:
        # This would typically query the database for override details
        # For now, using placeholder data
        context = {
            'override_id': override_id,
            'override_title': 'Payment Override Request',
            'requester_name': 'John Doe',
            'hostel_name': 'Central Hostel',
            'urgency': 'high',
            'description': 'Override required for payment processing',
            'review_link': f'https://admin.hostel.com/overrides/{override_id}',
            **(extra_data or {})
        }
        
        # Send email to supervisors
        await send_notification(
            recipient='supervisor@hostel.com',
            channel=NotificationChannel.EMAIL,
            template='override_requested',
            context=context,
            priority=NotificationPriority.HIGH
        )
        
        logger.info(f"Override notification sent for {override_id}")
        
    except Exception as e:
        logger.error(f"Failed to send override notification: {str(e)}")


# Export main functions and classes
__all__ = [
    'NotificationChannel',
    'NotificationPriority',
    'NotificationStatus',
    'Notification',
    'NotificationManager',
    'notification_manager',
    'send_notification',
    'send_override_notification'
]
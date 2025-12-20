# --- File: C:\Hostel-Main\app\services\notification\__init__.py ---
"""
Notification services package.

Provides business logic layer for notification system with comprehensive
service implementations for all notification channels and management features.

Services Overview:
    - NotificationService: Core orchestration and multi-channel delivery
    - EmailNotificationService: Email delivery with tracking and engagement
    - SMSNotificationService: SMS delivery with cost tracking and DLT compliance
    - PushNotificationService: Push notifications across iOS, Android, and Web
    - InAppNotificationService: In-app notification management and real-time delivery
    - NotificationTemplateService: Template management with versioning
    - NotificationQueueService: Queue and batch processing management
    - NotificationRoutingService: Intelligent routing and escalation
    - NotificationPreferenceService: User preference and subscription management
    - DeviceTokenService: Device registration and badge management

Architecture:
    - Business logic layer between controllers and repositories
    - Transaction management and coordination
    - External service integration (email/SMS/push providers)
    - Validation and rule enforcement
    - Error handling and logging
    - Performance optimization

Features:
    - Multi-channel notification delivery
    - Template rendering with Jinja2
    - Queue-based processing with priority
    - Intelligent routing with escalation
    - User preference management
    - Engagement tracking and analytics
    - Cost tracking and optimization
    - Real-time notifications
    - Batch processing capabilities
    - Comprehensive error handling

Integration Points:
    - Email providers: SendGrid, AWS SES, Mailgun, SMTP
    - SMS providers: Twilio, MSG91, AWS SNS
    - Push providers: FCM, APNs, Web Push
    - WebSocket for real-time in-app notifications
    - Background job queues (Celery, RQ)
    - Caching layer (Redis)
    - Analytics and monitoring tools
"""

from app.services.notification.notification_service import NotificationService
from app.services.notification.email_notification_service import EmailNotificationService
from app.services.notification.sms_notification_service import SMSNotificationService
from app.services.notification.push_notification_service import PushNotificationService
from app.services.notification.in_app_notification_service import InAppNotificationService
from app.services.notification.notification_template_service import (
    NotificationTemplateService
)
from app.services.notification.notification_queue_service import (
    NotificationQueueService
)
from app.services.notification.notification_routing_service import (
    NotificationRoutingService
)
from app.services.notification.notification_preference_service import (
    NotificationPreferenceService
)
from app.services.notification.device_token_service import DeviceTokenService


__all__ = [
    # Core service
    "NotificationService",
    
    # Channel services
    "EmailNotificationService",
    "SMSNotificationService",
    "PushNotificationService",
    "InAppNotificationService",
    
    # Management services
    "NotificationTemplateService",
    "NotificationQueueService",
    "NotificationRoutingService",
    "NotificationPreferenceService",
    "DeviceTokenService",
]



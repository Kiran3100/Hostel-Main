# --- File: C:\Hostel-Main\app\repositories\notification\__init__.py ---
"""
Notification repositories package.

Provides comprehensive notification repository implementations with advanced
querying, analytics, and management capabilities across all notification channels.

Architecture Overview:
    - Device Token Repository: Device and token management for push notifications
    - Email Notification Repository: Email delivery tracking and engagement analytics  
    - SMS Notification Repository: SMS delivery, cost tracking, and DLT compliance
    - Push Notification Repository: Push notification delivery and device targeting
    - Notification Repository: Core notification lifecycle and status management
    - Template Repository: Template versioning and content management
    - Queue Repository: Batch processing and priority queue management
    - Preferences Repository: User preferences and subscription management
    - Routing Repository: Intelligent routing rules and escalation paths
    - Aggregate Repository: Cross-module analytics and executive reporting

Performance Features:
    - Optimized queries with proper indexing strategies
    - Bulk operations for high-volume processing
    - Connection pooling and session management
    - Query result caching with intelligent invalidation
    - Batch processing for efficient resource utilization

Analytics Capabilities:
    - Real-time delivery and engagement metrics
    - Channel performance comparisons
    - User segmentation and behavior analysis
    - Cost tracking and optimization insights
    - Template effectiveness measurement
    - Routing rule performance monitoring
    - Executive dashboard metrics
    - Trend analysis and forecasting

Monitoring and Optimization:
    - Performance bottleneck identification
    - Queue depth monitoring and alerts
    - Failed delivery pattern analysis
    - Resource usage optimization
    - Automated maintenance and cleanup
    - Health check endpoints
"""

# Core repositories
from app.repositories.notification.notification_repository import (
    NotificationRepository,
    PendingNotificationsSpec,
    UnreadNotificationsSpec
)

from app.repositories.notification.device_token_repository import (
    DeviceTokenRepository,
    ActiveDeviceTokensSpec,
    RecentlyUsedDevicesSpec
)

# Channel-specific repositories
from app.repositories.notification.email_notification_repository import (
    EmailNotificationRepository,
    HighEngagementEmailsSpec,
    BouncedEmailsSpec
)

from app.repositories.notification.sms_notification_repository import (
    SMSNotificationRepository,
    DeliveredSMSSpec,
    HighCostSMSSpec
)

from app.repositories.notification.push_notification_repository import (
    PushNotificationRepository,
    DeliveredPushSpec,
    HighEngagementPushSpec
)

# Management repositories
from app.repositories.notification.notification_template_repository import (
    NotificationTemplateRepository,
    ActiveTemplatesSpec,
    PopularTemplatesSpec
)

from app.repositories.notification.notification_queue_repository import (
    NotificationQueueRepository,
    PendingQueueItemsSpec,
    RetryEligibleSpec
)

from app.repositories.notification.notification_preferences_repository import (
    NotificationPreferencesRepository,
    ActivePreferencesSpec,
    QuietHoursEnabledSpec
)

from app.repositories.notification.notification_routing_repository import (
    NotificationRoutingRepository,
    ActiveRoutingRulesSpec,
    PendingEscalationsSpec
)

# Analytics repository
from app.repositories.notification.notification_aggregate_repository import (
    NotificationAggregateRepository
)


__all__ = [
    # Core repositories
    "NotificationRepository",
    "DeviceTokenRepository",
    
    # Channel repositories
    "EmailNotificationRepository",
    "SMSNotificationRepository", 
    "PushNotificationRepository",
    
    # Management repositories
    "NotificationTemplateRepository",
    "NotificationQueueRepository",
    "NotificationPreferencesRepository",
    "NotificationRoutingRepository",
    
    # Analytics repository
    "NotificationAggregateRepository",
    
    # Specifications
    "PendingNotificationsSpec",
    "UnreadNotificationsSpec",
    "ActiveDeviceTokensSpec",
    "RecentlyUsedDevicesSpec",
    "HighEngagementEmailsSpec",
    "BouncedEmailsSpec",
    "DeliveredSMSSpec",
    "HighCostSMSSpec",
    "DeliveredPushSpec",
    "HighEngagementPushSpec",
    "ActiveTemplatesSpec",
    "PopularTemplatesSpec",
    "PendingQueueItemsSpec",
    "RetryEligibleSpec",
    "ActivePreferencesSpec",
    "QuietHoursEnabledSpec",
    "ActiveRoutingRulesSpec",
    "PendingEscalationsSpec"
]


# Repository usage examples and best practices
"""
Usage Examples:

1. Basic Notification Operations:
   ```python
   from app.repositories.notification import NotificationRepository
   
   # Create notification
   repo = NotificationRepository(db_session)
   notification = repo.create_notification({
       'recipient_user_id': user_id,
       'notification_type': NotificationType.EMAIL,
       'subject': 'Booking Confirmation',
       'message_body': 'Your booking has been confirmed...'
   })
   
   # Get user notifications
   user_notifications = repo.find_by_user(user_id, pagination=pagination_params)
   
   # Mark as read
   repo.mark_as_read(notification.id, user_id, {'read_method': 'web_view'})
   """
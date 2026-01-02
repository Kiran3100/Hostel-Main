# --- File: app/schemas/notification/__init__.py ---
"""
Notification schemas package.

Provides comprehensive schemas for notification management including
email, SMS, push notifications, templates, preferences, routing, and queues.
"""

# Base notification schemas
from app.schemas.notification.notification_base import (
    BulkMarkAsRead,
    BulkNotificationRequest,
    BulkNotificationResponse,
    MarkAsRead,
    NotificationBase,
    NotificationCreate,
    NotificationDelete,
    NotificationUpdate,
)

# Response schemas
from app.schemas.notification.notification_response import (
    InAppNotificationResponse,
    NotificationDetail,
    NotificationList,
    NotificationListItem,
    NotificationResponse,
    NotificationStats,
    NotificationSummary,
    UnreadCount,
)

# Template schemas
from app.schemas.notification.notification_template import (
    NotificationTemplate,
    NotificationTemplateCreate,
    NotificationTemplateUpdate,
    TemplateCategory,
    TemplateCopyRequest,
    TemplateCreate,
    TemplateList,
    TemplatePreview,
    TemplatePreviewRequest,
    TemplatePreviewResponse,
    TemplateResponse,
    TemplateUpdate,
    VariableMapping,
)

# Email schemas
from app.schemas.notification.email_notification import (
    BulkEmailRequest,
    EmailAttachment,
    EmailConfig,
    EmailRequest,
    EmailSchedule,
    EmailStats,
    EmailTemplate,
    EmailTracking,
)

# SMS schemas
from app.schemas.notification.sms_notification import (
    BulkSMSRequest,
    DeliveryStatus,
    SMSConfig,
    SMSQuota,
    SMSRequest,
    SMSStats,
    SMSTemplate,
)

# Push notification schemas
from app.schemas.notification.push_notification import (
    BulkPushRequest,
    DeviceRegistration,
    DeviceToken,
    DeviceTokenCreate,
    DeviceTokenResponse,
    DeviceUnregistration,
    PushAction,
    PushConfig,
    PushDeliveryStatus,
    PushRequest,
    PushStats,
    PushTemplate,
)

# Queue schemas
from app.schemas.notification.notification_queue import (
    BatchProcessing,
    QueuedNotification,
    QueueHealth,
    QueuePriority,
    QueueStats,
    QueueStatus,
)

# Preference schemas
from app.schemas.notification.notification_preferences import (
    ChannelPreferences,
    EmailPreferences,
    FrequencySettings,
    NotificationPreferences,
    NotificationPreferencesUpdate,
    PreferenceUpdate,
    PushPreferences,
    QuietHours,
    SMSPreferences,
    UnsubscribeRequest,
    UserPreferences,
)

# Routing schemas
from app.schemas.notification.notification_routing import (
    EscalationLevel,
    EscalationRouting,
    HierarchicalRouting,
    NotificationRoute,
    RoutingCondition,
    RoutingConfig,
    RoutingRule,
)

__all__ = [
    # Base
    "NotificationBase",
    "NotificationCreate",
    "NotificationUpdate",
    "MarkAsRead",
    "BulkMarkAsRead",
    "NotificationDelete",
    "BulkNotificationRequest",
    "BulkNotificationResponse",
    # Response
    "NotificationResponse",
    "NotificationDetail",
    "NotificationList",
    "NotificationListItem",
    "UnreadCount",
    "NotificationSummary",
    "InAppNotificationResponse",
    "NotificationStats",
    # Template
    "TemplateCreate",
    "TemplateUpdate",
    "TemplateResponse",
    "VariableMapping",
    "TemplatePreview",
    "TemplatePreviewResponse",
    "TemplateList",
    "TemplateCategory",
    "TemplateCopyRequest",
    "NotificationTemplate",
    "NotificationTemplateCreate",
    "NotificationTemplateUpdate",
    "TemplatePreviewRequest",
    # Email
    "EmailRequest",
    "EmailConfig",
    "EmailTracking",
    "EmailTemplate",
    "BulkEmailRequest",
    "EmailStats",
    "EmailAttachment",
    "EmailSchedule",
    # SMS
    "SMSRequest",
    "SMSConfig",
    "DeliveryStatus",
    "SMSTemplate",
    "BulkSMSRequest",
    "SMSStats",
    "SMSQuota",
    # Push
    "PushRequest",
    "PushConfig",
    "DeviceToken",
    "DeviceRegistration",
    "DeviceUnregistration",
    "PushTemplate",
    "PushDeliveryStatus",
    "PushStats",
    "PushAction",
    "BulkPushRequest",
    "DeviceTokenCreate",
    "DeviceTokenResponse",
    # Queue
    "QueueStatus",
    "QueuedNotification",
    "BatchProcessing",
    "QueueStats",
    "QueueHealth",
    "QueuePriority",
    # Preferences
    "UserPreferences",
    "ChannelPreferences",
    "EmailPreferences",
    "SMSPreferences",
    "PushPreferences",
    "FrequencySettings",
    "PreferenceUpdate",
    "UnsubscribeRequest",
    "QuietHours",
    "NotificationPreferences",
    "NotificationPreferencesUpdate",
    # Routing
    "RoutingConfig",
    "RoutingRule",
    "RoutingCondition",
    "HierarchicalRouting",
    "EscalationRouting",
    "EscalationLevel",
    "NotificationRoute",
]
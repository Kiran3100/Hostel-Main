# app/services/notification/__init__.py
"""
Notification services package.

- NotificationService:
    Orchestrates in‑app notifications and dispatch to channels
    (email / SMS / push), plus read/unread management.

- EmailService:
    Email sending, configuration, and basic stats (provider‑agnostic).

- SMSService:
    SMS sending, configuration, and basic stats (provider‑agnostic).

- PushService:
    Push notifications + device registration and stats.

- TemplateService:
    Notification template CRUD and rendering/preview.

- PreferenceService:
    Per‑user notification preferences.

- RoutingService:
    Hostel notification routing rules (who should receive what).

- QueueService:
    Notification queue abstraction for async processing.
"""

from .notification_service import NotificationService, NotificationStore
from .email_service import EmailService, EmailProvider, EmailConfigStore, EmailTrackingStore
from .sms_service import SMSService, SMSProvider, SMSConfigStore, SMSStatusStore
from .push_service import PushService, PushProvider, PushConfigStore, DeviceStore
from .template_service import TemplateService, TemplateStore
from .preference_service import PreferenceService, PreferenceStore
from .routing_service import RoutingService, RoutingStore
from .queue_service import QueueService, NotificationQueueStore

__all__ = [
    "NotificationService",
    "NotificationStore",
    "EmailService",
    "EmailProvider",
    "EmailConfigStore",
    "EmailTrackingStore",
    "SMSService",
    "SMSProvider",
    "SMSConfigStore",
    "SMSStatusStore",
    "PushService",
    "PushProvider",
    "PushConfigStore",
    "DeviceStore",
    "TemplateService",
    "TemplateStore",
    "PreferenceService",
    "PreferenceStore",
    "RoutingService",
    "RoutingStore",
    "QueueService",
    "NotificationQueueStore",
]
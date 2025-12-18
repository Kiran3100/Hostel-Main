# --- File: C:\Hostel-Main\app\models\notification\__init__.py ---
"""
Notification models package.

Provides comprehensive notification system models including:
- Core notification management
- Multi-channel support (email, SMS, push)
- Template management with versioning
- Queue and batch processing
- User preferences and settings
- Intelligent routing and escalation
- Device token management
- Analytics and tracking
"""

# Core notification models
from app.models.notification.notification import (
    Notification,
    NotificationStatusHistory,
    NotificationReadReceipt,
)

# Template models
from app.models.notification.notification_template import (
    NotificationTemplate,
    NotificationTemplateVersion,
)

# Channel-specific models
from app.models.notification.email_notification import (
    EmailNotification,
    EmailAttachment,
    EmailClickEvent,
)

from app.models.notification.sms_notification import (
    SMSNotification,
)

from app.models.notification.push_notification import (
    PushNotification,
)

# Device management
from app.models.notification.device_token import (
    DeviceToken,
)

# Queue management
from app.models.notification.notification_queue import (
    NotificationQueue,
    NotificationBatch,
)

# Preferences
from app.models.notification.notification_preferences import (
    NotificationPreference,
    ChannelPreference,
    UnsubscribeToken,
)

# Routing and escalation
from app.models.notification.notification_routing import (
    RoutingRule,
    EscalationPath,
    NotificationEscalation,
    NotificationRoute,
)


__all__ = [
    # Core
    "Notification",
    "NotificationStatusHistory",
    "NotificationReadReceipt",
    
    # Templates
    "NotificationTemplate",
    "NotificationTemplateVersion",
    
    # Email
    "EmailNotification",
    "EmailAttachment",
    "EmailClickEvent",
    
    # SMS
    "SMSNotification",
    
    # Push
    "PushNotification",
    
    # Device
    "DeviceToken",
    
    # Queue
    "NotificationQueue",
    "NotificationBatch",
    
    # Preferences
    "NotificationPreference",
    "ChannelPreference",
    "UnsubscribeToken",
    
    # Routing
    "RoutingRule",
    "EscalationPath",
    "NotificationEscalation",
    "NotificationRoute",
]


# Model relationship summary for documentation
"""
Model Relationships:

1. Notification (Core)
   ├── → NotificationTemplate (many-to-one)
   ├── → User (recipient, many-to-one)
   ├── → Hostel (many-to-one)
   ├── ← NotificationStatusHistory (one-to-many)
   ├── ← NotificationReadReceipt (one-to-many)
   ├── ← EmailNotification (one-to-one)
   ├── ← SMSNotification (one-to-one)
   ├── ← PushNotification (one-to-one)
   ├── ← NotificationQueue (one-to-one)
   ├── ← NotificationRoute (one-to-one)
   └── ← NotificationEscalation (one-to-one)

2. NotificationTemplate
   ├── ← NotificationTemplateVersion (one-to-many)
   └── ← Notification (one-to-many)

3. EmailNotification
   ├── → Notification (one-to-one)
   ├── ← EmailAttachment (one-to-many)
   └── ← EmailClickEvent (one-to-many)

4. SMSNotification
   └── → Notification (one-to-one)

5. PushNotification
   ├── → Notification (one-to-one)
   └── → DeviceToken (many-to-one)

6. DeviceToken
   ├── → User (many-to-one)
   └── ← PushNotification (one-to-many)

7. NotificationQueue
   ├── → Notification (one-to-one)
   └── → NotificationBatch (many-to-one)

8. NotificationBatch
   └── ← NotificationQueue (one-to-many)

9. NotificationPreference
   ├── → User (one-to-one)
   └── ← ChannelPreference (one-to-many)

10. RoutingRule
    └── → Hostel (many-to-one)

11. EscalationPath
    ├── → Hostel (many-to-one)
    └── ← NotificationEscalation (one-to-many)

12. NotificationEscalation
    ├── → Notification (one-to-one)
    ├── → EscalationPath (many-to-one)
    └── → User (resolved_by, many-to-one)

13. NotificationRoute
    ├── → Notification (one-to-one)
    ├── → RoutingRule (many-to-one)
    └── → EscalationPath (many-to-one)
"""


# Database indexes summary
"""
Key Indexes for Performance:

1. Notification queries:
   - (recipient_user_id, status) - User's notification list
   - (notification_type, status, priority) - Queue processing
   - (scheduled_at, status) - Scheduled notifications
   - (recipient_user_id, read_at) WHERE read_at IS NULL - Unread count

2. Queue processing:
   - (priority, status, scheduled_for) - Priority queue
   - (next_retry_at, retry_count) WHERE next_retry_at IS NOT NULL - Retry queue
   - (status, processing_started_at) WHERE status = 'PROCESSING' - Active jobs

3. Analytics queries:
   - (hostel_id, created_at) - Hostel analytics
   - (created_at, status) - Time-based metrics
   - (opened, clicked) - Email engagement
   - (delivery_status, delivered) - Delivery rates

4. Routing queries:
   - (hostel_id, is_active, rule_priority) - Rule matching
   - (is_resolved, next_escalation_at) WHERE is_resolved = FALSE - Escalations

5. User preferences:
   - (user_id) - User settings lookup
   - (preference_id, channel) - Channel preferences
"""


# Validation rules summary
"""
Data Validation:

1. Notification:
   - At least one recipient (user_id, email, or phone) required
   - Subject required for email and push notifications
   - Scheduled_at must be in the future if set
   - Retry_count must not exceed max_retries

2. NotificationTemplate:
   - Template_code must be unique and lowercase
   - Variables in template must match declared variables
   - Subject required for email/push templates

3. EmailNotification:
   - Valid email addresses for to, cc, bcc
   - At least HTML or text body required
   - Attachments total size limit (25MB)

4. SMSNotification:
   - Phone number must be in E.164 format
   - Message length limit (1600 chars = 10 segments)
   - Sender_id max 11 alphanumeric characters

5. PushNotification:
   - Title max 100 characters
   - Body max 500 characters
   - Data payload max 4KB
   - Max 3 action buttons

6. DeviceToken:
   - Unique per user and token combination
   - Device_type must be valid (ios/android/web)

7. NotificationQueue:
   - Retry_count must not exceed max_retries
   - Scheduled_for must be in the future if set

8. RoutingRule:
   - At least one recipient (roles, users, or groups) required
   - Channels must be valid notification types

9. EscalationPath:
   - Levels must be sequential starting from 1
   - Escalation hours must increase with each level
"""


# Usage examples
"""
Common Usage Patterns:

1. Send immediate email notification:
   ```python
   notification = Notification(
       recipient_user_id=user.id,
       recipient_email=user.email,
       notification_type=NotificationType.EMAIL,
       subject="Booking Confirmed",
       message_body="Your booking has been confirmed...",
       priority=Priority.HIGH,
       status=NotificationStatus.QUEUED
   )
   
   email_details = EmailNotification(
       notification=notification,
       body_html="<html>...</html>",
       body_text="Plain text version...",
       track_opens=True,
       track_clicks=True
   )
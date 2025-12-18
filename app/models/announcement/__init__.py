# --- File: app/models/announcement/__init__.py ---
"""
Announcement models package.

This package provides comprehensive SQLAlchemy models for managing
announcements throughout their lifecycle - from creation to delivery
and engagement tracking.

Models are organized by functional area:
    - announcement: Core announcement entity and attachments
    - announcement_targeting: Audience targeting and selection
    - announcement_scheduling: Scheduling and recurrence
    - announcement_approval: Approval workflows
    - announcement_delivery: Multi-channel delivery tracking
    - announcement_tracking: Read receipts and engagement

Example Usage:
    from app.models.announcement import (
        Announcement,
        AnnouncementDelivery,
        ReadReceipt,
    )
    
    # Create announcement
    announcement = Announcement(
        hostel_id=hostel_uuid,
        title="Important Notice",
        content="Please be informed that...",
        category=AnnouncementCategory.GENERAL,
        created_by_id=admin_uuid,
    )
    db.session.add(announcement)
    db.session.commit()
"""

# Core announcement models
from app.models.announcement.announcement import (
    Announcement,
    AnnouncementAttachment,
    AnnouncementRecipient,
    AnnouncementVersion,
)

# Targeting models
from app.models.announcement.announcement_targeting import (
    AnnouncementTarget,
    BulkTargetingRule,
    TargetAudienceCache,
    TargetingRule,
)

# Scheduling models
from app.models.announcement.announcement_scheduling import (
    AnnouncementSchedule,
    PublishQueue,
    RecurringAnnouncement,
    ScheduleExecution,
)

# Approval models
from app.models.announcement.announcement_approval import (
    AnnouncementApproval,
    ApprovalHistory,
    ApprovalRule,
    ApprovalWorkflow,
)

# Delivery models
from app.models.announcement.announcement_delivery import (
    AnnouncementDelivery,
    DeliveryBatch,
    DeliveryChannel,
    DeliveryFailure,
    DeliveryRetry,
)

# Tracking models
from app.models.announcement.announcement_tracking import (
    Acknowledgment,
    AnnouncementView,
    EngagementMetric,
    ReadingTimeAnalytic,
    ReadReceipt,
)

__all__ = [
    # Core
    "Announcement",
    "AnnouncementAttachment",
    "AnnouncementVersion",
    "AnnouncementRecipient",
    
    # Targeting
    "AnnouncementTarget",
    "TargetingRule",
    "TargetAudienceCache",
    "BulkTargetingRule",
    
    # Scheduling
    "AnnouncementSchedule",
    "RecurringAnnouncement",
    "ScheduleExecution",
    "PublishQueue",
    
    # Approval
    "AnnouncementApproval",
    "ApprovalWorkflow",
    "ApprovalHistory",
    "ApprovalRule",
    
    # Delivery
    "AnnouncementDelivery",
    "DeliveryChannel",
    "DeliveryBatch",
    "DeliveryFailure",
    "DeliveryRetry",
    
    # Tracking
    "AnnouncementView",
    "ReadReceipt",
    "Acknowledgment",
    "EngagementMetric",
    "ReadingTimeAnalytic",
]

# Package version
__version__ = "1.0.0"

# Package metadata
__author__ = "Hostel Management System"
__description__ = "Comprehensive announcement management models"
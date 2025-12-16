# --- File: app/schemas/announcement/__init__.py ---
"""
Announcement schemas package.

This package provides comprehensive schemas for managing announcements
throughout their lifecycle - from creation to delivery and tracking.

Modules:
    announcement_base: Base schemas for creation and updates
    announcement_response: Response schemas for API responses
    announcement_targeting: Audience targeting configuration
    announcement_scheduling: Scheduling and recurrence
    announcement_approval: Approval workflow
    announcement_delivery: Delivery configuration and tracking
    announcement_tracking: Read receipts and engagement
    announcement_filters: Filtering, search, and export

Example Usage:
    from app.schemas.announcement import (
        AnnouncementCreate,
        AnnouncementResponse,
        DeliveryConfig,
    )
    
    # Create announcement
    announcement = AnnouncementCreate(
        hostel_id=hostel_uuid,
        title="Important Notice",
        content="Please be informed that...",
        category=AnnouncementCategory.GENERAL,
        created_by=admin_uuid,
    )
"""

# Base schemas
from app.schemas.announcement.announcement_base import (
    AnnouncementBase,
    AnnouncementCreate,
    AnnouncementPublish,
    AnnouncementUnpublish,
    AnnouncementUpdate,
)

# Response schemas
from app.schemas.announcement.announcement_response import (
    AnnouncementDetail,
    AnnouncementList,
    AnnouncementListItem,
    AnnouncementResponse,
    AnnouncementSummary,
    StudentAnnouncementView,
)

# Targeting schemas
from app.schemas.announcement.announcement_targeting import (
    AudienceSelection,
    BulkTargeting,
    CombineMode,
    IndividualTargeting,
    TargetFloors,
    TargetingConfig,
    TargetingPreview,
    TargetingSummary,
    TargetRooms,
    TargetType,
)

# Scheduling schemas
from app.schemas.announcement.announcement_scheduling import (
    PublishNow,
    RecurrencePattern,
    RecurringAnnouncement,
    ScheduleCancel,
    ScheduleConfig,
    ScheduledAnnouncementItem,
    ScheduledAnnouncementsList,
    ScheduleRequest,
    ScheduleStatus,
    ScheduleUpdate,
)

# Approval schemas
from app.schemas.announcement.announcement_approval import (
    ApprovalHistory,
    ApprovalRequest,
    ApprovalResponse,
    ApprovalStatus,
    ApprovalWorkflow,
    BulkApproval,
    PendingApprovalItem,
    RejectionRequest,
    SupervisorApprovalQueue,
)

# Delivery schemas
from app.schemas.announcement.announcement_delivery import (
    BatchDelivery,
    ChannelDeliveryStats,
    DeliveryChannel,
    DeliveryConfig,
    DeliveryChannels,
    DeliveryPause,
    DeliveryReport,
    DeliveryResume,
    DeliveryState,
    DeliveryStatus,
    DeliveryStrategy,
    FailedDelivery,
    RetryDelivery,
)

# Tracking schemas
from app.schemas.announcement.announcement_tracking import (
    AcknowledgmentRequest,
    AcknowledgmentResponse,
    AcknowledgmentTracking,
    AnnouncementAnalytics,
    DeviceType,
    EngagementMetrics,
    EngagementTrend,
    PendingAcknowledgment,
    ReadingTime,
    ReadReceipt,
    ReadReceiptResponse,
    StudentEngagement,
)

# Filter schemas
from app.schemas.announcement.announcement_filters import (
    AnnouncementExportRequest,
    AnnouncementFilterParams,
    AnnouncementSortField,
    AnnouncementStatsRequest,
    ArchiveRequest,
    BulkDeleteRequest,
    ExportFormat,
    SearchRequest,
)

__all__ = [
    # Base
    "AnnouncementBase",
    "AnnouncementCreate",
    "AnnouncementUpdate",
    "AnnouncementPublish",
    "AnnouncementUnpublish",
    
    # Response
    "AnnouncementResponse",
    "AnnouncementDetail",
    "AnnouncementList",
    "AnnouncementListItem",
    "StudentAnnouncementView",
    "AnnouncementSummary",
    
    # Targeting
    "TargetType",
    "CombineMode",
    "TargetingConfig",
    "AudienceSelection",
    "TargetRooms",
    "TargetFloors",
    "IndividualTargeting",
    "TargetingSummary",
    "BulkTargeting",
    "TargetingPreview",
    
    # Scheduling
    "RecurrencePattern",
    "ScheduleStatus",
    "ScheduleRequest",
    "ScheduleConfig",
    "RecurringAnnouncement",
    "ScheduleUpdate",
    "ScheduleCancel",
    "PublishNow",
    "ScheduledAnnouncementsList",
    "ScheduledAnnouncementItem",
    
    # Approval
    "ApprovalStatus",
    "ApprovalRequest",
    "ApprovalResponse",
    "RejectionRequest",
    "ApprovalWorkflow",
    "SupervisorApprovalQueue",
    "PendingApprovalItem",
    "BulkApproval",
    "ApprovalHistory",
    
    # Delivery
    "DeliveryChannel",
    "DeliveryStrategy",
    "DeliveryState",
    "DeliveryConfig",
    "DeliveryChannels",
    "DeliveryStatus",
    "DeliveryReport",
    "ChannelDeliveryStats",
    "FailedDelivery",
    "BatchDelivery",
    "RetryDelivery",
    "DeliveryPause",
    "DeliveryResume",
    
    # Tracking
    "DeviceType",
    "ReadReceipt",
    "ReadReceiptResponse",
    "AcknowledgmentRequest",
    "AcknowledgmentResponse",
    "AcknowledgmentTracking",
    "PendingAcknowledgment",
    "EngagementMetrics",
    "ReadingTime",
    "AnnouncementAnalytics",
    "StudentEngagement",
    "EngagementTrend",
    
    # Filters
    "ExportFormat",
    "AnnouncementSortField",
    "AnnouncementFilterParams",
    "SearchRequest",
    "ArchiveRequest",
    "AnnouncementExportRequest",
    "BulkDeleteRequest",
    "AnnouncementStatsRequest",
]

# Package version
__version__ = "2.0.0"  # Updated for Pydantic v2
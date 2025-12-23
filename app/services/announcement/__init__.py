"""
Announcement service layer.

Provides comprehensive business logic for announcement lifecycle management:
- Creation, update, publishing, and archival
- Advanced targeting and audience selection
- Scheduling with recurring patterns
- Multi-level approval workflows
- Multi-channel delivery orchestration
- Engagement tracking and analytics
- Reusable content templates

Version: 2.0.0
Enhanced with improved error handling, validation, and performance optimizations.
"""

from app.services.announcement.announcement_service import AnnouncementService
from app.services.announcement.announcement_targeting_service import (
    AnnouncementTargetingService
)
from app.services.announcement.announcement_scheduling_service import (
    AnnouncementSchedulingService
)
from app.services.announcement.announcement_approval_service import (
    AnnouncementApprovalService
)
from app.services.announcement.announcement_delivery_service import (
    AnnouncementDeliveryService
)
from app.services.announcement.announcement_tracking_service import (
    AnnouncementTrackingService
)
from app.services.announcement.announcement_template_service import (
    AnnouncementTemplateService
)

__all__ = [
    "AnnouncementService",
    "AnnouncementTargetingService",
    "AnnouncementSchedulingService",
    "AnnouncementApprovalService",
    "AnnouncementDeliveryService",
    "AnnouncementTrackingService",
    "AnnouncementTemplateService",
]

__version__ = "2.0.0"
__author__ = "Hostel Management System Team"
__description__ = "Enhanced announcement services with comprehensive lifecycle management"

# Service initialization order for dependency management
SERVICE_INITIALIZATION_ORDER = [
    "AnnouncementService",          # Core service - no dependencies
    "AnnouncementTargetingService",  # Depends on core service
    "AnnouncementTemplateService",   # Independent service
    "AnnouncementSchedulingService", # Depends on core service
    "AnnouncementApprovalService",   # Depends on core service
    "AnnouncementDeliveryService",   # Depends on core, targeting, and approval
    "AnnouncementTrackingService",   # Depends on core and delivery
]

# Feature flags for gradual rollout
FEATURE_FLAGS = {
    "advanced_targeting": True,
    "recurring_schedules": True,
    "multi_level_approval": True,
    "multi_channel_delivery": True,
    "engagement_analytics": True,
    "template_inheritance": True,
}
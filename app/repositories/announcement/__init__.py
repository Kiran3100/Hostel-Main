"""
Announcement Repositories Package

This package provides a comprehensive repository layer for the Announcement module,
implementing the Repository pattern with Domain-Driven Design (DDD) principles.

Architecture:
- Core Repositories: Individual domain entity repositories
- Aggregate Repository: Orchestrates complex cross-repository workflows
- Base Repository: Abstract foundation with common CRUD operations

Repositories:
- AnnouncementRepository: Core announcement CRUD and lifecycle management
- AnnouncementTargetingRepository: Audience targeting and segmentation
- AnnouncementSchedulingRepository: Scheduling and recurring patterns
- AnnouncementApprovalRepository: Approval workflows and SLA tracking
- AnnouncementDeliveryRepository: Multi-channel delivery management
- AnnouncementTrackingRepository: Engagement tracking and analytics
- AnnouncementAggregateRepository: Workflow orchestration

Usage:
    from app.repositories.announcement import (
        AnnouncementRepository,
        AnnouncementAggregateRepository
    )
    
    # Initialize repositories
    announcement_repo = AnnouncementRepository(session)
    aggregate_repo = AnnouncementAggregateRepository(session)
    
    # Create complete announcement workflow
    result = aggregate_repo.create_complete_announcement(
        hostel_id=hostel_uuid,
        created_by_id=user_uuid,
        announcement_data={...},
        targeting_data={...},
        schedule_data={...}
    )

Features:
- Transactional integrity across operations
- Separation of concerns with specialized repositories
- Complex workflow orchestration via aggregate repository
- Comprehensive query operations with filtering and pagination
- Performance-optimized bulk operations
- Real-time analytics and metrics calculation
- Audit trail and versioning support
"""

from app.repositories.announcement.announcement_repository import (
    AnnouncementRepository,
    ActiveAnnouncementsSpec,
    UrgentAnnouncementsSpec,
    RequiresAcknowledgmentSpec,
)
from app.repositories.announcement.announcement_targeting_repository import (
    AnnouncementTargetingRepository,
)
from app.repositories.announcement.announcement_scheduling_repository import (
    AnnouncementSchedulingRepository,
)
from app.repositories.announcement.announcement_approval_repository import (
    AnnouncementApprovalRepository,
)
from app.repositories.announcement.announcement_delivery_repository import (
    AnnouncementDeliveryRepository,
)
from app.repositories.announcement.announcement_tracking_repository import (
    AnnouncementTrackingRepository,
)
from app.repositories.announcement.announcement_aggregate_repository import (
    AnnouncementAggregateRepository,
)

# Public API
__all__ = [
    # Core Repositories
    "AnnouncementRepository",
    "AnnouncementTargetingRepository",
    "AnnouncementSchedulingRepository",
    "AnnouncementApprovalRepository",
    "AnnouncementDeliveryRepository",
    "AnnouncementTrackingRepository",
    
    # Aggregate Repository
    "AnnouncementAggregateRepository",
    
    # Specifications
    "ActiveAnnouncementsSpec",
    "UrgentAnnouncementsSpec",
    "RequiresAcknowledgmentSpec",
]

# Package metadata
__version__ = "1.0.0"
__author__ = "Hostel Management System Team"
__description__ = "Comprehensive announcement repository layer with DDD patterns"

# Repository registry for dependency injection
REPOSITORY_REGISTRY = {
    'announcement': AnnouncementRepository,
    'targeting': AnnouncementTargetingRepository,
    'scheduling': AnnouncementSchedulingRepository,
    'approval': AnnouncementApprovalRepository,
    'delivery': AnnouncementDeliveryRepository,
    'tracking': AnnouncementTrackingRepository,
    'aggregate': AnnouncementAggregateRepository,
}


def get_repository(repository_name: str, session):
    """
    Factory function to get repository instance by name.
    
    Args:
        repository_name: Name of repository
        session: Database session
        
    Returns:
        Repository instance
        
    Example:
        repo = get_repository('announcement', session)
    """
    repo_class = REPOSITORY_REGISTRY.get(repository_name)
    if not repo_class:
        raise ValueError(f"Unknown repository: {repository_name}")
    return repo_class(session)
"""
Announcement Services Package

This package provides comprehensive business logic services for the Announcement module,
implementing service layer patterns with transaction management, validation, and events.

Architecture:
- Service Layer: Business logic orchestration
- DTOs: Data Transfer Objects with validation
- Events: Event publishing for integrations
- Transactions: Atomic operations

Services:
- AnnouncementService: Core announcement CRUD and lifecycle
- AnnouncementTargetingService: Audience targeting and segmentation
- AnnouncementSchedulingService: Scheduling and recurring patterns
- AnnouncementApprovalService: Approval workflows and SLA tracking
- AnnouncementDeliveryService: Multi-channel delivery management
- AnnouncementTrackingService: Engagement tracking and analytics
- AnnouncementTemplateService: Template management and rendering

Usage:
    from app.services.announcement import (
        AnnouncementService,
        CreateAnnouncementDTO,
        UserContext,
    )
    
    # Initialize service
    service = AnnouncementService(session)
    
    # Create announcement
    result = service.create_announcement(
        dto=CreateAnnouncementDTO(...),
        user_context=UserContext(...)
    )
    
    if result.success:
        announcement_data = result.data
    else:
        error_message = result.error

Features:
- Comprehensive business validation
- Permission-based access control
- Event-driven architecture
- Transaction management
- DTO-based data validation
- Service result pattern
- Real-time metrics and analytics
"""

from app.services.announcement.announcement_service import (
    AnnouncementService,
    CreateAnnouncementDTO,
    UpdateAnnouncementDTO,
    PublishAnnouncementDTO,
    ArchiveAnnouncementDTO,
    BulkActionDTO,
    UserContext,
    ServiceResult,
)

from app.services.announcement.announcement_targeting_service import (
    AnnouncementTargetingService,
    BuildAudienceSegmentDTO,
    MultiCriteriaSegmentDTO,
    BulkTargetingDTO,
    PersonalizationContextDTO,
    NotificationPreferencesDTO,
)

from app.services.announcement.announcement_scheduling_service import (
    AnnouncementSchedulingService,
    CreateScheduleDTO,
    CreateRecurringScheduleDTO,
    UpdateScheduleDTO,
    CreateRecurringTemplateDTO,
)

from app.services.announcement.announcement_approval_service import (
    AnnouncementApprovalService,
    RequestApprovalDTO,
    ApproveAnnouncementDTO,
    RejectAnnouncementDTO,
    ResubmitApprovalDTO,
    AssignApproverDTO,
    EscalateApprovalDTO,
    CreateApprovalWorkflowDTO,
    CreateApprovalRuleDTO,
)

from app.services.announcement.announcement_delivery_service import (
    AnnouncementDeliveryService,
    InitializeDeliveryDTO,
    RetryDeliveryDTO,
    ChannelConfigurationDTO,
)

from app.services.announcement.announcement_tracking_service import (
    AnnouncementTrackingService,
    RecordViewDTO,
    UpdateReadingMetricsDTO,
    RecordEngagementActionDTO,
    MarkAsReadDTO,
    AcknowledgeAnnouncementDTO,
    VerifyAcknowledgmentDTO,
    GetEngagementProfileDTO,
    IdentifyLowEngagementDTO,
)

from app.services.announcement.announcement_template_service import (
    AnnouncementTemplateService,
    CreateTemplateDTO,
    UpdateTemplateDTO,
    RenderTemplateDTO,
    CreateFromTemplateDTO,
)

# Public API
__all__ = [
    # Core Service
    "AnnouncementService",
    "CreateAnnouncementDTO",
    "UpdateAnnouncementDTO",
    "PublishAnnouncementDTO",
    "ArchiveAnnouncementDTO",
    "BulkActionDTO",
    "UserContext",
    "ServiceResult",
    
    # Targeting Service
    "AnnouncementTargetingService",
    "BuildAudienceSegmentDTO",
    "MultiCriteriaSegmentDTO",
    "BulkTargetingDTO",
    "PersonalizationContextDTO",
    "NotificationPreferencesDTO",
    
    # Scheduling Service
    "AnnouncementSchedulingService",
    "CreateScheduleDTO",
    "CreateRecurringScheduleDTO",
    "UpdateScheduleDTO",
    "CreateRecurringTemplateDTO",
    
    # Approval Service
    "AnnouncementApprovalService",
    "RequestApprovalDTO",
    "ApproveAnnouncementDTO",
    "RejectAnnouncementDTO",
    "ResubmitApprovalDTO",
    "AssignApproverDTO",
    "EscalateApprovalDTO",
    "CreateApprovalWorkflowDTO",
    "CreateApprovalRuleDTO",
    
    # Delivery Service
    "AnnouncementDeliveryService",
    "InitializeDeliveryDTO",
    "RetryDeliveryDTO",
    "ChannelConfigurationDTO",
    
    # Tracking Service
    "AnnouncementTrackingService",
    "RecordViewDTO",
    "UpdateReadingMetricsDTO",
    "RecordEngagementActionDTO",
    "MarkAsReadDTO",
    "AcknowledgeAnnouncementDTO",
    "VerifyAcknowledgmentDTO",
    "GetEngagementProfileDTO",
    "IdentifyLowEngagementDTO",
    
    # Template Service
    "AnnouncementTemplateService",
    "CreateTemplateDTO",
    "UpdateTemplateDTO",
    "RenderTemplateDTO",
    "CreateFromTemplateDTO",
]

# Package metadata
__version__ = "1.0.0"
__author__ = "Hostel Management System Team"
__description__ = "Comprehensive announcement service layer with business logic"

# Service registry for dependency injection
SERVICE_REGISTRY = {
    'announcement': AnnouncementService,
    'targeting': AnnouncementTargetingService,
    'scheduling': AnnouncementSchedulingService,
    'approval': AnnouncementApprovalService,
    'delivery': AnnouncementDeliveryService,
    'tracking': AnnouncementTrackingService,
    'template': AnnouncementTemplateService,
}


def get_service(service_name: str, session, **kwargs):
    """
    Factory function to get service instance by name.
    
    Args:
        service_name: Name of service
        session: Database session
        **kwargs: Additional service dependencies
        
    Returns:
        Service instance
        
    Example:
        service = get_service('announcement', session)
    """
    service_class = SERVICE_REGISTRY.get(service_name)
    if not service_class:
        raise ValueError(f"Unknown service: {service_name}")
    return service_class(session, **kwargs)


# Service container for managing multiple services
class ServiceContainer:
    """
    Container for managing multiple announcement services.
    
    Provides unified access to all announcement services with
    shared session and dependency management.
    """
    
    def __init__(self, session, **dependencies):
        self.session = session
        self.dependencies = dependencies
        
        # Initialize all services
        self.announcement = AnnouncementService(session, **self._filter_deps(AnnouncementService))
        self.targeting = AnnouncementTargetingService(session, **self._filter_deps(AnnouncementTargetingService))
        self.scheduling = AnnouncementSchedulingService(session, **self._filter_deps(AnnouncementSchedulingService))
        self.approval = AnnouncementApprovalService(session, **self._filter_deps(AnnouncementApprovalService))
        self.delivery = AnnouncementDeliveryService(session, **self._filter_deps(AnnouncementDeliveryService))
        self.tracking = AnnouncementTrackingService(session, **self._filter_deps(AnnouncementTrackingService))
        self.template = AnnouncementTemplateService(session, **self._filter_deps(AnnouncementTemplateService))
    
    def _filter_deps(self, service_class):
        """Filter dependencies based on service constructor parameters."""
        import inspect
        sig = inspect.signature(service_class.__init__)
        params = set(sig.parameters.keys()) - {'self', 'session'}
        return {k: v for k, v in self.dependencies.items() if k in params}
    
    def commit(self):
        """Commit all changes."""
        self.session.commit()
    
    def rollback(self):
        """Rollback all changes."""
        self.session.rollback()
    
    def close(self):
        """Close session."""
        self.session.close()
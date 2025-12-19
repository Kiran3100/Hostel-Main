"""
Integration repositories package.

This package contains all repository implementations for integration management,
including API integrations, communication channels, third-party services,
workflow automation, and aggregate analytics.
"""

from app.repositories.integrations.api_integration_repository import (
    APIIntegrationRepository,
    IntegrationStatus,
    IntegrationType
)
from app.repositories.integrations.communication_repository import (
    CommunicationRepository,
    CommunicationChannel,
    CommunicationStatus,
    CommunicationPriority,
    CommunicationType
)
from app.repositories.integrations.third_party_repository import (
    ThirdPartyRepository,
    ThirdPartyProvider,
    SyncDirection,
    SyncStatus
)
from app.repositories.integrations.workflow_repository import (
    WorkflowRepository,
    WorkflowStatus,
    WorkflowTriggerType,
    TaskStatus,
    TaskType,
    ApprovalStatus
)
from app.repositories.integrations.integration_aggregate_repository import (
    IntegrationAggregateRepository
)

__all__ = [
    # API Integration
    "APIIntegrationRepository",
    "IntegrationStatus",
    "IntegrationType",
    
    # Communication
    "CommunicationRepository",
    "CommunicationChannel",
    "CommunicationStatus",
    "CommunicationPriority",
    "CommunicationType",
    
    # Third Party
    "ThirdPartyRepository",
    "ThirdPartyProvider",
    "SyncDirection",
    "SyncStatus",
    
    # Workflow
    "WorkflowRepository",
    "WorkflowStatus",
    "WorkflowTriggerType",
    "TaskStatus",
    "TaskType",
    "ApprovalStatus",
    
    # Aggregate
    "IntegrationAggregateRepository",
]
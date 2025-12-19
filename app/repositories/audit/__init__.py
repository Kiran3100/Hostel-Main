"""
Audit repositories package.

Provides comprehensive audit trail and activity logging repositories
for system-wide tracking, compliance, and analytics.
"""

from app.repositories.audit.audit_log_repository import AuditLogRepository
from app.repositories.audit.entity_change_log_repository import (
    EntityChangeLogRepository,
    EntityChangeHistoryRepository
)
from app.repositories.audit.supervisor_activity_log_repository import (
    SupervisorActivityLogRepository
)
from app.repositories.audit.admin_override_log_repository import (
    AdminOverrideLogRepository
)
from app.repositories.audit.audit_aggregate_repository import (
    AuditAggregateRepository
)

__all__ = [
    # Core audit repositories
    "AuditLogRepository",
    "EntityChangeLogRepository",
    "EntityChangeHistoryRepository",
    
    # Specialized audit repositories
    "SupervisorActivityLogRepository",
    "AdminOverrideLogRepository",
    
    # Aggregation and analytics
    "AuditAggregateRepository",
]
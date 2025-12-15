# --- File: app/schemas/audit/__init__.py ---
"""
Audit & logging schemas package.

Comprehensive audit trail and activity logging for:
- System-wide audit logs
- Supervisor activity tracking
- Admin override recording
- Compliance and security reporting
- Performance analytics
"""

# Base audit logs
from app.schemas.audit.audit_log_base import (
    AuditLogBase,
    AuditLogCreate,
    AuditContext,
    ChangeDetail,
)

# Audit responses
from app.schemas.audit.audit_log_response import (
    AuditLogResponse,
    AuditLogDetail,
    AuditLogSummary,
    AuditLogTimeline,
)

# Audit filters
from app.schemas.audit.audit_filters import (
    AuditFilterParams,
    AuditSearchParams,
    AuditExportParams,
    AuditSortField,
)

# Audit reports
from app.schemas.audit.audit_reports import (
    AuditReport,
    AuditSummary,
    UserActivitySummary,
    EntityChangeHistory,
    EntityChangeRecord,
    EntityChangeSummary,
    CategoryAnalytics,
    ComplianceReport,
    SecurityAuditReport,
    AuditTrendAnalysis,
    ReportFormat,
)

# Supervisor activity
from app.schemas.audit.supervisor_activity_log import (
    SupervisorActivityBase,
    SupervisorActivityCreate,
    SupervisorActivityLogResponse,
    SupervisorActivityDetail,
    SupervisorActivityFilter,
    SupervisorActivitySummary,
    SupervisorActivityTimelinePoint,
    SupervisorPerformanceMetrics,
    SupervisorShiftReport,
    SupervisorActionCategory,
)

# Admin overrides
from app.schemas.audit.admin_override_log import (
    AdminOverrideBase,
    AdminOverrideCreate,
    AdminOverrideLogResponse,
    AdminOverrideDetail,
    AdminOverrideSummary,
    AdminOverrideTimelinePoint,
    AdminOverrideAnalytics,
    SupervisorImpactAnalysis,
)

__all__ = [
    # Base audit logs
    "AuditLogBase",
    "AuditLogCreate",
    "AuditContext",
    "ChangeDetail",
    
    # Audit responses
    "AuditLogResponse",
    "AuditLogDetail",
    "AuditLogSummary",
    "AuditLogTimeline",
    
    # Filters and search
    "AuditFilterParams",
    "AuditSearchParams",
    "AuditExportParams",
    "AuditSortField",
    
    # Reports and analytics
    "AuditReport",
    "AuditSummary",
    "UserActivitySummary",
    "EntityChangeHistory",
    "EntityChangeRecord",
    "EntityChangeSummary",
    "CategoryAnalytics",
    "ComplianceReport",
    "SecurityAuditReport",
    "AuditTrendAnalysis",
    "ReportFormat",
    
    # Supervisor activity
    "SupervisorActivityBase",
    "SupervisorActivityCreate",
    "SupervisorActivityLogResponse",
    "SupervisorActivityDetail",
    "SupervisorActivityFilter",
    "SupervisorActivitySummary",
    "SupervisorActivityTimelinePoint",
    "SupervisorPerformanceMetrics",
    "SupervisorShiftReport",
    "SupervisorActionCategory",
    
    # Admin overrides
    "AdminOverrideBase",
    "AdminOverrideCreate",
    "AdminOverrideLogResponse",
    "AdminOverrideDetail",
    "AdminOverrideSummary",
    "AdminOverrideTimelinePoint",
    "AdminOverrideAnalytics",
    "SupervisorImpactAnalysis",
]
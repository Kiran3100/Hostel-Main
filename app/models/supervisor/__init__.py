# app/models/supervisor/__init__.py
"""
Supervisor models package.

Comprehensive supervisor management models including:
- Core supervisor entity and employment
- Permission management and access control
- Assignment and transfer tracking
- Activity logging and audit trails
- Dashboard metrics and real-time data
- Performance tracking and evaluation
"""

from app.models.supervisor.supervisor import (
    Supervisor,
    SupervisorEmployment,
    SupervisorStatusHistory,
    SupervisorNote,
)

from app.models.supervisor.supervisor_permissions import (
    SupervisorPermission,
    PermissionTemplate,
    PermissionAuditLog,
)

from app.models.supervisor.supervisor_assignment import (
    SupervisorAssignment,
    AssignmentTransfer,
    AssignmentCoverage,
    WorkloadMetric,
)

from app.models.supervisor.supervisor_activity import (
    SupervisorActivity,
    SupervisorSession,
    ActivitySummary,
    ActivityMetric,
)

from app.models.supervisor.supervisor_dashboard import (
    DashboardMetrics,
    DashboardAlert,
    QuickAction,
    TodaySchedule,
    PerformanceIndicator,
)

from app.models.supervisor.supervisor_performance import (
    SupervisorPerformance,
    PerformanceReview,
    PerformanceGoal,
    PerformanceMetric,
    PeerComparison,
)

__all__ = [
    # Core supervisor models
    "Supervisor",
    "SupervisorEmployment",
    "SupervisorStatusHistory",
    "SupervisorNote",
    
    # Permission models
    "SupervisorPermission",
    "PermissionTemplate",
    "PermissionAuditLog",
    
    # Assignment models
    "SupervisorAssignment",
    "AssignmentTransfer",
    "AssignmentCoverage",
    "WorkloadMetric",
    
    # Activity models
    "SupervisorActivity",
    "SupervisorSession",
    "ActivitySummary",
    "ActivityMetric",
    
    # Dashboard models
    "DashboardMetrics",
    "DashboardAlert",
    "QuickAction",
    "TodaySchedule",
    "PerformanceIndicator",
    
    # Performance models
    "SupervisorPerformance",
    "PerformanceReview",
    "PerformanceGoal",
    "PerformanceMetric",
    "PeerComparison",
]
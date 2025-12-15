# --- File: app/schemas/supervisor/__init__.py ---
# app/schemas/supervisor/__init__.py
"""
Supervisor schemas package
"""
from app.schemas.supervisor.supervisor_base import (
    SupervisorBase,
    SupervisorCreate,
    SupervisorUpdate
)
from app.schemas.supervisor.supervisor_response import (
    SupervisorResponse,
    SupervisorDetail,
    SupervisorListItem
)
from app.schemas.supervisor.supervisor_profile import (
    SupervisorProfile,
    SupervisorEmployment,
    SupervisorProfileUpdate
)
from app.schemas.supervisor.supervisor_permissions import (
    SupervisorPermissions,
    PermissionUpdate,
    PermissionCheckRequest,
    PermissionCheckResponse
)
from app.schemas.supervisor.supervisor_assignment import (
    SupervisorAssignment,
    AssignmentRequest,
    AssignmentUpdate,
    RevokeAssignmentRequest
)
from app.schemas.supervisor.supervisor_activity import (
    SupervisorActivityLog,
    ActivitySummary,
    ActivityDetail,
    ActivityFilterParams
)
from app.schemas.supervisor.supervisor_dashboard import (
    SupervisorDashboard,
    DashboardMetrics,
    TaskSummary,
    RecentComplaintItem,
    RecentMaintenanceItem,
    PendingLeaveItem,
    TodaySchedule,
    ScheduledMaintenanceItem,
    ScheduledMeeting,
    DashboardAlert,
    QuickActions,
    PerformanceIndicators
)
from app.schemas.supervisor.supervisor_performance import (
    PerformanceMetrics,
    PerformanceReport,
    PerformanceReview,
    ComplaintPerformance,
    AttendancePerformance,
    MaintenancePerformance
)

__all__ = [
    # Base
    "SupervisorBase",
    "SupervisorCreate",
    "SupervisorUpdate",
    
    # Response
    "SupervisorResponse",
    "SupervisorDetail",
    "SupervisorListItem",
    
    # Profile
    "SupervisorProfile",
    "SupervisorEmployment",
    "SupervisorProfileUpdate",
    
    # Permissions
    "SupervisorPermissions",
    "PermissionUpdate",
    "PermissionCheckRequest",
    "PermissionCheckResponse",
    
    # Assignment
    "SupervisorAssignment",
    "AssignmentRequest",
    "AssignmentUpdate",
    "RevokeAssignmentRequest",
    
    # Activity
    "SupervisorActivityLog",
    "ActivitySummary",
    "ActivityDetail",
    "ActivityFilterParams",
    
    # Dashboard
    "SupervisorDashboard",
    "DashboardMetrics",
    "TaskSummary",
    "RecentComplaintItem",
    "RecentMaintenanceItem",
    "PendingLeaveItem",
    "TodaySchedule",
    "ScheduledMaintenanceItem",
    "ScheduledMeeting",
    "DashboardAlert",
    "QuickActions",
    "PerformanceIndicators",
    
    # Performance
    "PerformanceMetrics",
    "PerformanceReport",
    "PerformanceReview",
    "ComplaintPerformance",
    "AttendancePerformance",
    "MaintenancePerformance",
]
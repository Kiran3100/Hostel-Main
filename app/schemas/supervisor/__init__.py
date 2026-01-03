# app/schemas/supervisor/__init__.py
"""
Supervisor schemas package with complete exports
"""

# Base supervisor schemas
from app.schemas.supervisor.supervisor_base import (
    SupervisorBase,
    SupervisorCreate,
    SupervisorUpdate,
    SupervisorStatusUpdate,
    SupervisorReassignment,
    SupervisorTermination,
)

# Response schemas
from app.schemas.supervisor.supervisor_response import (
    SupervisorResponse,
    SupervisorDetail,
    SupervisorListItem,
    SupervisorSummary,
    SupervisorEmploymentInfo,
    SupervisorStatistics,
)

# Profile schemas
from app.schemas.supervisor.supervisor_profile import (
    SupervisorProfile,
    SupervisorEmployment,
    SupervisorProfileUpdate,
    PerformanceSummary,
    EmploymentHistory,
    SupervisorPreferences,
)

# Permission schemas
from app.schemas.supervisor.supervisor_permissions import (
    SupervisorPermissions,
    PermissionUpdate as SupervisorPermissionsUpdate,
    PermissionCheckRequest,
    PermissionCheckResponse,
    BulkPermissionUpdate,
    PermissionTemplate as SupervisorPermissionTemplate,
    ApplyPermissionTemplate,
    PermissionAuditLog as SupervisorPermissionHistory,
)

# Assignment schemas
from app.schemas.supervisor.supervisor_assignment import (
    SupervisorAssignment,
    AssignmentRequest as SupervisorAssignmentCreate,
    AssignmentUpdate as SupervisorAssignmentUpdate,
    RevokeAssignmentRequest,
    AssignmentTransfer as SupervisorAssignmentTransfer,
    AssignmentSummary,
)

# Activity schemas
from app.schemas.supervisor.supervisor_activity import (
    SupervisorActivityLog as SupervisorActivityLogResponse,
    ActivityDetail,
    ActivitySummary as SupervisorActivitySummary,
    ActivityFilterParams,
    ActivityExportRequest,
    TopActivity,
    ActivityTimelinePoint,
    ActivityMetrics,
    SupervisorActivityCreate,
    SupervisorActivityBulkCreate,
    SupervisorActivityTimeline,
)

# Dashboard schemas
from app.schemas.supervisor.supervisor_dashboard import (
    SupervisorDashboard as SupervisorDashboardAnalytics,
    DashboardMetrics as SupervisorDashboardMetrics,
    TaskSummary as SupervisorRecentTasks,
    RecentComplaintItem,
    RecentMaintenanceItem,
    PendingLeaveItem,
    TodaySchedule,
    ScheduledMaintenanceItem,
    ScheduledMeeting,
    DashboardAlert,
    QuickActions,
    PerformanceIndicators,
    SupervisorDashboardAlerts,
)

# Performance schemas
from app.schemas.supervisor.supervisor_performance import (
    PerformanceMetrics as SupervisorPerformanceMetrics,
    PerformanceReport as SupervisorPerformanceReport,
    ComplaintPerformance,
    AttendancePerformance,
    MaintenancePerformance,
    PerformanceTrendPoint,
    PeerComparison,
    MetricComparison,
    PeriodComparison,
    PerformanceReview,
    PerformanceReviewResponse,
    PerformanceGoal,
    PerformanceGoalProgress,
    PerformanceInsights,
    PerformanceReviewCreate,
    PerformanceReviewUpdate,
    SupervisorPerformanceTrends,
    PerformanceRating,
)

# Enhanced assignment detail (alias for API compatibility)
SupervisorAssignmentDetail = SupervisorAssignment

__all__ = [
    # Base
    "SupervisorBase",
    "SupervisorCreate",
    "SupervisorUpdate",
    "SupervisorStatusUpdate",
    "SupervisorReassignment",
    "SupervisorTermination",
    
    # Response
    "SupervisorResponse",
    "SupervisorDetail",
    "SupervisorListItem",
    "SupervisorSummary",
    "SupervisorEmploymentInfo",
    "SupervisorStatistics",
    
    # Profile
    "SupervisorProfile",
    "SupervisorEmployment",
    "SupervisorProfileUpdate",
    "PerformanceSummary",
    "EmploymentHistory",
    "SupervisorPreferences",
    
    # Permissions
    "SupervisorPermissions",
    "SupervisorPermissionsUpdate",
    "PermissionCheckRequest",
    "PermissionCheckResponse",
    "BulkPermissionUpdate",
    "SupervisorPermissionTemplate",
    "ApplyPermissionTemplate",
    "SupervisorPermissionHistory",
    
    # Assignment
    "SupervisorAssignment",
    "SupervisorAssignmentCreate",
    "SupervisorAssignmentUpdate",
    "SupervisorAssignmentDetail",
    "RevokeAssignmentRequest",
    "SupervisorAssignmentTransfer",
    "AssignmentSummary",
    
    # Activity
    "SupervisorActivityLogResponse",
    "SupervisorActivityCreate",
    "SupervisorActivityBulkCreate",
    "SupervisorActivitySummary",
    "SupervisorActivityTimeline",
    "ActivityDetail",
    "ActivityFilterParams",
    "ActivityExportRequest",
    "TopActivity",
    "ActivityTimelinePoint",
    "ActivityMetrics",
    
    # Dashboard
    "SupervisorDashboardAnalytics",
    "SupervisorDashboardMetrics",
    "SupervisorDashboardAlerts",
    "SupervisorRecentTasks",
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
    "SupervisorPerformanceMetrics",
    "SupervisorPerformanceReport",
    "SupervisorPerformanceTrends",
    "PerformanceReviewCreate",
    "PerformanceReviewUpdate",
    "PerformanceRating",
    "ComplaintPerformance",
    "AttendancePerformance", 
    "MaintenancePerformance",
    "PerformanceTrendPoint",
    "PeerComparison",
    "MetricComparison",
    "PeriodComparison",
    "PerformanceReview",
    "PerformanceReviewResponse",
    "PerformanceGoal",
    "PerformanceGoalProgress",
    "PerformanceInsights",
]
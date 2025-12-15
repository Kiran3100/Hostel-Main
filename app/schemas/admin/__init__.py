from __future__ import annotations

from app.schemas.admin.admin_hostel_assignment import (
    AdminHostelAssignment,
    AssignmentCreate,
    AssignmentList,
    AssignmentUpdate,
    BulkAssignment,
    HostelAdminItem,
    HostelAdminList,
    RevokeAssignment,
)
from app.schemas.admin.admin_override import (
    AdminOverrideRequest,
    OverrideLog,
    OverrideReason,
    OverrideSummary,
    SupervisorOverrideStats,
)
from app.schemas.admin.admin_permissions import (
    AdminPermissions,
    PermissionCheck,
    PermissionMatrix,
    RolePermissions,
)
from app.schemas.admin.hostel_context import (
    ActiveHostelResponse,
    ContextHistory,
    ContextSwitch,
    HostelContext,
    HostelSwitchRequest,
)
from app.schemas.admin.hostel_selector import (
    FavoriteHostelItem,
    FavoriteHostels,
    HostelSelectorItem,
    HostelSelectorResponse,
    RecentHostelItem,
    RecentHostels,
    UpdateFavoriteRequest,
)
from app.schemas.admin.multi_hostel_dashboard import (
    AggregatedStats,
    BottomPerformer,
    CrossHostelComparison,
    HostelMetricComparison,
    HostelQuickStats,
    HostelTaskSummary,
    MultiHostelDashboard,
    TopPerformer,
)

__all__ = [
    # Hostel Assignment Management
    "AdminHostelAssignment",
    "AssignmentCreate",
    "AssignmentUpdate",
    "BulkAssignment",
    "RevokeAssignment",
    "AssignmentList",
    "HostelAdminList",
    "HostelAdminItem",
    
    # Hostel Context Management
    "HostelContext",
    "HostelSwitchRequest",
    "ActiveHostelResponse",
    "ContextHistory",
    "ContextSwitch",
    
    # Hostel Selector UI
    "HostelSelectorResponse",
    "HostelSelectorItem",
    "RecentHostels",
    "RecentHostelItem",
    "FavoriteHostels",
    "FavoriteHostelItem",
    "UpdateFavoriteRequest",
    
    # Multi-Hostel Dashboard
    "MultiHostelDashboard",
    "AggregatedStats",
    "HostelQuickStats",
    "CrossHostelComparison",
    "TopPerformer",
    "BottomPerformer",
    "HostelMetricComparison",
    "HostelTaskSummary",
    
    # Admin Override System
    "AdminOverrideRequest",
    "OverrideLog",
    "OverrideReason",
    "OverrideSummary",
    "SupervisorOverrideStats",
    
    # Admin Permissions
    "AdminPermissions",
    "PermissionMatrix",
    "RolePermissions",
    "PermissionCheck",
]


# Package metadata
__author__ = "Hostel Management System Team"
__description__ = "Admin management schemas for multi-hostel operations"
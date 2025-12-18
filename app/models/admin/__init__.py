"""
Admin Module Models

Comprehensive admin management models for multi-hostel operations including
user management, permissions, assignments, overrides, context switching,
and dashboard analytics.
"""

from __future__ import annotations

from app.models.admin.admin_hostel_assignment import (
    AdminHostelAssignment,
    AssignmentHistory,
    AssignmentPermission,
    PrimaryHostelDesignation,
)
from app.models.admin.admin_override import (
    AdminOverride,
    OverrideApproval,
    OverrideImpact,
    OverrideReason,
)
from app.models.admin.admin_permissions import (
    AdminPermission,
    PermissionAudit,
    PermissionGroup,
    PermissionTemplate,
    RolePermission,
)
from app.models.admin.admin_user import (
    AdminProfile,
    AdminRole,
    AdminSession,
    AdminUser,
)
from app.models.admin.hostel_context import (
    ContextPreference,
    ContextSnapshot,
    ContextSwitch,
    HostelContext,
)
from app.models.admin.hostel_selector import (
    FavoriteHostel,
    HostelQuickStats,
    HostelSelectorCache,
    RecentHostel,
)
from app.models.admin.multi_hostel_dashboard import (
    CrossHostelMetric,
    DashboardSnapshot,
    DashboardWidget,
    HostelPerformanceRanking,
    MultiHostelDashboard,
)

__all__ = [
    # Admin User Management
    "AdminUser",
    "AdminProfile",
    "AdminRole",
    "AdminSession",
    
    # Admin Permissions
    "AdminPermission",
    "PermissionGroup",
    "RolePermission",
    "PermissionAudit",
    "PermissionTemplate",
    
    # Hostel Assignments
    "AdminHostelAssignment",
    "AssignmentPermission",
    "AssignmentHistory",
    "PrimaryHostelDesignation",
    
    # Admin Overrides
    "AdminOverride",
    "OverrideReason",
    "OverrideApproval",
    "OverrideImpact",
    
    # Hostel Context Management
    "HostelContext",
    "ContextSwitch",
    "ContextPreference",
    "ContextSnapshot",
    
    # Hostel Selector
    "RecentHostel",
    "FavoriteHostel",
    "HostelQuickStats",
    "HostelSelectorCache",
    
    # Multi-Hostel Dashboard
    "MultiHostelDashboard",
    "CrossHostelMetric",
    "HostelPerformanceRanking",
    "DashboardWidget",
    "DashboardSnapshot",
]


# Module metadata
__version__ = "1.0.0"
__author__ = "Hostel Management System Team"
__description__ = "Admin module models for multi-hostel operations"


# Model groups for easy import
ADMIN_USER_MODELS = [
    AdminUser,
    AdminProfile,
    AdminRole,
    AdminSession,
]

PERMISSION_MODELS = [
    AdminPermission,
    PermissionGroup,
    RolePermission,
    PermissionAudit,
    PermissionTemplate,
]

ASSIGNMENT_MODELS = [
    AdminHostelAssignment,
    AssignmentPermission,
    AssignmentHistory,
    PrimaryHostelDesignation,
]

OVERRIDE_MODELS = [
    AdminOverride,
    OverrideReason,
    OverrideApproval,
    OverrideImpact,
]

CONTEXT_MODELS = [
    HostelContext,
    ContextSwitch,
    ContextPreference,
    ContextSnapshot,
]

SELECTOR_MODELS = [
    RecentHostel,
    FavoriteHostel,
    HostelQuickStats,
    HostelSelectorCache,
]

DASHBOARD_MODELS = [
    MultiHostelDashboard,
    CrossHostelMetric,
    HostelPerformanceRanking,
    DashboardWidget,
    DashboardSnapshot,
]

# All models in dependency order for migrations
ALL_MODELS_ORDERED = [
    # 1. Core admin user models (no dependencies)
    AdminRole,
    AdminUser,
    AdminProfile,
    AdminSession,
    
    # 2. Permission models (depend on AdminUser, AdminRole)
    PermissionGroup,
    PermissionTemplate,
    AdminPermission,
    RolePermission,
    PermissionAudit,
    
    # 3. Assignment models (depend on AdminUser, Hostel)
    AdminHostelAssignment,
    AssignmentPermission,
    AssignmentHistory,
    PrimaryHostelDesignation,
    
    # 4. Override models (depend on AdminUser, Supervisor, Hostel)
    OverrideReason,
    AdminOverride,
    OverrideApproval,
    OverrideImpact,
    
    # 5. Context models (depend on AdminUser, Hostel)
    HostelContext,
    ContextSwitch,
    ContextPreference,
    ContextSnapshot,
    
    # 6. Selector models (depend on AdminUser, Hostel)
    RecentHostel,
    FavoriteHostel,
    HostelQuickStats,
    HostelSelectorCache,
    
    # 7. Dashboard models (depend on AdminUser, Hostel)
    MultiHostelDashboard,
    CrossHostelMetric,
    HostelPerformanceRanking,
    DashboardWidget,
    DashboardSnapshot,
]


def get_model_by_name(model_name: str):
    """
    Get model class by name.
    
    Args:
        model_name: Name of the model class
        
    Returns:
        Model class or None if not found
    """
    return globals().get(model_name)


def get_models_by_category(category: str) -> list:
    """
    Get all models in a specific category.
    
    Args:
        category: Category name (user, permission, assignment, override, 
                 context, selector, dashboard)
        
    Returns:
        List of model classes in the category
    """
    category_map = {
        "user": ADMIN_USER_MODELS,
        "permission": PERMISSION_MODELS,
        "assignment": ASSIGNMENT_MODELS,
        "override": OVERRIDE_MODELS,
        "context": CONTEXT_MODELS,
        "selector": SELECTOR_MODELS,
        "dashboard": DASHBOARD_MODELS,
    }
    return category_map.get(category.lower(), [])


# Relationship back-population helpers
def setup_relationships():
    """
    Setup bidirectional relationships after all models are defined.
    This is called automatically when the module is imported.
    """
    # AdminUser relationships
    AdminUser.permissions = relationship(
        "AdminPermission",
        back_populates="admin",
        lazy="select"
    )
    
    AdminUser.role_assignments = relationship(
        "RolePermission",
        secondary="admin_role_assignments",  # If you have a junction table
        lazy="select"
    )
    
    # Add more relationship setups as needed


# Auto-setup relationships on import
# setup_relationships()
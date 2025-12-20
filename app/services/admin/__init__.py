"""
Admin Services Module

Business logic layer for admin module operations.
Orchestrates repositories and implements complex workflows.
"""

from app.services.admin.admin_user_service import AdminUserService
from app.services.admin.admin_authentication_service import AdminAuthenticationService
from app.services.admin.admin_permission_service import AdminPermissionService
from app.services.admin.admin_role_service import AdminRoleService
from app.services.admin.admin_activity_service import AdminActivityService
from app.services.admin.admin_override_service import AdminOverrideService
from app.services.admin.hostel_assignment_service import HostelAssignmentService
from app.services.admin.hostel_context_service import HostelContextService
from app.services.admin.hostel_selector_service import HostelSelectorService
from app.services.admin.multi_hostel_dashboard_service import MultiHostelDashboardService


__all__ = [
    # Core User Management
    "AdminUserService",
    "AdminAuthenticationService",
    
    # Access Control
    "AdminPermissionService",
    "AdminRoleService",
    
    # Operations
    "AdminActivityService",
    "AdminOverrideService",
    "HostelAssignmentService",
    
    # UX & Performance
    "HostelContextService",
    "HostelSelectorService",
    
    # Analytics
    "MultiHostelDashboardService",
]


# Service factory for dependency injection
class AdminServiceFactory:
    """
    Factory for creating admin service instances.
    Centralizes service creation and dependency management.
    """

    def __init__(self, db_session):
        """
        Initialize factory with database session.
        
        Args:
            db_session: SQLAlchemy session
        """
        self.db = db_session
        self._services = {}

    def get_admin_user_service(self) -> AdminUserService:
        """Get or create AdminUserService instance."""
        if 'admin_user' not in self._services:
            self._services['admin_user'] = AdminUserService(self.db)
        return self._services['admin_user']

    def get_authentication_service(self) -> AdminAuthenticationService:
        """Get or create AdminAuthenticationService instance."""
        if 'authentication' not in self._services:
            self._services['authentication'] = AdminAuthenticationService(self.db)
        return self._services['authentication']

    def get_permission_service(self) -> AdminPermissionService:
        """Get or create AdminPermissionService instance."""
        if 'permission' not in self._services:
            self._services['permission'] = AdminPermissionService(self.db)
        return self._services['permission']

    def get_role_service(self) -> AdminRoleService:
        """Get or create AdminRoleService instance."""
        if 'role' not in self._services:
            self._services['role'] = AdminRoleService(self.db)
        return self._services['role']

    def get_activity_service(self) -> AdminActivityService:
        """Get or create AdminActivityService instance."""
        if 'activity' not in self._services:
            self._services['activity'] = AdminActivityService(self.db)
        return self._services['activity']

    def get_override_service(self) -> AdminOverrideService:
        """Get or create AdminOverrideService instance."""
        if 'override' not in self._services:
            self._services['override'] = AdminOverrideService(self.db)
        return self._services['override']

    def get_assignment_service(self) -> HostelAssignmentService:
        """Get or create HostelAssignmentService instance."""
        if 'assignment' not in self._services:
            self._services['assignment'] = HostelAssignmentService(self.db)
        return self._services['assignment']

    def get_context_service(self) -> HostelContextService:
        """Get or create HostelContextService instance."""
        if 'context' not in self._services:
            self._services['context'] = HostelContextService(self.db)
        return self._services['context']

    def get_selector_service(self) -> HostelSelectorService:
        """Get or create HostelSelectorService instance."""
        if 'selector' not in self._services:
            self._services['selector'] = HostelSelectorService(self.db)
        return self._services['selector']

    def get_dashboard_service(self) -> MultiHostelDashboardService:
        """Get or create MultiHostelDashboardService instance."""
        if 'dashboard' not in self._services:
            self._services['dashboard'] = MultiHostelDashboardService(self.db)
        return self._services['dashboard']

    def clear_cache(self) -> None:
        """Clear all cached service instances."""
        self._services.clear()


# Convenience function
def get_admin_service_factory(db_session) -> AdminServiceFactory:
    """
    Get admin service factory instance.
    
    Args:
        db_session: SQLAlchemy database session
        
    Returns:
        AdminServiceFactory instance
    """
    return AdminServiceFactory(db_session)


# Module metadata
__version__ = "1.0.0"
__author__ = "Hostel Management System Team"
__description__ = "Admin module business logic services"


# Service groups for organized imports
CORE_SERVICES = [
    AdminUserService,
    AdminAuthenticationService,
]

ACCESS_CONTROL_SERVICES = [
    AdminPermissionService,
    AdminRoleService,
]

OPERATIONAL_SERVICES = [
    AdminActivityService,
    AdminOverrideService,
    HostelAssignmentService,
]

UX_SERVICES = [
    HostelContextService,
    HostelSelectorService,
]

ANALYTICS_SERVICES = [
    MultiHostelDashboardService,
]
"""
Admin Module Repositories

Provides data access layer for all admin-related operations including
user management, permissions, assignments, overrides, context switching,
hostel selection, and multi-hostel dashboards.
"""

from app.repositories.admin.admin_user_repository import AdminUserRepository
from app.repositories.admin.admin_permissions_repository import AdminPermissionsRepository
from app.repositories.admin.admin_hostel_assignment_repository import AdminHostelAssignmentRepository
from app.repositories.admin.admin_override_repository import AdminOverrideRepository
from app.repositories.admin.hostel_context_repository import HostelContextRepository
from app.repositories.admin.hostel_selector_repository import HostelSelectorRepository
from app.repositories.admin.multi_hostel_dashboard_repository import MultiHostelDashboardRepository


__all__ = [
    # Core Admin Management
    "AdminUserRepository",
    "AdminPermissionsRepository",
    
    # Assignment & Access Control
    "AdminHostelAssignmentRepository",
    "AdminOverrideRepository",
    
    # UX & Performance
    "HostelContextRepository",
    "HostelSelectorRepository",
    
    # Analytics & Reporting
    "MultiHostelDashboardRepository",
]


# Repository factory for dependency injection
class AdminRepositoryFactory:
    """
    Factory for creating admin repository instances.
    Supports dependency injection and centralized configuration.
    """
    
    def __init__(self, db_session):
        """
        Initialize factory with database session.
        
        Args:
            db_session: SQLAlchemy session
        """
        self.db = db_session
        self._repositories = {}
    
    def get_admin_user_repository(self) -> AdminUserRepository:
        """Get or create AdminUserRepository instance."""
        if 'admin_user' not in self._repositories:
            self._repositories['admin_user'] = AdminUserRepository(self.db)
        return self._repositories['admin_user']
    
    def get_admin_permissions_repository(self) -> AdminPermissionsRepository:
        """Get or create AdminPermissionsRepository instance."""
        if 'admin_permissions' not in self._repositories:
            self._repositories['admin_permissions'] = AdminPermissionsRepository(self.db)
        return self._repositories['admin_permissions']
    
    def get_admin_assignment_repository(self) -> AdminHostelAssignmentRepository:
        """Get or create AdminHostelAssignmentRepository instance."""
        if 'admin_assignment' not in self._repositories:
            self._repositories['admin_assignment'] = AdminHostelAssignmentRepository(self.db)
        return self._repositories['admin_assignment']
    
    def get_admin_override_repository(self) -> AdminOverrideRepository:
        """Get or create AdminOverrideRepository instance."""
        if 'admin_override' not in self._repositories:
            self._repositories['admin_override'] = AdminOverrideRepository(self.db)
        return self._repositories['admin_override']
    
    def get_hostel_context_repository(self) -> HostelContextRepository:
        """Get or create HostelContextRepository instance."""
        if 'hostel_context' not in self._repositories:
            self._repositories['hostel_context'] = HostelContextRepository(self.db)
        return self._repositories['hostel_context']
    
    def get_hostel_selector_repository(self) -> HostelSelectorRepository:
        """Get or create HostelSelectorRepository instance."""
        if 'hostel_selector' not in self._repositories:
            self._repositories['hostel_selector'] = HostelSelectorRepository(self.db)
        return self._repositories['hostel_selector']
    
    def get_dashboard_repository(self) -> MultiHostelDashboardRepository:
        """Get or create MultiHostelDashboardRepository instance."""
        if 'dashboard' not in self._repositories:
            self._repositories['dashboard'] = MultiHostelDashboardRepository(self.db)
        return self._repositories['dashboard']
    
    def clear_cache(self) -> None:
        """Clear all cached repository instances."""
        self._repositories.clear()


# Convenience function for getting repository factory
def get_admin_repository_factory(db_session) -> AdminRepositoryFactory:
    """
    Get admin repository factory instance.
    
    Args:
        db_session: SQLAlchemy database session
        
    Returns:
        AdminRepositoryFactory instance
    """
    return AdminRepositoryFactory(db_session)


# Module metadata
__version__ = "1.0.0"
__author__ = "Hostel Management System Team"
__description__ = "Admin module data access repositories"
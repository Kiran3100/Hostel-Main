"""
Admin service layer.

This package provides comprehensive business logic for admin-related operations
including user management, permissions, hostel assignments, context switching,
activity tracking, and multi-hostel dashboard analytics.

The services follow a layered architecture:
- BaseService: Common functionality and error handling
- Domain Services: Business logic implementation
- Repositories: Data access abstraction

All services use the ServiceResult pattern for consistent error handling
and return value wrapping.
"""

from app.services.admin.admin_user_service import AdminUserService
from app.services.admin.admin_permission_service import AdminPermissionService
from app.services.admin.admin_role_service import AdminRoleService
from app.services.admin.hostel_assignment_service import HostelAssignmentService
from app.services.admin.admin_override_service import AdminOverrideService
from app.services.admin.hostel_context_service import HostelContextService
from app.services.admin.hostel_selector_service import HostelSelectorService
from app.services.admin.multi_hostel_dashboard_service import MultiHostelDashboardService
from app.services.admin.admin_authentication_service import AdminAuthenticationService
from app.services.admin.admin_activity_service import AdminActivityService

__all__ = [
    # Core admin services
    "AdminUserService",
    "AdminPermissionService",
    "AdminRoleService",
    
    # Hostel assignment services
    "HostelAssignmentService",
    "AdminOverrideService",
    
    # Context and UI services
    "HostelContextService",
    "HostelSelectorService",
    "MultiHostelDashboardService",
    
    # Authentication and activity
    "AdminAuthenticationService",
    "AdminActivityService",
]

__version__ = "1.0.0"
__author__ = "Hostel Management System"
__description__ = "Admin service layer providing business logic for admin operations"
# app/services/admin/__init__.py
"""
Admin-facing services.

- AdminHostelAssignmentService: manage admin ↔ hostel assignments.
- AdminOverrideService: record and inspect admin overrides of supervisor actions.
- MultiHostelDashboardService: aggregated dashboard for multi-hostel admins.
- PermissionMatrixService: manage global role → permissions matrix.
- SuperAdminDashboardService: platform-wide analytics for super admins.
"""

from .admin_hostel_assignment_service import AdminHostelAssignmentService
from .admin_override_service import AdminOverrideService
from .multi_hostel_dashboard_service import MultiHostelDashboardService
from .permission_matrix_service import PermissionMatrixService
from .super_admin_dashboard_service import SuperAdminDashboardService

__all__ = [
    "AdminHostelAssignmentService",
    "AdminOverrideService",
    "MultiHostelDashboardService",
    "PermissionMatrixService",
    "SuperAdminDashboardService",
]
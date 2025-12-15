# app/services/supervisor/__init__.py
"""
Supervisor-related services.

- SupervisorService:
    Core CRUD, listing, and detail for supervisors.

- SupervisorAssignmentService:
    Assign / revoke supervisors to hostels (multi-hostel support).

- SupervisorPermissionsService:
    Manage supervisor permissions and perform permission checks.

- SupervisorDashboardService:
    Supervisor dashboard aggregation (complaints, maintenance, attendance, etc.).

- SupervisorPerformanceService:
    Performance metrics & reports based on analytics tables.

- SupervisorActivityService:
    Activity log listing, details, and summaries for supervisors.
"""

from .supervisor_service import SupervisorService
from .supervisor_assignment_service import SupervisorAssignmentService
from .supervisor_permissions_service import SupervisorPermissionsService
from .supervisor_dashboard_service import SupervisorDashboardService
from .supervisor_performance_service import SupervisorPerformanceService
from .supervisor_activity_service import SupervisorActivityService

__all__ = [
    "SupervisorService",
    "SupervisorAssignmentService",
    "SupervisorPermissionsService",
    "SupervisorDashboardService",
    "SupervisorPerformanceService",
    "SupervisorActivityService",
]
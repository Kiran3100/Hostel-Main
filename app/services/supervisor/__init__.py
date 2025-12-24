"""
Supervisor services package.

Provides services for:

- Core supervisor CRUD and profile:
  - SupervisorService

- Assignments:
  - SupervisorAssignmentService

- Activity and logging:
  - SupervisorActivityService

- Dashboards:
  - SupervisorDashboardService

- Performance & reviews:
  - SupervisorPerformanceService

- Permissions:
  - SupervisorPermissionService

- Scheduling:
  - SupervisorSchedulingService

- Training recommendations:
  - SupervisorTrainingService
"""

from .supervisor_activity_service import SupervisorActivityService
from .supervisor_assignment_service import SupervisorAssignmentService
from .supervisor_dashboard_service import SupervisorDashboardService
from .supervisor_performance_service import SupervisorPerformanceService
from .supervisor_permission_service import SupervisorPermissionService
from .supervisor_scheduling_service import SupervisorSchedulingService
from .supervisor_service import SupervisorService
from .supervisor_training_service import SupervisorTrainingService

__all__ = [
    "SupervisorActivityService",
    "SupervisorAssignmentService",
    "SupervisorDashboardService",
    "SupervisorPerformanceService",
    "SupervisorPermissionService",
    "SupervisorSchedulingService",
    "SupervisorService",
    "SupervisorTrainingService",
]
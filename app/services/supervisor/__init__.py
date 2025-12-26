"""
Supervisor services package.

Provides comprehensive services for supervisor management:

- Core supervisor CRUD and profile:
  - SupervisorService: Main supervisor operations and profile management

- Assignments:
  - SupervisorAssignmentService: Manage supervisor-hostel assignments and transfers

- Activity and logging:
  - SupervisorActivityService: Track and analyze supervisor activities

- Dashboards:
  - SupervisorDashboardService: Build comprehensive dashboard views

- Performance & reviews:
  - SupervisorPerformanceService: Handle performance metrics, reports, and reviews

- Permissions:
  - SupervisorPermissionService: Manage permissions and role-based access

- Scheduling:
  - SupervisorSchedulingService: Manage daily/weekly/monthly schedules

- Training recommendations:
  - SupervisorTrainingService: Generate training recommendations and learning paths

All services follow consistent patterns:
- Comprehensive error handling with ValidationException
- Detailed logging for debugging and audit trails
- Input validation on all methods
- Type hints and comprehensive docstrings
- Example usage in docstrings

Example usage:
    >>> from app.services.supervisor import (
    ...     SupervisorService,
    ...     SupervisorDashboardService,
    ...     SupervisorPermissionService
    ... )
    >>> 
    >>> # Initialize services with repositories
    >>> supervisor_service = SupervisorService(supervisor_repo, aggregate_repo)
    >>> dashboard_service = SupervisorDashboardService(dashboard_repo)
    >>> permission_service = SupervisorPermissionService(permissions_repo)
    >>> 
    >>> # Use services
    >>> supervisor = supervisor_service.get_supervisor(db, supervisor_id)
    >>> dashboard = dashboard_service.get_dashboard(db, supervisor_id, hostel_id)
    >>> permissions = permission_service.get_permissions(db, supervisor_id)
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

__version__ = "1.0.0"
__author__ = "Hostel Management System"
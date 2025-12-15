# app/services/maintenance/__init__.py
"""
Maintenance services package.

- MaintenanceService: core CRUD, listing, status, hostel summary.
- MaintenanceAssignmentService: assign/reassign tasks to supervisors.
- MaintenanceApprovalService: cost approval with hostel-specific thresholds.
- MaintenanceCompletionService: completion details, quality checks, certificates.
- MaintenanceCostService: cost tracking, budgets, expense reports & analysis.
- MaintenanceScheduleService: preventive maintenance scheduling (store-based).
- MaintenanceAnalyticsService: basic analytics for maintenance requests.
- MaintenanceWorkflowService: wrapper over wf_maintenance table.
"""

from .maintenance_service import MaintenanceService
from .maintenance_assignment_service import MaintenanceAssignmentService
from .maintenance_approval_service import MaintenanceApprovalService
from .maintenance_completion_service import MaintenanceCompletionService
from .maintenance_cost_service import MaintenanceCostService
from .maintenance_schedule_service import MaintenanceScheduleService
from .maintenance_analytics_service import MaintenanceAnalyticsService
from .maintenance_workflow_service import MaintenanceWorkflowService

__all__ = [
    "MaintenanceService",
    "MaintenanceAssignmentService",
    "MaintenanceApprovalService",
    "MaintenanceCompletionService",
    "MaintenanceCostService",
    "MaintenanceScheduleService",
    "MaintenanceAnalyticsService",
    "MaintenanceWorkflowService",
]
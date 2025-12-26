"""
Maintenance services package.

Provides services for:

- Requests:
  - MaintenanceRequestService

- Approvals:
  - MaintenanceApprovalService

- Assignments:
  - MaintenanceAssignmentService

- Completion & QC:
  - MaintenanceCompletionService

- Costs & Budgets:
  - MaintenanceCostService

- Scheduling:
  - MaintenanceScheduleService

- Vendors:
  - MaintenanceVendorService

- Analytics:
  - MaintenanceAnalyticsService

- Predictive:
  - PredictiveMaintenanceService
"""

from .maintenance_analytics_service import MaintenanceAnalyticsService
from .maintenance_approval_service import MaintenanceApprovalService
from .maintenance_assignment_service import MaintenanceAssignmentService
from .maintenance_completion_service import MaintenanceCompletionService
from .maintenance_cost_service import MaintenanceCostService
from .maintenance_request_service import MaintenanceRequestService
from .maintenance_schedule_service import MaintenanceScheduleService
from .maintenance_vendor_service import MaintenanceVendorService
from .predictive_maintenance_service import PredictiveMaintenanceService

__all__ = [
    "MaintenanceAnalyticsService",
    "MaintenanceApprovalService",
    "MaintenanceAssignmentService",
    "MaintenanceCompletionService",
    "MaintenanceCostService",
    "MaintenanceRequestService",
    "MaintenanceScheduleService",
    "MaintenanceVendorService",
    "PredictiveMaintenanceService",
]
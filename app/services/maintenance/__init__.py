"""
Maintenance services package.

Provides comprehensive services for maintenance management including:

- **Requests**: MaintenanceRequestService
  - Request lifecycle management
  - Emergency request handling
  - Request tracking and status updates

- **Approvals**: MaintenanceApprovalService
  - Multi-level approval workflows
  - Threshold-based routing
  - Approval delegation

- **Assignments**: MaintenanceAssignmentService
  - Staff and vendor assignments
  - Workload balancing
  - Assignment history tracking

- **Completion**: MaintenanceCompletionService
  - Work completion documentation
  - Quality checks and inspections
  - Completion certificates

- **Costs**: MaintenanceCostService
  - Cost tracking and budgeting
  - Expense reporting
  - Budget compliance monitoring

- **Schedules**: MaintenanceScheduleService
  - Preventive maintenance scheduling
  - Schedule execution tracking
  - Compliance reporting

- **Vendors**: MaintenanceVendorService
  - Vendor management
  - Contract tracking
  - Performance reviews

- **Analytics**: MaintenanceAnalyticsService
  - Comprehensive analytics and KPIs
  - Performance metrics
  - Category and vendor analytics

- **Predictive**: PredictiveMaintenanceService
  - Risk assessment
  - Failure prediction
  - Preventive action recommendations
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

__version__ = "1.0.0"
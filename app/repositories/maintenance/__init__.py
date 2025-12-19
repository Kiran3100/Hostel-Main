# app/repositories/maintenance/__init__.py
"""
Maintenance module repositories.

Comprehensive repository layer for all maintenance-related
database operations and business logic.
"""

from app.repositories.maintenance.maintenance_request_repository import (
    MaintenanceRequestRepository,
)
from app.repositories.maintenance.maintenance_assignment_repository import (
    MaintenanceAssignmentRepository,
    VendorAssignmentRepository,
)
from app.repositories.maintenance.maintenance_approval_repository import (
    MaintenanceApprovalRepository,
)
from app.repositories.maintenance.maintenance_completion_repository import (
    MaintenanceCompletionRepository,
)
from app.repositories.maintenance.maintenance_cost_repository import (
    MaintenanceCostRepository,
)
from app.repositories.maintenance.maintenance_schedule_repository import (
    MaintenanceScheduleRepository,
)
from app.repositories.maintenance.maintenance_vendor_repository import (
    MaintenanceVendorRepository,
)
from app.repositories.maintenance.maintenance_analytics_repository import (
    MaintenanceAnalyticsRepository,
)
from app.repositories.maintenance.maintenance_aggregate_repository import (
    MaintenanceAggregateRepository,
)

__all__ = [
    # Request repositories
    "MaintenanceRequestRepository",
    # Assignment repositories
    "MaintenanceAssignmentRepository",
    "VendorAssignmentRepository",
    # Approval repository
    "MaintenanceApprovalRepository",
    # Completion repository
    "MaintenanceCompletionRepository",
    # Cost repository
    "MaintenanceCostRepository",
    # Schedule repository
    "MaintenanceScheduleRepository",
    # Vendor repository
    "MaintenanceVendorRepository",
    # Analytics repository
    "MaintenanceAnalyticsRepository",
    # Aggregate repository
    "MaintenanceAggregateRepository",
]
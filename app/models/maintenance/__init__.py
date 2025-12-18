# app/models/maintenance/__init__.py
"""
Maintenance module models.

Comprehensive maintenance management models including requests,
assignments, approvals, completions, costs, schedules, vendors,
and analytics.
"""

from app.models.maintenance.maintenance_analytics import (
    CategoryPerformanceMetric,
    MaintenanceAnalytic,
)
from app.models.maintenance.maintenance_approval import (
    ApprovalThreshold,
    ApprovalWorkflow,
    MaintenanceApproval,
)
from app.models.maintenance.maintenance_assignment import (
    MaintenanceAssignment,
    VendorAssignment,
)
from app.models.maintenance.maintenance_completion import (
    MaintenanceCertificate,
    MaintenanceCompletion,
    MaintenanceMaterial,
    MaintenanceQualityCheck,
)
from app.models.maintenance.maintenance_cost import (
    BudgetAllocation,
    CategoryBudget,
    ExpenseReport,
    MaintenanceCost,
    VendorInvoice,
)
from app.models.maintenance.maintenance_request import (
    MaintenanceIssueType,
    MaintenanceRequest,
    MaintenanceStatusHistory,
)
from app.models.maintenance.maintenance_schedule import (
    MaintenanceSchedule,
    ScheduleExecution,
)
from app.models.maintenance.maintenance_vendor import (
    MaintenanceVendor,
    VendorContract,
    VendorPerformanceReview,
)

__all__ = [
    # Request models
    "MaintenanceRequest",
    "MaintenanceStatusHistory",
    "MaintenanceIssueType",
    # Assignment models
    "MaintenanceAssignment",
    "VendorAssignment",
    # Approval models
    "MaintenanceApproval",
    "ApprovalThreshold",
    "ApprovalWorkflow",
    # Completion models
    "MaintenanceCompletion",
    "MaintenanceMaterial",
    "MaintenanceQualityCheck",
    "MaintenanceCertificate",
    # Cost models
    "MaintenanceCost",
    "BudgetAllocation",
    "CategoryBudget",
    "VendorInvoice",
    "ExpenseReport",
    # Schedule models
    "MaintenanceSchedule",
    "ScheduleExecution",
    # Vendor models
    "MaintenanceVendor",
    "VendorContract",
    "VendorPerformanceReview",
    # Analytics models
    "MaintenanceAnalytic",
    "CategoryPerformanceMetric",
]
# --- File: app/schemas/maintenance/__init__.py ---
"""
Maintenance management schemas package.

Comprehensive maintenance request, scheduling, cost tracking, and analytics
schemas for hostel management system with enhanced validation and type safety.

Migrated to Pydantic v2 with full compatibility.
"""

from __future__ import annotations

from app.schemas.maintenance.maintenance_analytics import (
    CategoryBreakdown,
    CostTrendPoint,
    MaintenanceAnalytics,
    PerformanceMetrics,
    ProductivityMetrics,
    TrendPoint,
    VendorPerformance,
)
from app.schemas.maintenance.maintenance_approval import (
    ApprovalRequest,
    ApprovalResponse,
    ApprovalWorkflow,
    RejectionRequest,
    ThresholdConfig,
)
from app.schemas.maintenance.maintenance_assignment import (
    AssignmentEntry,
    AssignmentHistory,
    AssignmentUpdate,
    BulkAssignment,
    TaskAssignment,
    VendorAssignment,
)
from app.schemas.maintenance.maintenance_base import (
    MaintenanceBase,
    MaintenanceCreate,
    MaintenanceStatusUpdate,
    MaintenanceUpdate,
)
from app.schemas.maintenance.maintenance_completion import (
    ChecklistItem,
    CompletionCertificate,
    CompletionRequest,
    CompletionResponse,
    MaterialItem,
    QualityCheck,
)
from app.schemas.maintenance.maintenance_cost import (
    BudgetAllocation,
    CategoryBudget,
    CostAnalysis,
    CostTracking,
    ExpenseItem,
    ExpenseReport,
    InvoiceLineItem,
    MonthlyExpense,
    VendorInvoice,
)
from app.schemas.maintenance.maintenance_filters import (
    AdvancedFilterParams,
    MaintenanceExportRequest,
    MaintenanceFilterParams,
    SearchRequest,
)
from app.schemas.maintenance.maintenance_request import (
    EmergencyRequest,
    MaintenanceRequest,
    RequestSubmission,
)
from app.schemas.maintenance.maintenance_response import (
    MaintenanceDetail,
    MaintenanceResponse,
    MaintenanceSummary,
    RequestListItem,
)
from app.schemas.maintenance.maintenance_schedule import (
    ChecklistResult,
    ExecutionHistoryItem,
    PreventiveSchedule,
    RecurrenceConfig,
    ScheduleChecklistItem,
    ScheduleCreate,
    ScheduleExecution,
    ScheduleHistory,
    ScheduleUpdate,
)

__all__ = [
    # Base schemas
    "MaintenanceBase",
    "MaintenanceCreate",
    "MaintenanceUpdate",
    "MaintenanceStatusUpdate",
    # Request schemas
    "MaintenanceRequest",
    "RequestSubmission",
    "EmergencyRequest",
    # Response schemas
    "MaintenanceResponse",
    "MaintenanceDetail",
    "RequestListItem",
    "MaintenanceSummary",
    # Assignment schemas
    "TaskAssignment",
    "VendorAssignment",
    "AssignmentUpdate",
    "BulkAssignment",
    "AssignmentEntry",
    "AssignmentHistory",
    # Approval schemas
    "ApprovalRequest",
    "ApprovalResponse",
    "ApprovalWorkflow",
    "RejectionRequest",
    "ThresholdConfig",
    # Completion schemas
    "CompletionRequest",
    "CompletionResponse",
    "CompletionCertificate",
    "MaterialItem",
    "QualityCheck",
    "ChecklistItem",
    # Schedule schemas
    "PreventiveSchedule",
    "ScheduleCreate",
    "ScheduleUpdate",
    "ScheduleChecklistItem",
    "RecurrenceConfig",
    "ScheduleExecution",
    "ChecklistResult",
    "ScheduleHistory",
    "ExecutionHistoryItem",
    # Cost schemas
    "CostTracking",
    "BudgetAllocation",
    "CategoryBudget",
    "ExpenseReport",
    "MonthlyExpense",
    "ExpenseItem",
    "VendorInvoice",
    "InvoiceLineItem",
    "CostAnalysis",
    # Filter schemas
    "MaintenanceFilterParams",
    "AdvancedFilterParams",
    "SearchRequest",
    "MaintenanceExportRequest",
    # Analytics schemas
    "MaintenanceAnalytics",
    "TrendPoint",
    "CostTrendPoint",
    "CategoryBreakdown",
    "VendorPerformance",
    "PerformanceMetrics",
    "ProductivityMetrics",
]
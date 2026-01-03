"""
Leave management schemas package.

Comprehensive leave application, approval, and balance tracking schemas
for hostel management system with enhanced validation and type safety.

Migrated to Pydantic v2 with full compatibility.
"""

from __future__ import annotations

from app.schemas.leave.leave_application import (
    LeaveApplicationRequest,
    LeaveCancellationRequest,
)
from app.schemas.leave.leave_approval import (
    LeaveApprovalAction,
    LeaveApprovalRequest,
    LeaveApprovalResponse,
    LeaveApprovalHistoryResponse,
    LeaveApprovalHistoryItem,
    PendingApprovalItem,
)
from app.schemas.leave.leave_balance import (
    LeaveBalance,
    LeaveBalanceSummary,
    LeaveQuota,
    LeaveUsageDetail,
    LeaveBalanceDetail,
    LeaveAdjustment,
    LeaveUsageHistory,
)
from app.schemas.leave.leave_base import (
    LeaveBase,
    LeaveCreate,
    LeaveUpdate,
)
from app.schemas.leave.leave_response import (
    LeaveDetail,
    LeaveListItem,
    LeaveResponse,
    LeaveSummary,
    PaginatedLeaveResponse,
)
from app.schemas.leave.leave_calendar import (
    CalendarEvent,
    CalendarDay,
    StudentCalendarResponse,
    HostelCalendarResponse,
    OccupancyStats,
)

__all__ = [
    # Base schemas
    "LeaveBase",
    "LeaveCreate", 
    "LeaveUpdate",
    # Response schemas
    "LeaveResponse",
    "LeaveDetail",
    "LeaveListItem", 
    "LeaveSummary",
    "PaginatedLeaveResponse",
    # Application schemas
    "LeaveApplicationRequest",
    "LeaveCancellationRequest",
    # Approval schemas
    "LeaveApprovalRequest",
    "LeaveApprovalAction",
    "LeaveApprovalResponse",
    "LeaveApprovalHistoryResponse",
    "LeaveApprovalHistoryItem",
    "PendingApprovalItem",
    # Balance schemas
    "LeaveBalance",
    "LeaveBalanceSummary",
    "LeaveQuota", 
    "LeaveUsageDetail",
    "LeaveBalanceDetail",
    "LeaveAdjustment",
    "LeaveUsageHistory",
    # Calendar schemas
    "CalendarEvent",
    "CalendarDay",
    "StudentCalendarResponse", 
    "HostelCalendarResponse",
    "OccupancyStats",
]
# --- File: app/schemas/leave/__init__.py ---
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
)
from app.schemas.leave.leave_balance import (
    LeaveBalance,
    LeaveBalanceSummary,
    LeaveQuota,
    LeaveUsageDetail,
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
    # Application schemas
    "LeaveApplicationRequest",
    "LeaveCancellationRequest",
    # Approval schemas
    "LeaveApprovalRequest",
    "LeaveApprovalAction",
    "LeaveApprovalResponse",
    # Balance schemas
    "LeaveBalance",
    "LeaveBalanceSummary",
    "LeaveQuota",
    "LeaveUsageDetail",
]
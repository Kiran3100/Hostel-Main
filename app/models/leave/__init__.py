# --- File: C:\Hostel-Main\app\models\leave\__init__.py ---
"""
Leave management models package.

Comprehensive leave application, approval, and balance tracking models
for hostel management system with full audit trail and validation.

Database models using SQLAlchemy ORM with PostgreSQL.
"""

from __future__ import annotations

from app.models.leave.leave_application import (
    LeaveApplication,
    LeaveCancellation,
    LeaveDocument,
    LeaveEmergencyContact,
    LeaveStatusHistory,
)
from app.models.leave.leave_approval import (
    LeaveApproval,
    LeaveApprovalStep,
    LeaveApprovalWorkflow,
)
from app.models.leave.leave_balance import (
    LeaveAdjustment,
    LeaveBalance,
    LeaveCarryForward,
    LeaveQuota,
    LeaveUsage,
)
from app.models.leave.leave_type import (
    LeaveBlackoutDate,
    LeavePolicy,
    LeaveTypeConfig,
)

__all__ = [
    # Application models
    "LeaveApplication",
    "LeaveCancellation",
    "LeaveDocument",
    "LeaveEmergencyContact",
    "LeaveStatusHistory",
    # Approval models
    "LeaveApproval",
    "LeaveApprovalWorkflow",
    "LeaveApprovalStep",
    # Balance models
    "LeaveBalance",
    "LeaveQuota",
    "LeaveUsage",
    "LeaveCarryForward",
    "LeaveAdjustment",
    # Configuration models
    "LeaveTypeConfig",
    "LeavePolicy",
    "LeaveBlackoutDate",
]
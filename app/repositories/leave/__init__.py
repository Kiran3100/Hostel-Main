"""
Leave repositories package.

Comprehensive repository layer for leave management with advanced
querying, analytics, and aggregation capabilities.
"""

from app.repositories.leave.leave_application_repository import (
    LeaveApplicationRepository,
)
from app.repositories.leave.leave_approval_repository import (
    LeaveApprovalRepository,
    LeaveApprovalWorkflowRepository,
)
from app.repositories.leave.leave_balance_repository import (
    LeaveBalanceRepository,
)
from app.repositories.leave.leave_type_repository import (
    LeaveTypeRepository,
    LeavePolicyRepository,
    LeaveBlackoutDateRepository,
)
from app.repositories.leave.leave_aggregate_repository import (
    LeaveAggregateRepository,
)

__all__ = [
    # Application repositories
    "LeaveApplicationRepository",
    
    # Approval repositories
    "LeaveApprovalRepository",
    "LeaveApprovalWorkflowRepository",
    
    # Balance repositories
    "LeaveBalanceRepository",
    
    # Type and configuration repositories
    "LeaveTypeRepository",
    "LeavePolicyRepository",
    "LeaveBlackoutDateRepository",
    
    # Aggregate repository
    "LeaveAggregateRepository",
]
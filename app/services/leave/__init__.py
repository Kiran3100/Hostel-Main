"""
Leave Service Layer

Provides comprehensive business logic for leave management including:
- Leave applications (submit, cancel, update, list, detail)
- Approval workflows (approve, reject, escalate, request changes)
- Balances, quotas, and usage analytics
- Calendar views (hostel/student monthly and period views)
- Leave type and policy configuration
- Notifications (submission, decision, reminders, escalations)

All services follow consistent patterns:
- Comprehensive error handling with logging
- Transaction management (commit/rollback)
- Validation at service layer
- Detailed audit trails
- Standardized ServiceResult responses

Version: 2.0.0
Last Updated: 2024
"""

from app.services.leave.leave_application_service import LeaveApplicationService
from app.services.leave.leave_approval_service import LeaveApprovalService
from app.services.leave.leave_balance_service import LeaveBalanceService
from app.services.leave.leave_calendar_service import LeaveCalendarService
from app.services.leave.leave_notification_service import LeaveNotificationService
from app.services.leave.leave_type_service import LeaveTypeService

__all__ = [
    "LeaveApplicationService",
    "LeaveApprovalService",
    "LeaveBalanceService",
    "LeaveCalendarService",
    "LeaveNotificationService",
    "LeaveTypeService",
]

__version__ = "2.0.0"
__author__ = "Hostel Management System Team"

# Service descriptions for documentation
SERVICE_DESCRIPTIONS = {
    "LeaveApplicationService": (
        "Manages the complete lifecycle of leave applications including "
        "submission, cancellation, updates, retrieval, and analytics."
    ),
    "LeaveApprovalService": (
        "Handles approval workflows with support for multi-level approvals, "
        "rejections, change requests, and escalations."
    ),
    "LeaveBalanceService": (
        "Tracks leave balances, manages quotas, processes adjustments, "
        "and provides usage analytics."
    ),
    "LeaveCalendarService": (
        "Provides calendar-based visualizations of leave data with "
        "monthly and custom period views."
    ),
    "LeaveNotificationService": (
        "Dispatches notifications for leave events via multiple channels "
        "with templating and scheduling support."
    ),
    "LeaveTypeService": (
        "Configures leave types, policies, and restrictions including "
        "blackout dates and approval rules."
    ),
}
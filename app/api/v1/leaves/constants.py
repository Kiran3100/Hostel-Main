"""
API-specific constants and configuration for leave management endpoints.
These are specific to the REST API layer.
"""
from typing import Final, List, Dict, Any

# Import business enums and constants from common location
from app.schemas.common.enums import (
    LeaveStatus,
    LeaveType,
    WorkflowAction,
    UserRole,
    Priority,
    NotificationType,
    LEAVE_TYPE_LIMITS,
    MAX_LEAVE_DURATION_DAYS,
    MIN_LEAVE_DURATION_DAYS,
    ADVANCE_BOOKING_DAYS,
)

# Re-export for convenience in API modules
__all__ = [
    # Business enums (re-exported)
    "LeaveStatus",
    "LeaveType", 
    "WorkflowAction",
    "UserRole",
    "Priority",
    "NotificationType",
    # Business constants (re-exported)
    "LEAVE_TYPE_LIMITS",
    "MAX_LEAVE_DURATION_DAYS",
    "MIN_LEAVE_DURATION_DAYS",
    "ADVANCE_BOOKING_DAYS",
    # API-specific constants
    "DEFAULT_PAGE_SIZE",
    "MAX_PAGE_SIZE",
    "MIN_PAGE_SIZE",
    "CACHE_TTL_BALANCE",
    "CACHE_TTL_CALENDAR",
    "CACHE_TTL_PENDING",
    "DEFAULT_EXPORT_FORMATS",
    "MAX_EXPORT_RECORDS",
    "RATE_LIMIT_APPLICATIONS_PER_DAY",
    "RATE_LIMIT_REQUESTS_PER_MINUTE",
    "API_VERSION",
    "API_TITLE",
    "BULK_OPERATION_LIMITS",
    "ERROR_MESSAGES",
    "API_TAGS",
]

# ============================================================================
# API Configuration Constants
# ============================================================================

# Pagination settings
DEFAULT_PAGE_SIZE: Final[int] = 20
MAX_PAGE_SIZE: Final[int] = 100
MIN_PAGE_SIZE: Final[int] = 1

# Cache Configuration (seconds)
CACHE_TTL_BALANCE: Final[int] = 300      # 5 minutes
CACHE_TTL_CALENDAR: Final[int] = 600     # 10 minutes
CACHE_TTL_PENDING: Final[int] = 60       # 1 minute
CACHE_TTL_STATISTICS: Final[int] = 900   # 15 minutes
CACHE_TTL_APPROVERS: Final[int] = 1800   # 30 minutes

# ============================================================================
# Export and Reporting Configuration
# ============================================================================

DEFAULT_EXPORT_FORMATS: Final[List[str]] = ["csv", "excel", "pdf"]
MAX_EXPORT_RECORDS: Final[int] = 10000
EXPORT_TIMEOUT_SECONDS: Final[int] = 300  # 5 minutes

# Calendar export settings
ICAL_EXPORT_MONTHS_LIMIT: Final[int] = 12
CALENDAR_SYNC_BATCH_SIZE: Final[int] = 50

# ============================================================================
# Rate Limiting Configuration
# ============================================================================

RATE_LIMIT_APPLICATIONS_PER_DAY: Final[int] = 5
RATE_LIMIT_REQUESTS_PER_MINUTE: Final[int] = 60
RATE_LIMIT_BULK_OPERATIONS_PER_HOUR: Final[int] = 3

# API endpoint specific limits
ENDPOINT_RATE_LIMITS: Final[Dict[str, Dict[str, Any]]] = {
    "/leaves": {"requests": 100, "window": "minute"},
    "/leaves/approval": {"requests": 50, "window": "minute"},
    "/leaves/balance": {"requests": 30, "window": "minute"},
    "/leaves/calendar": {"requests": 20, "window": "minute"},
}

# ============================================================================
# Bulk Operations Configuration
# ============================================================================

BULK_OPERATION_LIMITS: Final[Dict[str, int]] = {
    "max_approve_at_once": 50,
    "max_reject_at_once": 50,
    "max_export_records": 10000,
    "max_balance_adjustments": 25,
    "batch_size": 10,
}

# ============================================================================
# API Response Configuration
# ============================================================================

# Default response formats
DEFAULT_DATETIME_FORMAT: Final[str] = "%Y-%m-%dT%H:%M:%S.%fZ"
DEFAULT_DATE_FORMAT: Final[str] = "%Y-%m-%d"

# Error message templates
ERROR_MESSAGES: Final[Dict[str, str]] = {
    "leave_not_found": "Leave application with ID '{leave_id}' not found",
    "permission_denied": "You don't have permission to perform this action",
    "invalid_status_transition": "Cannot change status from {from_status} to {to_status}",
    "insufficient_balance": "Insufficient {leave_type} leave balance",
    "overlapping_leaves": "Leave dates overlap with existing application",
    "invalid_date_range": "Invalid date range: end date must be after start date",
    "past_date_not_allowed": "Cannot apply for leave starting in the past",
    "max_duration_exceeded": "Leave duration exceeds maximum allowed for {leave_type}",
    "document_required": "Supporting document required for {leave_type} leave exceeding {days} days",
    "contact_required": "Contact information required for leave exceeding {days} days",
    "approval_required": "This leave type requires approval",
    "invalid_leave_type": "Invalid leave type: {leave_type}",
    "invalid_workflow_action": "Invalid workflow action: {action}",
}

# ============================================================================
# API Metadata
# ============================================================================

API_VERSION: Final[str] = "1.0.0"
API_TITLE: Final[str] = "Hostel Leave Management API"
API_DESCRIPTION: Final[str] = """
Comprehensive leave management system for hostel administration.

**Features**:
- Student leave application submission
- Multi-level approval workflow  
- Leave balance tracking
- Calendar integration
- Analytics and reporting

**Authentication**: Bearer token required for all endpoints
**Rate Limiting**: Applied per endpoint and user role
"""

# OpenAPI tags for endpoint organization
API_TAGS: Final[List[Dict[str, str]]] = [
    {
        "name": "leaves",
        "description": "Core leave application operations",
    },
    {
        "name": "leaves:approval", 
        "description": "Leave approval workflow and decisions",
    },
    {
        "name": "leaves:balance",
        "description": "Leave balance and quota management",
    },
    {
        "name": "leaves:calendar",
        "description": "Calendar views and scheduling",
    },
]
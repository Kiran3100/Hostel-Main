"""
Constants and enumerations for leave management system.
Centralized configuration for better maintainability.
"""
from enum import Enum
from typing import Final


class LeaveStatus(str, Enum):
    """Leave application status enumeration."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    ESCALATED = "escalated"
    DELEGATED = "delegated"


class LeaveType(str, Enum):
    """Types of leave available."""
    CASUAL = "casual"
    SICK = "sick"
    EMERGENCY = "emergency"
    ACADEMIC = "academic"
    VACATION = "vacation"


class WorkflowAction(str, Enum):
    """Workflow actions for leave processing."""
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    DELEGATE = "delegate"


class UserRole(str, Enum):
    """User role enumeration."""
    STUDENT = "student"
    WARDEN = "warden"
    ADMIN = "admin"
    SUPERVISOR = "supervisor"


# API Configuration Constants
DEFAULT_PAGE_SIZE: Final[int] = 20
MAX_PAGE_SIZE: Final[int] = 100
MIN_PAGE_SIZE: Final[int] = 1

# Leave Configuration
MAX_LEAVE_DURATION_DAYS: Final[int] = 30
MIN_LEAVE_DURATION_DAYS: Final[int] = 1
ADVANCE_BOOKING_DAYS: Final[int] = 90

# Cache Configuration (seconds)
CACHE_TTL_BALANCE: Final[int] = 300  # 5 minutes
CACHE_TTL_CALENDAR: Final[int] = 600  # 10 minutes
CACHE_TTL_PENDING: Final[int] = 60   # 1 minute
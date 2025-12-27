"""
Shared dependencies for leave management endpoints.
Promotes reusability and consistent validation.
"""
from functools import lru_cache
from typing import Optional

from fastapi import Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.api.v1.leaves.constants import (
    DEFAULT_PAGE_SIZE,
    MAX_PAGE_SIZE,
    MIN_PAGE_SIZE,
    UserRole,
)
from app.services.leave.leave_application_service import LeaveApplicationService
from app.services.leave.leave_approval_service import LeaveApprovalService
from app.services.leave.leave_balance_service import LeaveBalanceService
from app.services.leave.leave_calendar_service import LeaveCalendarService


# ============================================================================
# Service Dependencies with Caching
# ============================================================================

def get_leave_application_service(
    db: Session = Depends(deps.get_db),
) -> LeaveApplicationService:
    """
    Dependency for LeaveApplicationService.
    Creates a new instance per request with database session.
    """
    return LeaveApplicationService(db=db)


def get_leave_approval_service(
    db: Session = Depends(deps.get_db),
) -> LeaveApprovalService:
    """
    Dependency for LeaveApprovalService.
    Creates a new instance per request with database session.
    """
    return LeaveApprovalService(db=db)


def get_leave_balance_service(
    db: Session = Depends(deps.get_db),
) -> LeaveBalanceService:
    """
    Dependency for LeaveBalanceService.
    Creates a new instance per request with database session.
    """
    return LeaveBalanceService(db=db)


def get_leave_calendar_service(
    db: Session = Depends(deps.get_db),
) -> LeaveCalendarService:
    """
    Dependency for LeaveCalendarService.
    Creates a new instance per request with database session.
    """
    return LeaveCalendarService(db=db)


# ============================================================================
# Pagination Dependencies
# ============================================================================

class PaginationParams:
    """Enhanced pagination parameters with validation."""
    
    def __init__(
        self,
        page: int = Query(1, ge=1, description="Page number (starting from 1)"),
        page_size: int = Query(
            DEFAULT_PAGE_SIZE,
            ge=MIN_PAGE_SIZE,
            le=MAX_PAGE_SIZE,
            description=f"Items per page (max: {MAX_PAGE_SIZE})",
        ),
    ):
        self.page = page
        self.page_size = page_size
        self.skip = (page - 1) * page_size
        self.limit = page_size

    def to_dict(self) -> dict:
        """Convert to dictionary for service layer."""
        return {
            "page": self.page,
            "page_size": self.page_size,
            "skip": self.skip,
            "limit": self.limit,
        }


def get_pagination_params(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(
        DEFAULT_PAGE_SIZE,
        ge=MIN_PAGE_SIZE,
        le=MAX_PAGE_SIZE,
        description="Items per page",
    ),
) -> PaginationParams:
    """Get validated pagination parameters."""
    return PaginationParams(page=page, page_size=page_size)


# ============================================================================
# Permission & Authorization Dependencies
# ============================================================================

def verify_student_or_admin(current_user=Depends(deps.get_current_user)):
    """Verify user is either a student or has admin privileges."""
    allowed_roles = {UserRole.STUDENT, UserRole.ADMIN, UserRole.WARDEN}
    if current_user.role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions",
        )
    return current_user


def verify_approver_role(current_user=Depends(deps.get_current_user)):
    """Verify user has approval permissions."""
    approver_roles = {UserRole.WARDEN, UserRole.ADMIN, UserRole.SUPERVISOR}
    if current_user.role not in approver_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only wardens, admins, and supervisors can approve leaves",
        )
    return current_user


def get_target_student_id(
    student_id: Optional[str] = Query(None, description="Target student ID"),
    current_user=Depends(deps.get_current_user),
) -> str:
    """
    Get target student ID with permission validation.
    Students can only query their own data unless they're admin.
    """
    # If student_id provided
    if student_id:
        # Only admins can query other students
        if current_user.role == UserRole.STUDENT and student_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Students can only access their own data",
            )
        return student_id
    
    # If no student_id provided, use current user if they're a student
    if current_user.role == UserRole.STUDENT:
        return current_user.id
    
    # Admins must specify student_id
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="student_id is required for non-student users",
    )


# ============================================================================
# Validation Dependencies
# ============================================================================

class CalendarParams:
    """Validated calendar query parameters."""
    
    def __init__(
        self,
        year: int = Query(..., ge=2000, le=2100, description="Year"),
        month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    ):
        self.year = year
        self.month = month


def get_calendar_params(
    year: int = Query(..., ge=2000, le=2100),
    month: int = Query(..., ge=1, le=12),
) -> CalendarParams:
    """Get validated calendar parameters."""
    return CalendarParams(year=year, month=month)


# ============================================================================
# Filter Dependencies
# ============================================================================

class LeaveFilterParams:
    """Filter parameters for leave listing."""
    
    def __init__(
        self,
        student_id: Optional[str] = Query(None, description="Filter by student ID"),
        hostel_id: Optional[str] = Query(None, description="Filter by hostel ID"),
        status: Optional[str] = Query(None, description="Filter by status"),
        leave_type: Optional[str] = Query(None, description="Filter by leave type"),
        from_date: Optional[str] = Query(None, description="Filter from date (YYYY-MM-DD)"),
        to_date: Optional[str] = Query(None, description="Filter to date (YYYY-MM-DD)"),
    ):
        self.student_id = student_id
        self.hostel_id = hostel_id
        self.status = status
        self.leave_type = leave_type
        self.from_date = from_date
        self.to_date = to_date
    
    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
        return {
            k: v for k, v in self.__dict__.items() 
            if v is not None
        }


def get_leave_filter_params(
    student_id: Optional[str] = Query(None),
    hostel_id: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    leave_type: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
) -> LeaveFilterParams:
    """Get validated filter parameters."""
    return LeaveFilterParams(
        student_id=student_id,
        hostel_id=hostel_id,
        status=status,
        leave_type=leave_type,
        from_date=from_date,
        to_date=to_date,
    )
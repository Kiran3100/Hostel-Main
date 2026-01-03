"""
Student Leave Application API Endpoints

Provides endpoints for students to manage their leave applications.
"""
from typing import List, Optional
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, Query, status, Body, Path

from app.core.dependencies import get_current_user
from app.services.leave.leave_application_service import LeaveApplicationService
from app.schemas.leave import (
    LeaveApplicationRequest,
    LeaveCancellationRequest,
    LeaveResponse,
    LeaveDetail,
    LeaveListItem,
    LeaveSummary,
    PaginatedLeaveResponse,
    LeaveBalanceSummary,
)
from app.schemas.common.enums import LeaveStatus, LeaveType
from app.schemas.common.base import User

router = APIRouter(
    prefix="/students/me/leaves",
    tags=["Students - Leaves"],
)


def get_leave_service() -> LeaveApplicationService:
    """
    Dependency injection for LeaveApplicationService.
    
    Returns:
        LeaveApplicationService: Instance of the leave service
        
    Raises:
        NotImplementedError: To be implemented with actual service instantiation
    """
    raise NotImplementedError("LeaveApplicationService dependency not configured")


@router.get(
    "",
    response_model=PaginatedLeaveResponse,
    status_code=status.HTTP_200_OK,
    summary="List my leave applications",
    description="Retrieve all leave applications for the authenticated student with optional filtering.",
    responses={
        200: {"description": "Leave applications retrieved successfully"},
        401: {"description": "Unauthorized - Invalid or missing authentication"},
    },
)
async def list_my_leaves(
    status_filter: Optional[LeaveStatus] = Query(
        None,
        alias="status",
        description="Filter by leave status",
    ),
    leave_type: Optional[LeaveType] = Query(
        None,
        description="Filter by leave type",
    ),
    start_date: Optional[date] = Query(
        None,
        description="Filter leaves starting from this date",
    ),
    end_date: Optional[date] = Query(
        None,
        description="Filter leaves ending before this date",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    leave_service: LeaveApplicationService = Depends(get_leave_service),
    current_user: User = Depends(get_current_user),
) -> PaginatedLeaveResponse:
    """
    List all leave applications for the authenticated student.
    
    Args:
        status_filter: Optional status filter (PENDING, APPROVED, REJECTED, CANCELLED)
        leave_type: Optional leave type filter
        start_date: Filter by start date
        end_date: Filter by end date
        page: Page number for pagination
        page_size: Number of items per page
        leave_service: Injected leave service
        current_user: Authenticated user from dependency
        
    Returns:
        PaginatedLeaveResponse: Paginated list of leave applications
    """
    result = leave_service.list_for_student(
        student_id=current_user.id,
        status=status_filter.value if status_filter else None,
        leave_type=leave_type.value if leave_type else None,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    return result.unwrap()


@router.get(
    "/{leave_id}",
    response_model=LeaveDetail,
    status_code=status.HTTP_200_OK,
    summary="Get leave application details",
    description="Retrieve detailed information about a specific leave application.",
    responses={
        200: {"description": "Leave application details retrieved successfully"},
        401: {"description": "Unauthorized - Invalid or missing authentication"},
        403: {"description": "Forbidden - Leave application does not belong to student"},
        404: {"description": "Leave application not found"},
    },
)
async def get_leave_detail(
    leave_id: UUID = Path(..., description="Unique leave application identifier"),
    leave_service: LeaveApplicationService = Depends(get_leave_service),
    current_user: User = Depends(get_current_user),
) -> LeaveDetail:
    """
    Get detailed information about a specific leave application.
    
    Args:
        leave_id: UUID of the leave application
        leave_service: Injected leave service
        current_user: Authenticated user from dependency
        
    Returns:
        LeaveDetail: Detailed leave application information
    """
    result = leave_service.get_by_id(
        leave_id=str(leave_id),
        student_id=current_user.id,
    )
    return result.unwrap()


@router.post(
    "",
    response_model=LeaveResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply for leave",
    description="Submit a new leave application.",
    responses={
        201: {"description": "Leave application created successfully"},
        400: {"description": "Invalid leave data or overlapping leave exists"},
        401: {"description": "Unauthorized"},
        422: {"description": "Validation error in leave application data"},
    },
)
async def apply_leave(
    payload: LeaveApplicationRequest = Body(
        ...,
        description="Leave application details including dates, type, and reason",
    ),
    leave_service: LeaveApplicationService = Depends(get_leave_service),
    current_user: User = Depends(get_current_user),
) -> LeaveResponse:
    """
    Create a new leave application for the authenticated student.
    
    Validates:
    - Leave dates are valid and in the future
    - No overlapping leave applications exist
    - Leave balance is sufficient (if applicable)
    - Required documents for specific leave types
    
    Args:
        payload: Leave application data
        leave_service: Injected leave service
        current_user: Authenticated user from dependency
        
    Returns:
        LeaveResponse: Created leave application details
    """
    # The student_id is already included in the LeaveApplicationRequest schema
    # but we ensure it matches the authenticated user
    leave_data = payload.model_dump()
    leave_data["student_id"] = current_user.id
    
    result = leave_service.apply(data=leave_data)
    return result.unwrap()


@router.post(
    "/{leave_id}/cancel",
    response_model=LeaveResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel leave application",
    description="Cancel a pending or approved leave application.",
    responses={
        200: {"description": "Leave cancelled successfully"},
        400: {"description": "Cannot cancel - leave already started or completed"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - Leave application does not belong to student"},
        404: {"description": "Leave application not found"},
        422: {"description": "Validation error in cancellation request"},
    },
)
async def cancel_leave(
    leave_id: UUID = Path(..., description="Unique leave application identifier"),
    payload: LeaveCancellationRequest = Body(
        ...,
        description="Cancellation request details",
    ),
    leave_service: LeaveApplicationService = Depends(get_leave_service),
    current_user: User = Depends(get_current_user),
) -> LeaveResponse:
    """
    Cancel a leave application.
    
    Only pending or future approved leaves can be cancelled.
    Students can request immediate return for ongoing leaves.
    
    Args:
        leave_id: UUID of the leave application
        payload: Cancellation request with reason and return details
        leave_service: Injected leave service
        current_user: Authenticated user from dependency
        
    Returns:
        LeaveResponse: Updated leave application
    """
    # Ensure the leave_id and student_id in payload match request context
    cancel_data = payload.model_dump()
    cancel_data["leave_id"] = leave_id
    cancel_data["student_id"] = current_user.id
    
    result = leave_service.cancel(
        leave_id=str(leave_id),
        student_id=current_user.id,
        cancellation_data=cancel_data,
    )
    return result.unwrap()


@router.get(
    "/balance/summary",
    response_model=LeaveBalanceSummary,
    status_code=status.HTTP_200_OK,
    summary="Get leave balance summary",
    description="Retrieve leave balance and quota information for the authenticated student.",
    responses={
        200: {"description": "Leave balance summary retrieved successfully"},
        401: {"description": "Unauthorized - Invalid or missing authentication"},
        404: {"description": "Student or hostel information not found"},
    },
)
async def get_leave_balance(
    leave_service: LeaveApplicationService = Depends(get_leave_service),
    current_user: User = Depends(get_current_user),
) -> LeaveBalanceSummary:
    """
    Get leave balance summary including:
    - Total leave quota by type
    - Used leaves by type  
    - Remaining leaves by type
    - Carry forward information
    - Usage statistics
    
    Args:
        leave_service: Injected leave service
        current_user: Authenticated user from dependency
        
    Returns:
        LeaveBalanceSummary: Comprehensive leave balance information
    """
    result = leave_service.get_leave_balance(student_id=current_user.id)
    return result.unwrap()


@router.get(
    "/summary",
    response_model=LeaveSummary,
    status_code=status.HTTP_200_OK,
    summary="Get leave usage summary",
    description="Retrieve leave usage statistics for the authenticated student.",
    responses={
        200: {"description": "Leave summary retrieved successfully"},
        401: {"description": "Unauthorized - Invalid or missing authentication"},
    },
)
async def get_leave_summary(
    period_start: Optional[date] = Query(
        None,
        description="Summary period start date (defaults to academic year start)",
    ),
    period_end: Optional[date] = Query(
        None, 
        description="Summary period end date (defaults to academic year end)",
    ),
    leave_service: LeaveApplicationService = Depends(get_leave_service),
    current_user: User = Depends(get_current_user),
) -> LeaveSummary:
    """
    Get leave usage summary for specified period.
    
    Args:
        period_start: Optional start date for summary period
        period_end: Optional end date for summary period
        leave_service: Injected leave service
        current_user: Authenticated user from dependency
        
    Returns:
        LeaveSummary: Leave usage statistics and summary
    """
    result = leave_service.get_leave_summary(
        student_id=current_user.id,
        period_start=period_start,
        period_end=period_end,
    )
    return result.unwrap()
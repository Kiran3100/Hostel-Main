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
    LeaveApplicationCreate,
    LeaveApplicationResponse,
    LeaveApplicationListResponse,
    LeaveStatus,
    LeaveType,
)
from app.schemas.base import User

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
    response_model=LeaveApplicationListResponse,
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
) -> LeaveApplicationListResponse:
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
        LeaveApplicationListResponse: Paginated list of leave applications
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
    response_model=LeaveApplicationResponse,
    status_code=status.HTTP_200_OK,
    summary="Get leave application details",
    description="Retrieve detailed information about a specific leave application.",
)
async def get_leave_detail(
    leave_id: UUID = Path(..., description="Unique leave application identifier"),
    leave_service: LeaveApplicationService = Depends(get_leave_service),
    current_user: User = Depends(get_current_user),
) -> LeaveApplicationResponse:
    """
    Get detailed information about a specific leave application.
    
    Args:
        leave_id: UUID of the leave application
        leave_service: Injected leave service
        current_user: Authenticated user from dependency
        
    Returns:
        LeaveApplicationResponse: Detailed leave application information
    """
    result = leave_service.get_by_id(
        leave_id=str(leave_id),
        student_id=current_user.id,
    )
    return result.unwrap()


@router.post(
    "",
    response_model=LeaveApplicationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Apply for leave",
    description="Submit a new leave application.",
    responses={
        201: {"description": "Leave application created successfully"},
        400: {"description": "Invalid leave data or overlapping leave exists"},
        401: {"description": "Unauthorized"},
    },
)
async def apply_leave(
    payload: LeaveApplicationCreate = Body(
        ...,
        description="Leave application details including dates, type, and reason",
    ),
    leave_service: LeaveApplicationService = Depends(get_leave_service),
    current_user: User = Depends(get_current_user),
) -> LeaveApplicationResponse:
    """
    Create a new leave application for the authenticated student.
    
    Validates:
    - Leave dates are valid and in the future
    - No overlapping leave applications exist
    - Leave balance is sufficient (if applicable)
    
    Args:
        payload: Leave application data
        leave_service: Injected leave service
        current_user: Authenticated user from dependency
        
    Returns:
        LeaveApplicationResponse: Created leave application details
    """
    leave_data = payload.dict()
    leave_data["student_id"] = current_user.id
    
    result = leave_service.apply(data=leave_data)
    return result.unwrap()


@router.patch(
    "/{leave_id}/cancel",
    response_model=LeaveApplicationResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel leave application",
    description="Cancel a pending or approved leave application.",
    responses={
        200: {"description": "Leave cancelled successfully"},
        400: {"description": "Cannot cancel - leave already started or completed"},
        404: {"description": "Leave application not found"},
    },
)
async def cancel_leave(
    leave_id: UUID = Path(..., description="Unique leave application identifier"),
    cancellation_reason: Optional[str] = Body(
        None,
        embed=True,
        description="Reason for cancellation",
    ),
    leave_service: LeaveApplicationService = Depends(get_leave_service),
    current_user: User = Depends(get_current_user),
) -> LeaveApplicationResponse:
    """
    Cancel a leave application.
    
    Only pending or future approved leaves can be cancelled.
    
    Args:
        leave_id: UUID of the leave application
        cancellation_reason: Optional reason for cancellation
        leave_service: Injected leave service
        current_user: Authenticated user from dependency
        
    Returns:
        LeaveApplicationResponse: Updated leave application
    """
    result = leave_service.cancel(
        leave_id=str(leave_id),
        student_id=current_user.id,
        reason=cancellation_reason,
    )
    return result.unwrap()


@router.get(
    "/balance/summary",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Get leave balance summary",
    description="Retrieve leave balance and quota information for the authenticated student.",
)
async def get_leave_balance(
    leave_service: LeaveApplicationService = Depends(get_leave_service),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Get leave balance summary including:
    - Total leave quota
    - Used leaves
    - Remaining leaves
    - Leave by type breakdown
    
    Args:
        leave_service: Injected leave service
        current_user: Authenticated user from dependency
        
    Returns:
        dict: Leave balance summary
    """
    result = leave_service.get_leave_balance(student_id=current_user.id)
    return result.unwrap()
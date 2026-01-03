"""
Student Complaints API Endpoints

Provides endpoints for students to manage their complaints and grievances.
"""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status, Body, Path

from app.core.dependencies import get_current_user
from app.services.complaint.complaint_service import ComplaintService
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintResponse,
    ComplaintListResponse,
)
from app.schemas.common.enums import ComplaintStatus
from app.schemas.common.base import User

router = APIRouter(
    prefix="/students/me/complaints",
    tags=["Students - Complaints"],
)


def get_complaint_service() -> ComplaintService:
    """
    Dependency injection for ComplaintService.
    
    Returns:
        ComplaintService: Instance of the complaint service
        
    Raises:
        NotImplementedError: To be implemented with actual service instantiation
    """
    raise NotImplementedError("ComplaintService dependency not configured")


@router.get(
    "",
    response_model=ComplaintListResponse,
    status_code=status.HTTP_200_OK,
    summary="List my complaints",
    description="Retrieve all complaints filed by the authenticated student with optional status filtering.",
    responses={
        200: {"description": "Complaints retrieved successfully"},
        401: {"description": "Unauthorized - Invalid or missing authentication"},
    },
)
async def list_my_complaints(
    status_filter: Optional[ComplaintStatus] = Query(
        None,
        alias="status",
        description="Filter complaints by status",
    ),
    page: int = Query(1, ge=1, description="Page number for pagination"),
    page_size: int = Query(
        20,
        ge=1,
        le=100,
        description="Number of items per page",
    ),
    complaint_service: ComplaintService = Depends(get_complaint_service),
    current_user: User = Depends(get_current_user),
) -> ComplaintListResponse:
    """
    List all complaints for the authenticated student.
    
    Args:
        status_filter: Optional status filter (e.g., PENDING, RESOLVED, CLOSED)
        page: Page number for pagination
        page_size: Number of items per page
        complaint_service: Injected complaint service
        current_user: Authenticated user from dependency
        
    Returns:
        ComplaintListResponse: Paginated list of complaints
    """
    result = complaint_service.list_with_filters(
        student_id=current_user.id,
        status=status_filter.value if status_filter else None,
        page=page,
        page_size=page_size,
    )
    return result.unwrap()


@router.get(
    "/{complaint_id}",
    response_model=ComplaintResponse,
    status_code=status.HTTP_200_OK,
    summary="Get complaint details",
    description="Retrieve detailed information about a specific complaint.",
    responses={
        200: {"description": "Complaint details retrieved successfully"},
        401: {"description": "Unauthorized - Invalid or missing authentication"},
        403: {"description": "Forbidden - Cannot access another student's complaint"},
        404: {"description": "Complaint not found"},
    },
)
async def get_complaint_detail(
    complaint_id: UUID = Path(..., description="Unique complaint identifier"),
    complaint_service: ComplaintService = Depends(get_complaint_service),
    current_user: User = Depends(get_current_user),
) -> ComplaintResponse:
    """
    Get detailed information about a specific complaint.
    
    Args:
        complaint_id: UUID of the complaint
        complaint_service: Injected complaint service
        current_user: Authenticated user from dependency
        
    Returns:
        ComplaintResponse: Detailed complaint information
    """
    result = complaint_service.get_by_id(
        complaint_id=str(complaint_id),
        student_id=current_user.id,
    )
    return result.unwrap()


@router.post(
    "",
    response_model=ComplaintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a complaint",
    description="File a new complaint or grievance.",
    responses={
        201: {"description": "Complaint created successfully"},
        400: {"description": "Invalid complaint data"},
        401: {"description": "Unauthorized"},
        422: {"description": "Validation error"},
    },
)
async def create_complaint(
    payload: ComplaintCreate = Body(
        ...,
        description="Complaint details including title, description, and category",
    ),
    complaint_service: ComplaintService = Depends(get_complaint_service),
    current_user: User = Depends(get_current_user),
) -> ComplaintResponse:
    """
    Create a new complaint for the authenticated student.
    
    Args:
        payload: Complaint creation data
        complaint_service: Injected complaint service
        current_user: Authenticated user from dependency
        
    Returns:
        ComplaintResponse: Created complaint details
    """
    # Ensure complaint is associated with the authenticated user
    complaint_data = payload.model_dump()
    complaint_data["raised_by"] = current_user.id
    
    # If student_id is not set, use current user's ID
    if not complaint_data.get("student_id"):
        complaint_data["student_id"] = current_user.id
    
    result = complaint_service.create(data=complaint_data)
    return result.unwrap()


@router.patch(
    "/{complaint_id}/cancel",
    response_model=ComplaintResponse,
    status_code=status.HTTP_200_OK,
    summary="Cancel a complaint",
    description="Cancel a pending complaint (only if not yet resolved).",
    responses={
        200: {"description": "Complaint cancelled successfully"},
        400: {"description": "Cannot cancel complaint in current status"},
        401: {"description": "Unauthorized"},
        403: {"description": "Forbidden - Cannot cancel another student's complaint"},
        404: {"description": "Complaint not found"},
    },
)
async def cancel_complaint(
    complaint_id: UUID = Path(..., description="Unique complaint identifier"),
    reason: Optional[str] = Body(
        None,
        embed=True,
        description="Optional reason for cancellation",
        max_length=500,
    ),
    complaint_service: ComplaintService = Depends(get_complaint_service),
    current_user: User = Depends(get_current_user),
) -> ComplaintResponse:
    """
    Cancel a complaint that is still pending.
    
    Args:
        complaint_id: UUID of the complaint to cancel
        reason: Optional cancellation reason
        complaint_service: Injected complaint service
        current_user: Authenticated user from dependency
        
    Returns:
        ComplaintResponse: Updated complaint details
    """
    result = complaint_service.cancel(
        complaint_id=str(complaint_id),
        student_id=current_user.id,
        cancellation_reason=reason,
    )
    return result.unwrap()
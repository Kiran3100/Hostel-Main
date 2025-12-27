"""
Complaint Management API Endpoints
Handles CRUD operations, filtering, searching, and status updates for complaints.
"""
from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.complaint import (
    ComplaintCreate,
    ComplaintUpdate,
    ComplaintResponse,
    ComplaintDetail,
    ComplaintListItem,
    ComplaintFilterParams,
    ComplaintSearchRequest,
    ComplaintStatusUpdate,
    ComplaintSummary,
)
from app.services.complaint.complaint_service import ComplaintService

router = APIRouter(prefix="/complaints", tags=["complaints"])


def get_complaint_service(db: Session = Depends(deps.get_db)) -> ComplaintService:
    """
    Dependency injection for ComplaintService.
    
    Args:
        db: Database session from dependency injection
        
    Returns:
        ComplaintService: Initialized service instance
    """
    return ComplaintService(db=db)


@router.post(
    "",
    response_model=ComplaintResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new complaint",
    description="Create a new complaint entry. Available to all authenticated users.",
    response_description="Created complaint with generated ID and metadata",
)
def create_complaint(
    payload: ComplaintCreate,
    current_user=Depends(deps.get_current_user),
    service: ComplaintService = Depends(get_complaint_service),
) -> Any:
    """
    Create a new complaint.
    
    Args:
        payload: Complaint creation data
        current_user: Authenticated user making the request
        service: Complaint service instance
        
    Returns:
        ComplaintResponse: Created complaint details
        
    Raises:
        HTTPException: If validation fails or creation error occurs
    """
    return service.create(payload, creator_id=current_user.id)


@router.get(
    "/{complaint_id}",
    response_model=ComplaintDetail,
    summary="Get complaint details",
    description="Retrieve detailed information about a specific complaint including history and assignments.",
    responses={
        200: {"description": "Complaint details retrieved successfully"},
        404: {"description": "Complaint not found"},
        403: {"description": "Access denied to this complaint"},
    },
)
def get_complaint(
    complaint_id: str,
    current_user=Depends(deps.get_current_user),
    service: ComplaintService = Depends(get_complaint_service),
) -> Any:
    """
    Get detailed complaint information.
    
    Args:
        complaint_id: Unique identifier of the complaint
        current_user: Authenticated user making the request
        service: Complaint service instance
        
    Returns:
        ComplaintDetail: Complete complaint information
        
    Raises:
        HTTPException: 404 if complaint not found, 403 if access denied
    """
    complaint = service.get_detail(complaint_id, user_id=current_user.id)
    if not complaint:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Complaint with ID '{complaint_id}' not found"
        )
    return complaint


@router.patch(
    "/{complaint_id}",
    response_model=ComplaintDetail,
    summary="Update complaint details",
    description="Partially update complaint information. Only complaint creator or supervisor can update.",
    responses={
        200: {"description": "Complaint updated successfully"},
        404: {"description": "Complaint not found"},
        403: {"description": "Not authorized to update this complaint"},
    },
)
def update_complaint(
    complaint_id: str,
    payload: ComplaintUpdate,
    current_user=Depends(deps.get_current_user),
    service: ComplaintService = Depends(get_complaint_service),
) -> Any:
    """
    Update complaint details.
    
    Args:
        complaint_id: Unique identifier of the complaint
        payload: Fields to update (partial update)
        current_user: Authenticated user making the request
        service: Complaint service instance
        
    Returns:
        ComplaintDetail: Updated complaint information
        
    Raises:
        HTTPException: If unauthorized or complaint not found
    """
    return service.update(
        complaint_id=complaint_id,
        payload=payload,
        user_id=current_user.id
    )


@router.post(
    "/{complaint_id}/status",
    response_model=ComplaintDetail,
    summary="Change complaint status",
    description="Update the status of a complaint with optional notes. Status transitions are validated.",
    responses={
        200: {"description": "Status updated successfully"},
        400: {"description": "Invalid status transition"},
        404: {"description": "Complaint not found"},
        403: {"description": "Not authorized to change status"},
    },
)
def change_complaint_status(
    complaint_id: str,
    payload: ComplaintStatusUpdate,
    current_user=Depends(deps.get_current_user),
    service: ComplaintService = Depends(get_complaint_service),
) -> Any:
    """
    Change complaint status.
    
    Args:
        complaint_id: Unique identifier of the complaint
        payload: New status and optional notes
        current_user: Authenticated user making the request
        service: Complaint service instance
        
    Returns:
        ComplaintDetail: Updated complaint with new status
        
    Raises:
        HTTPException: If status transition invalid or unauthorized
    """
    return service.change_status(
        complaint_id=complaint_id,
        payload=payload,
        user_id=current_user.id
    )


@router.get(
    "",
    response_model=List[ComplaintListItem],
    summary="List complaints with filters",
    description="Retrieve a paginated list of complaints with optional filtering by status, category, priority, etc.",
    response_description="List of complaints matching the filter criteria",
)
def list_complaints(
    filters: ComplaintFilterParams = Depends(),
    pagination=Depends(deps.get_pagination_params),
    current_user=Depends(deps.get_current_user),
    service: ComplaintService = Depends(get_complaint_service),
) -> Any:
    """
    List complaints with filtering and pagination.
    
    Args:
        filters: Filter parameters (status, category, priority, date range, etc.)
        pagination: Pagination parameters (skip, limit)
        current_user: Authenticated user making the request
        service: Complaint service instance
        
    Returns:
        List[ComplaintListItem]: Filtered and paginated complaints
    """
    return service.list_with_filters(
        filters=filters,
        pagination=pagination,
        user_id=current_user.id
    )


@router.post(
    "/search",
    response_model=List[ComplaintListItem],
    summary="Search complaints",
    description="Full-text search across complaint titles, descriptions, and metadata.",
    response_description="List of complaints matching search criteria",
)
def search_complaints(
    payload: ComplaintSearchRequest,
    pagination=Depends(deps.get_pagination_params),
    current_user=Depends(deps.get_current_user),
    service: ComplaintService = Depends(get_complaint_service),
) -> Any:
    """
    Search complaints using text and filters.
    
    Args:
        payload: Search request with query text and optional filters
        pagination: Pagination parameters
        current_user: Authenticated user making the request
        service: Complaint service instance
        
    Returns:
        List[ComplaintListItem]: Search results
    """
    return service.search(
        payload=payload,
        pagination=pagination,
        user_id=current_user.id
    )


@router.get(
    "/summary/stats",
    response_model=ComplaintSummary,
    summary="Get complaint statistics",
    description="Retrieve aggregated complaint statistics for a hostel including counts by status, category, priority, and trends.",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        400: {"description": "Invalid hostel ID"},
    },
)
def get_complaint_summary(
    hostel_id: str = Query(..., description="Hostel ID for statistics"),
    current_user=Depends(deps.get_current_user),
    service: ComplaintService = Depends(get_complaint_service),
) -> Any:
    """
    Get complaint summary statistics.
    
    Args:
        hostel_id: ID of the hostel to get statistics for
        current_user: Authenticated user making the request
        service: Complaint service instance
        
    Returns:
        ComplaintSummary: Aggregated statistics and metrics
    """
    return service.get_summary(hostel_id=hostel_id)
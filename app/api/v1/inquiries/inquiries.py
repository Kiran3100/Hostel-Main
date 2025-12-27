"""
Core Inquiry API Endpoints

Provides REST API endpoints for inquiry management including:
- CRUD operations
- Search and filtering
- Status management
- Assignment and conversion
- Analytics and statistics
"""

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger
from app.schemas.inquiry.inquiry_base import InquiryCreate, InquiryUpdate
from app.schemas.inquiry.inquiry_response import (
    InquiryDetail,
    InquiryListItem,
    InquiryResponse,
    InquiryStats,
)
from app.schemas.inquiry.inquiry_filters import (
    InquiryFilterParams,
    InquirySearchRequest,
)
from app.schemas.inquiry.inquiry_status import (
    InquiryStatusUpdate,
    InquiryAssignment,
    BulkInquiryStatusUpdate,
    InquiryConversion,
)
from app.services.inquiry.inquiry_service import InquiryService
from app.services.inquiry.inquiry_assignment_service import InquiryAssignmentService
from app.services.inquiry.inquiry_conversion_service import InquiryConversionService
from app.services.inquiry.inquiry_analytics_service import InquiryAnalyticsService

# Initialize logger
logger = get_logger(__name__)

# Initialize router with prefix and tags
router = APIRouter(
    prefix="/inquiries",
    tags=["inquiries"],
    responses={
        404: {"description": "Inquiry not found"},
        400: {"description": "Invalid request"},
        500: {"description": "Internal server error"},
    },
)


# ============================================================================
# Dependency Injection Functions
# ============================================================================


def get_inquiry_service(db: Session = Depends(deps.get_db)) -> InquiryService:
    """
    Dependency injection for InquiryService.
    
    Args:
        db: Database session
        
    Returns:
        InquiryService instance
    """
    return InquiryService(db=db)


def get_assignment_service(
    db: Session = Depends(deps.get_db)
) -> InquiryAssignmentService:
    """
    Dependency injection for InquiryAssignmentService.
    
    Args:
        db: Database session
        
    Returns:
        InquiryAssignmentService instance
    """
    return InquiryAssignmentService(db=db)


def get_conversion_service(
    db: Session = Depends(deps.get_db)
) -> InquiryConversionService:
    """
    Dependency injection for InquiryConversionService.
    
    Args:
        db: Database session
        
    Returns:
        InquiryConversionService instance
    """
    return InquiryConversionService(db=db)


def get_analytics_service(
    db: Session = Depends(deps.get_db)
) -> InquiryAnalyticsService:
    """
    Dependency injection for InquiryAnalyticsService.
    
    Args:
        db: Database session
        
    Returns:
        InquiryAnalyticsService instance
    """
    return InquiryAnalyticsService(db=db)


# ============================================================================
# Core CRUD Operations
# ============================================================================


@router.post(
    "",
    response_model=InquiryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new inquiry",
    description="""
    Create a new inquiry. This endpoint can be used by both public visitors 
    and authenticated users/admins.
    
    Public inquiries are typically created through web forms, while 
    authenticated users can create inquiries on behalf of visitors.
    """,
    response_description="Successfully created inquiry",
)
async def create_inquiry(
    payload: InquiryCreate,
    service: InquiryService = Depends(get_inquiry_service),
    current_user: Optional[Any] = Depends(deps.get_current_user_optional),
) -> InquiryResponse:
    """
    Create a new inquiry.
    
    Args:
        payload: Inquiry creation data
        service: Inquiry service instance
        current_user: Optional authenticated user (for admin-created inquiries)
        
    Returns:
        Created inquiry details
        
    Raises:
        HTTPException: If creation fails due to validation or database errors
    """
    try:
        logger.info(
            f"Creating new inquiry for contact: {payload.contact_email}",
            extra={"user_id": current_user.id if current_user else None}
        )
        
        inquiry = service.create(payload, created_by=current_user)
        
        logger.info(
            f"Successfully created inquiry {inquiry.id}",
            extra={"inquiry_id": inquiry.id}
        )
        
        return inquiry
        
    except ValueError as e:
        logger.warning(f"Validation error creating inquiry: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating inquiry: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create inquiry"
        )


@router.get(
    "/{inquiry_id}",
    response_model=InquiryDetail,
    summary="Get inquiry details",
    description="Retrieve detailed information about a specific inquiry by ID.",
    response_description="Inquiry details",
    responses={
        200: {"description": "Inquiry found and returned"},
        404: {"description": "Inquiry not found"},
    },
)
async def get_inquiry(
    inquiry_id: str,
    service: InquiryService = Depends(get_inquiry_service),
    current_user: Any = Depends(deps.get_admin_user),
) -> InquiryDetail:
    """
    Retrieve inquiry details.
    
    Args:
        inquiry_id: Unique identifier of the inquiry
        service: Inquiry service instance
        current_user: Authenticated admin user
        
    Returns:
        Detailed inquiry information
        
    Raises:
        HTTPException: If inquiry not found or access denied
    """
    try:
        logger.info(
            f"Fetching inquiry {inquiry_id}",
            extra={"inquiry_id": inquiry_id, "user_id": current_user.id}
        )
        
        inquiry = service.get_detail(inquiry_id)
        
        if not inquiry:
            logger.warning(f"Inquiry {inquiry_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inquiry with ID {inquiry_id} not found"
            )
        
        return inquiry
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching inquiry {inquiry_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve inquiry"
        )


@router.patch(
    "/{inquiry_id}",
    response_model=InquiryDetail,
    summary="Update inquiry",
    description="Update inquiry information. Only specified fields will be updated.",
    response_description="Updated inquiry details",
)
async def update_inquiry(
    inquiry_id: str,
    payload: InquiryUpdate,
    service: InquiryService = Depends(get_inquiry_service),
    current_user: Any = Depends(deps.get_admin_user),
) -> InquiryDetail:
    """
    Update inquiry details.
    
    Args:
        inquiry_id: Unique identifier of the inquiry
        payload: Fields to update
        service: Inquiry service instance
        current_user: Authenticated admin user
        
    Returns:
        Updated inquiry details
        
    Raises:
        HTTPException: If inquiry not found or update fails
    """
    try:
        logger.info(
            f"Updating inquiry {inquiry_id}",
            extra={"inquiry_id": inquiry_id, "user_id": current_user.id}
        )
        
        updated_inquiry = service.update(
            inquiry_id=inquiry_id,
            payload=payload,
            updated_by=current_user
        )
        
        if not updated_inquiry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inquiry with ID {inquiry_id} not found"
            )
        
        logger.info(f"Successfully updated inquiry {inquiry_id}")
        return updated_inquiry
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error updating inquiry {inquiry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating inquiry {inquiry_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update inquiry"
        )


@router.delete(
    "/{inquiry_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete inquiry",
    description="""
    Permanently delete an inquiry. This action is irreversible and requires 
    super admin privileges.
    """,
    response_description="Inquiry successfully deleted",
)
async def delete_inquiry(
    inquiry_id: str,
    service: InquiryService = Depends(get_inquiry_service),
    current_user: Any = Depends(deps.get_super_admin_user),
) -> None:
    """
    Delete an inquiry.
    
    Args:
        inquiry_id: Unique identifier of the inquiry
        service: Inquiry service instance
        current_user: Authenticated super admin user
        
    Raises:
        HTTPException: If inquiry not found or deletion fails
    """
    try:
        logger.warning(
            f"Deleting inquiry {inquiry_id}",
            extra={"inquiry_id": inquiry_id, "user_id": current_user.id}
        )
        
        deleted = service.delete(inquiry_id=inquiry_id, deleted_by=current_user)
        
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inquiry with ID {inquiry_id} not found"
            )
        
        logger.info(f"Successfully deleted inquiry {inquiry_id}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting inquiry {inquiry_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete inquiry"
        )


@router.get(
    "",
    response_model=List[InquiryListItem],
    summary="List inquiries",
    description="""
    Retrieve a filtered and paginated list of inquiries.
    
    Supports filtering by:
    - Status
    - Priority
    - Source
    - Date range
    - Assigned user
    - Hostel
    """,
    response_description="List of inquiries matching criteria",
)
async def list_inquiries(
    filters: InquiryFilterParams = Depends(),
    pagination: dict = Depends(deps.get_pagination_params),
    service: InquiryService = Depends(get_inquiry_service),
    current_user: Any = Depends(deps.get_admin_user),
) -> List[InquiryListItem]:
    """
    List inquiries with filters and pagination.
    
    Args:
        filters: Filter parameters
        pagination: Pagination parameters (skip, limit)
        service: Inquiry service instance
        current_user: Authenticated admin user
        
    Returns:
        List of inquiries matching the criteria
        
    Raises:
        HTTPException: If listing fails
    """
    try:
        logger.info(
            "Listing inquiries",
            extra={
                "user_id": current_user.id,
                "filters": filters.dict(exclude_none=True),
                "pagination": pagination
            }
        )
        
        inquiries = service.list_with_filters(
            filters=filters,
            pagination=pagination,
            user=current_user
        )
        
        logger.info(f"Retrieved {len(inquiries)} inquiries")
        return inquiries
        
    except Exception as e:
        logger.error(f"Error listing inquiries: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve inquiries"
        )


@router.post(
    "/search",
    response_model=List[InquiryListItem],
    summary="Search inquiries",
    description="""
    Advanced search for inquiries using text search and complex filters.
    
    Supports searching across:
    - Contact name and email
    - Message content
    - Notes
    - Custom fields
    """,
    response_description="List of inquiries matching search criteria",
)
async def search_inquiries(
    payload: InquirySearchRequest,
    pagination: dict = Depends(deps.get_pagination_params),
    service: InquiryService = Depends(get_inquiry_service),
    current_user: Any = Depends(deps.get_admin_user),
) -> List[InquiryListItem]:
    """
    Search inquiries with advanced criteria.
    
    Args:
        payload: Search parameters
        pagination: Pagination parameters
        service: Inquiry service instance
        current_user: Authenticated admin user
        
    Returns:
        List of inquiries matching search criteria
        
    Raises:
        HTTPException: If search fails
    """
    try:
        logger.info(
            "Searching inquiries",
            extra={
                "user_id": current_user.id,
                "search_term": payload.search_term if hasattr(payload, 'search_term') else None
            }
        )
        
        results = service.search(
            payload=payload,
            pagination=pagination,
            user=current_user
        )
        
        logger.info(f"Search returned {len(results)} results")
        return results
        
    except Exception as e:
        logger.error(f"Error searching inquiries: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to search inquiries"
        )


# ============================================================================
# Status & Workflow Management
# ============================================================================


@router.post(
    "/{inquiry_id}/status",
    response_model=InquiryDetail,
    summary="Change inquiry status",
    description="""
    Update the status of an inquiry with optional notes.
    
    Valid status transitions depend on current status and workflow rules.
    Status history is automatically tracked.
    """,
    response_description="Updated inquiry with new status",
)
async def change_status(
    inquiry_id: str,
    payload: InquiryStatusUpdate,
    service: InquiryService = Depends(get_inquiry_service),
    current_user: Any = Depends(deps.get_current_user),
) -> InquiryDetail:
    """
    Change inquiry status.
    
    Args:
        inquiry_id: Unique identifier of the inquiry
        payload: New status and optional notes
        service: Inquiry service instance
        current_user: Authenticated user making the change
        
    Returns:
        Updated inquiry details
        
    Raises:
        HTTPException: If status change is invalid or fails
    """
    try:
        logger.info(
            f"Changing status for inquiry {inquiry_id} to {payload.status}",
            extra={
                "inquiry_id": inquiry_id,
                "user_id": current_user.id,
                "new_status": payload.status
            }
        )
        
        updated_inquiry = service.change_status(
            inquiry_id=inquiry_id,
            payload=payload,
            user_id=current_user.id
        )
        
        if not updated_inquiry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inquiry with ID {inquiry_id} not found"
            )
        
        logger.info(f"Successfully changed status for inquiry {inquiry_id}")
        return updated_inquiry
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid status change for inquiry {inquiry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Error changing status for inquiry {inquiry_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to change inquiry status"
        )


@router.post(
    "/bulk-status",
    summary="Bulk change status",
    description="""
    Update the status of multiple inquiries in a single operation.
    
    Useful for batch operations like marking multiple inquiries as reviewed.
    Invalid or failed updates will be reported in the response.
    """,
    response_description="Summary of bulk status update operation",
)
async def bulk_change_status(
    payload: BulkInquiryStatusUpdate,
    service: InquiryService = Depends(get_inquiry_service),
    current_user: Any = Depends(deps.get_current_user),
) -> dict:
    """
    Change status for multiple inquiries.
    
    Args:
        payload: List of inquiry IDs and new status
        service: Inquiry service instance
        current_user: Authenticated user making the changes
        
    Returns:
        Summary of successful and failed updates
        
    Raises:
        HTTPException: If bulk operation fails
    """
    try:
        logger.info(
            f"Bulk status change for {len(payload.inquiry_ids)} inquiries",
            extra={
                "user_id": current_user.id,
                "inquiry_count": len(payload.inquiry_ids),
                "new_status": payload.status
            }
        )
        
        result = service.bulk_change_status(
            payload=payload,
            user_id=current_user.id
        )
        
        logger.info(
            f"Bulk status change completed: "
            f"{result.get('success_count', 0)} succeeded, "
            f"{result.get('failure_count', 0)} failed"
        )
        
        return result
        
    except ValueError as e:
        logger.warning(f"Validation error in bulk status change: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error in bulk status change: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to perform bulk status update"
        )


@router.post(
    "/{inquiry_id}/assign",
    summary="Assign inquiry",
    description="""
    Assign an inquiry to a specific user for follow-up.
    
    The assigned user will be notified and the inquiry will appear 
    in their task list. Assignment history is tracked.
    """,
    response_description="Assignment confirmation",
)
async def assign_inquiry(
    inquiry_id: str,
    payload: InquiryAssignment,
    service: InquiryAssignmentService = Depends(get_assignment_service),
    current_user: Any = Depends(deps.get_current_user),
) -> dict:
    """
    Assign inquiry to a user.
    
    Args:
        inquiry_id: Unique identifier of the inquiry
        payload: Assignment details (assignee, notes, etc.)
        service: Assignment service instance
        current_user: Authenticated user making the assignment
        
    Returns:
        Assignment confirmation details
        
    Raises:
        HTTPException: If assignment fails
    """
    try:
        logger.info(
            f"Assigning inquiry {inquiry_id} to user {payload.assignee_id}",
            extra={
                "inquiry_id": inquiry_id,
                "assignee_id": payload.assignee_id,
                "assigner_id": current_user.id
            }
        )
        
        result = service.assign(
            inquiry_id=inquiry_id,
            payload=payload,
            assigner_id=current_user.id
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inquiry with ID {inquiry_id} not found"
            )
        
        logger.info(f"Successfully assigned inquiry {inquiry_id}")
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Invalid assignment for inquiry {inquiry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Error assigning inquiry {inquiry_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign inquiry"
        )


@router.post(
    "/{inquiry_id}/convert",
    summary="Convert inquiry to booking",
    description="""
    Convert an inquiry to an actual booking.
    
    This creates a booking record and updates the inquiry status to 'converted'.
    The inquiry remains linked to the booking for reference.
    """,
    response_description="Conversion result with booking details",
)
async def convert_inquiry(
    inquiry_id: str,
    payload: InquiryConversion,
    service: InquiryConversionService = Depends(get_conversion_service),
    current_user: Any = Depends(deps.get_current_user),
) -> dict:
    """
    Convert inquiry to booking.
    
    Args:
        inquiry_id: Unique identifier of the inquiry
        payload: Booking details for conversion
        service: Conversion service instance
        current_user: Authenticated user performing the conversion
        
    Returns:
        Conversion result with booking information
        
    Raises:
        HTTPException: If conversion fails
    """
    try:
        logger.info(
            f"Converting inquiry {inquiry_id} to booking",
            extra={"inquiry_id": inquiry_id, "user_id": current_user.id}
        )
        
        result = service.convert(
            inquiry_id=inquiry_id,
            payload=payload,
            converter_id=current_user.id
        )
        
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Inquiry with ID {inquiry_id} not found"
            )
        
        logger.info(
            f"Successfully converted inquiry {inquiry_id} to booking",
            extra={"booking_id": result.get("booking_id")}
        )
        
        return result
        
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning(f"Validation error converting inquiry {inquiry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(
            f"Error converting inquiry {inquiry_id}: {str(e)}",
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to convert inquiry to booking"
        )


# ============================================================================
# Analytics & Reporting
# ============================================================================


@router.get(
    "/stats",
    response_model=InquiryStats,
    summary="Get inquiry statistics",
    description="""
    Retrieve comprehensive statistics for inquiries.
    
    Includes:
    - Total inquiries by status
    - Conversion rates
    - Response time metrics
    - Source distribution
    - Trends over time
    """,
    response_description="Inquiry statistics and metrics",
)
async def get_inquiry_stats(
    hostel_id: str = Query(..., description="Hostel ID for filtering stats"),
    start_date: Optional[str] = Query(None, description="Start date for stats (ISO format)"),
    end_date: Optional[str] = Query(None, description="End date for stats (ISO format)"),
    service: InquiryAnalyticsService = Depends(get_analytics_service),
    current_user: Any = Depends(deps.get_admin_user),
) -> InquiryStats:
    """
    Get inquiry statistics.
    
    Args:
        hostel_id: Hostel identifier for filtering
        start_date: Optional start date for date range
        end_date: Optional end date for date range
        service: Analytics service instance
        current_user: Authenticated admin user
        
    Returns:
        Comprehensive inquiry statistics
        
    Raises:
        HTTPException: If stats retrieval fails
    """
    try:
        logger.info(
            f"Fetching inquiry stats for hostel {hostel_id}",
            extra={
                "hostel_id": hostel_id,
                "user_id": current_user.id,
                "date_range": f"{start_date} to {end_date}" if start_date else None
            }
        )
        
        stats = service.get_overview(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
            user=current_user
        )
        
        logger.info(f"Successfully retrieved stats for hostel {hostel_id}")
        return stats
        
    except ValueError as e:
        logger.warning(f"Invalid parameters for stats: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error fetching inquiry stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve inquiry statistics"
        )
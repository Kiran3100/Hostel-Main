"""
Main Hostel API Endpoints
Core CRUD operations and management for hostels
"""
from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.hostel.hostel_base import (
    HostelCreate,
    HostelUpdate,
)
from app.schemas.hostel.hostel_admin import (
    HostelStatusUpdate,
)
from app.schemas.hostel.hostel_response import (
    HostelDetail,
    HostelResponse,
    HostelListItem,
    HostelStats,
)
from app.schemas.hostel.hostel_filter import HostelFilterParams
from app.schemas.common import PaginatedResponse
from app.services.hostel.hostel_service import HostelService
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/hostels", tags=["hostels"])


def get_hostel_service(db: Session = Depends(deps.get_db)) -> HostelService:
    """
    Dependency to get hostel service instance
    
    Args:
        db: Database session
        
    Returns:
        HostelService instance
    """
    return HostelService(db=db)


@router.post(
    "",
    response_model=HostelResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new hostel",
    description="Create a new hostel in the system. Requires super admin privileges.",
    responses={
        201: {"description": "Hostel created successfully"},
        400: {"description": "Invalid input data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (super admin required)"},
        409: {"description": "Hostel already exists"},
    },
)
def create_hostel(
    payload: HostelCreate,
    super_admin=Depends(deps.get_super_admin_user),
    service: HostelService = Depends(get_hostel_service),
) -> HostelResponse:
    """
    Create a new hostel.
    
    Required fields:
    - name: Hostel name
    - address: Physical address
    - city: City location
    - contact information
    - capacity details
    
    Args:
        payload: Hostel creation data
        super_admin: Current super admin user (from dependency)
        service: Hostel service instance
        
    Returns:
        Created hostel details
        
    Raises:
        HTTPException: If creation fails or validation errors occur
    """
    try:
        logger.info(
            f"Super admin {super_admin.id} creating hostel: {payload.name}"
        )
        
        hostel = service.create_hostel(payload)
        
        logger.info(f"Hostel {hostel.id} created successfully")
        return hostel
        
    except ValueError as e:
        logger.error(f"Validation error creating hostel: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except RuntimeError as e:
        logger.error(f"Hostel already exists: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating hostel: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create hostel"
        )


@router.get(
    "/{hostel_id}",
    response_model=HostelDetail,
    summary="Get hostel details",
    description="Retrieve detailed information about a specific hostel",
    responses={
        200: {"description": "Hostel details retrieved successfully"},
        404: {"description": "Hostel not found"},
    },
)
def get_hostel(
    hostel_id: str = Path(
        ...,
        description="ID or slug of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    include_rooms: bool = Query(
        False,
        description="Include room details in response"
    ),
    include_amenities: bool = Query(
        True,
        description="Include amenity details in response"
    ),
    include_reviews: bool = Query(
        True,
        description="Include reviews in response"
    ),
    service: HostelService = Depends(get_hostel_service),
) -> HostelDetail:
    """
    Get detailed information about a hostel.
    
    Returns comprehensive hostel information including:
    - Basic details (name, address, contact)
    - Amenities (if requested)
    - Room information (if requested)
    - Reviews and ratings (if requested)
    - Availability status
    - Media/images
    
    Args:
        hostel_id: The hostel identifier (ID or slug)
        include_rooms: Whether to include room details
        include_amenities: Whether to include amenity details
        include_reviews: Whether to include reviews
        service: Hostel service instance
        
    Returns:
        Detailed hostel information
        
    Raises:
        HTTPException: If hostel not found
    """
    try:
        hostel = service.get_detail(
            hostel_id=hostel_id,
            include_rooms=include_rooms,
            include_amenities=include_amenities,
            include_reviews=include_reviews
        )
        
        if not hostel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found"
            )
        
        logger.info(f"Retrieved details for hostel {hostel_id}")
        return hostel
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving hostel details: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve hostel details"
        )


@router.patch(
    "/{hostel_id}",
    response_model=HostelDetail,
    summary="Update hostel details",
    description="Update existing hostel information. Requires admin privileges.",
    responses={
        200: {"description": "Hostel updated successfully"},
        400: {"description": "Invalid input data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Hostel not found"},
    },
)
def update_hostel(
    hostel_id: str = Path(
        ...,
        description="ID of the hostel to update",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    payload: HostelUpdate = ...,
    admin=Depends(deps.get_admin_user),
    service: HostelService = Depends(get_hostel_service),
) -> HostelDetail:
    """
    Update hostel information.
    
    All fields are optional - only provided fields will be updated.
    
    Args:
        hostel_id: The hostel identifier
        payload: Updated hostel data
        admin: Current admin user (from dependency)
        service: Hostel service instance
        
    Returns:
        Updated hostel details
        
    Raises:
        HTTPException: If hostel not found or update fails
    """
    try:
        logger.info(f"Admin {admin.id} updating hostel {hostel_id}")
        
        updated_hostel = service.update_hostel(hostel_id, payload)
        
        if not updated_hostel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found"
            )
        
        logger.info(f"Hostel {hostel_id} updated successfully")
        return updated_hostel
        
    except ValueError as e:
        logger.error(f"Validation error updating hostel: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating hostel: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update hostel"
        )


@router.delete(
    "/{hostel_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete hostel",
    description="Soft delete a hostel. Requires super admin privileges.",
    responses={
        204: {"description": "Hostel deleted successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (super admin required)"},
        404: {"description": "Hostel not found"},
        409: {"description": "Hostel has active bookings and cannot be deleted"},
    },
)
def delete_hostel(
    hostel_id: str = Path(
        ...,
        description="ID of the hostel to delete",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    force: bool = Query(
        False,
        description="Force delete even if there are active bookings"
    ),
    super_admin=Depends(deps.get_super_admin_user),
    service: HostelService = Depends(get_hostel_service),
) -> None:
    """
    Soft delete a hostel.
    
    Args:
        hostel_id: The hostel identifier
        force: Whether to force deletion
        super_admin: Current super admin user
        service: Hostel service instance
        
    Raises:
        HTTPException: If hostel not found or deletion fails
    """
    try:
        logger.info(f"Super admin {super_admin.id} deleting hostel {hostel_id}")
        
        success = service.delete_hostel(hostel_id, force=force)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found"
            )
        
        logger.info(f"Hostel {hostel_id} deleted successfully")
        
    except ValueError as e:
        logger.error(f"Cannot delete hostel: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting hostel: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete hostel"
        )


@router.get(
    "",
    response_model=PaginatedResponse[HostelListItem],
    summary="List hostels",
    description="Retrieve a paginated list of hostels with optional filtering",
    responses={
        200: {"description": "Hostels retrieved successfully"},
        400: {"description": "Invalid filter parameters"},
    },
)
def list_hostels(
    filters: HostelFilterParams = Depends(HostelFilterParams),
    pagination=Depends(deps.get_pagination_params),
    sort_by: str = Query(
        "created_at",
        description="Field to sort by",
        pattern="^(created_at|name|city|rating|price)$"
    ),
    sort_order: str = Query(
        "desc",
        description="Sort order",
        pattern="^(asc|desc)$"
    ),
    service: HostelService = Depends(get_hostel_service),
) -> PaginatedResponse[HostelListItem]:
    """
    List hostels with filtering and pagination.
    
    Supports filtering by:
    - City
    - Price range
    - Amenities
    - Gender preference
    - Availability
    - Rating
    
    Args:
        filters: Filter parameters
        pagination: Pagination parameters
        sort_by: Field to sort results by
        sort_order: Ascending or descending order
        service: Hostel service instance
        
    Returns:
        Paginated list of hostels
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.info(
            f"Listing hostels with filters: {filters.model_dump(exclude_unset=True)}"
        )
        
        result = service.list_hostels(
            filters=filters,
            pagination=pagination,
            sort_by=sort_by,
            sort_order=sort_order
        )
        
        logger.info(
            f"Retrieved {len(result.items)} hostels "
            f"(page {pagination.page} of {result.meta.total_pages})"
        )
        return result
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error listing hostels: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve hostels"
        )


@router.get(
    "/{hostel_id}/stats",
    response_model=HostelStats,
    summary="Get hostel statistics",
    description="Retrieve statistical information for a hostel. Requires admin privileges.",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Hostel not found"},
    },
)
def get_hostel_stats(
    hostel_id: str = Path(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    admin=Depends(deps.get_admin_user),
    service: HostelService = Depends(get_hostel_service),
) -> HostelStats:
    """
    Get hostel statistics.
    
    Provides:
    - Total rooms
    - Occupied rooms
    - Occupancy rate
    - Total revenue
    - Active bookings
    - Pending requests
    - Maintenance issues
    
    Args:
        hostel_id: The hostel identifier
        admin: Current admin user
        service: Hostel service instance
        
    Returns:
        Hostel statistics
        
    Raises:
        HTTPException: If hostel not found
    """
    try:
        stats = service.get_stats(hostel_id)
        
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found"
            )
        
        logger.info(f"Retrieved stats for hostel {hostel_id}")
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving stats: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve statistics"
        )


@router.put(
    "/{hostel_id}/status",
    response_model=HostelDetail,
    summary="Update hostel status",
    description="Update the operational status of a hostel. Requires super admin privileges.",
    responses={
        200: {"description": "Status updated successfully"},
        400: {"description": "Invalid status value"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (super admin required)"},
        404: {"description": "Hostel not found"},
    },
)
def set_hostel_status(
    hostel_id: str = Path(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    status_payload: HostelStatusUpdate = ...,
    super_admin=Depends(deps.get_super_admin_user),
    service: HostelService = Depends(get_hostel_service),
) -> HostelDetail:
    """
    Update hostel status.
    
    Valid statuses:
    - ACTIVE: Hostel is operational
    - INACTIVE: Hostel temporarily closed
    - UNDER_MAINTENANCE: Under maintenance
    - CLOSED: Permanently closed
    
    Args:
        hostel_id: The hostel identifier
        status_payload: New status information
        super_admin: Current super admin user
        service: Hostel service instance
        
    Returns:
        Updated hostel details
        
    Raises:
        HTTPException: If hostel not found or status invalid
    """
    try:
        logger.info(
            f"Super admin {super_admin.id} updating status of hostel {hostel_id} "
            f"to {status_payload.status}"
        )
        
        updated_hostel = service.set_status(
            hostel_id=hostel_id,
            status=status_payload.status,
            is_active=status_payload.is_active,
            reason=status_payload.reason,
            effective_date=status_payload.effective_date
        )
        
        if not updated_hostel:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found"
            )
        
        logger.info(f"Hostel {hostel_id} status updated successfully")
        return updated_hostel
        
    except ValueError as e:
        logger.error(f"Invalid status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating status: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update hostel status"
        )


@router.get(
    "/{hostel_id}/availability",
    summary="Check hostel availability",
    description="Check room availability for specific dates",
    responses={
        200: {"description": "Availability data retrieved successfully"},
        404: {"description": "Hostel not found"},
    },
)
def check_availability(
    hostel_id: str = Path(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    start_date: str = Query(
        ...,
        description="Start date (YYYY-MM-DD)"
    ),
    end_date: str = Query(
        ...,
        description="End date (YYYY-MM-DD)"
    ),
    room_type: Optional[str] = Query(
        None,
        description="Filter by room type"
    ),
    service: HostelService = Depends(get_hostel_service),
) -> Any:
    """
    Check availability for specific dates.
    
    Args:
        hostel_id: The hostel identifier
        start_date: Check-in date
        end_date: Check-out date
        room_type: Optional room type filter
        service: Hostel service instance
        
    Returns:
        Availability information
    """
    try:
        availability = service.check_availability(
            hostel_id=hostel_id,
            start_date=start_date,
            end_date=end_date,
            room_type=room_type
        )
        
        return availability
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error checking availability: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to check availability"
        )
"""
Hostel Rooms API Endpoints
Endpoints for managing rooms within a hostel context
"""
from typing import Any, List

from fastapi import APIRouter, Depends, Query, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.room.room_response import RoomListItem
from app.schemas.common import PaginatedResponse
from app.services.room.room_service import RoomService
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/hostels/rooms", tags=["hostels:rooms"])


def get_room_service(db: Session = Depends(deps.get_db)) -> RoomService:
    """
    Dependency to get room service instance
    
    Args:
        db: Database session
        
    Returns:
        RoomService instance
    """
    return RoomService(db=db)


@router.get(
    "",
    response_model=PaginatedResponse[RoomListItem],
    summary="List rooms for a hostel",
    description="Retrieve all rooms for a specific hostel with filtering options",
    responses={
        200: {"description": "Rooms retrieved successfully"},
        400: {"description": "Invalid parameters"},
        404: {"description": "Hostel not found"},
    },
)
def list_rooms_for_hostel(
    hostel_id: str = Query(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    room_type: str | None = Query(
        None,
        description="Filter by room type (single, double, shared)"
    ),
    floor: int | None = Query(
        None,
        description="Filter by floor number",
        ge=0
    ),
    availability_status: str | None = Query(
        None,
        description="Filter by availability status",
        regex="^(available|occupied|maintenance|reserved)$"
    ),
    min_price: float | None = Query(
        None,
        description="Minimum price filter",
        ge=0
    ),
    max_price: float | None = Query(
        None,
        description="Maximum price filter",
        ge=0
    ),
    has_attached_bathroom: bool | None = Query(
        None,
        description="Filter by attached bathroom availability"
    ),
    is_ac: bool | None = Query(
        None,
        description="Filter by AC availability"
    ),
    sort_by: str = Query(
        "room_number",
        description="Sort by field",
        regex="^(room_number|floor|price|capacity|availability)$"
    ),
    sort_order: str = Query(
        "asc",
        description="Sort order",
        regex="^(asc|desc)$"
    ),
    pagination=Depends(deps.get_pagination_params),
    service: RoomService = Depends(get_room_service),
) -> PaginatedResponse[RoomListItem]:
    """
    List all rooms for a specific hostel.
    
    Supports comprehensive filtering:
    - Room type
    - Floor level
    - Availability status
    - Price range
    - Amenities (bathroom, AC)
    
    Args:
        hostel_id: The hostel identifier
        room_type: Optional room type filter
        floor: Optional floor filter
        availability_status: Optional status filter
        min_price: Minimum price per month
        max_price: Maximum price per month
        has_attached_bathroom: Filter by bathroom
        is_ac: Filter by AC
        sort_by: Field to sort by
        sort_order: Sort direction
        pagination: Pagination parameters
        service: Room service instance
        
    Returns:
        Paginated list of rooms
        
    Raises:
        HTTPException: If retrieval fails or hostel not found
    """
    try:
        # Validate price range
        if min_price and max_price and min_price > max_price:
            raise ValueError("min_price must be less than max_price")
        
        logger.info(f"Listing rooms for hostel {hostel_id}")
        
        result = service.list_rooms_for_hostel(
            hostel_id=hostel_id,
            room_type=room_type,
            floor=floor,
            availability_status=availability_status,
            min_price=min_price,
            max_price=max_price,
            has_attached_bathroom=has_attached_bathroom,
            is_ac=is_ac,
            sort_by=sort_by,
            sort_order=sort_order,
            pagination=pagination
        )
        
        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found"
            )
        
        logger.info(
            f"Retrieved {len(result.items)} rooms for hostel {hostel_id} "
            f"(page {pagination.page} of {result.total_pages})"
        )
        return result
        
    except ValueError as e:
        logger.error(f"Validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing rooms: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve rooms"
        )


@router.get(
    "/available",
    response_model=List[RoomListItem],
    summary="Get available rooms",
    description="Get all currently available rooms for a hostel",
    responses={
        200: {"description": "Available rooms retrieved successfully"},
        404: {"description": "Hostel not found"},
    },
)
def get_available_rooms(
    hostel_id: str = Query(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    room_type: str | None = Query(
        None,
        description="Filter by room type"
    ),
    max_price: float | None = Query(
        None,
        description="Maximum price filter",
        ge=0
    ),
    service: RoomService = Depends(get_room_service),
) -> List[RoomListItem]:
    """
    Get all available rooms for immediate booking.
    
    Args:
        hostel_id: The hostel identifier
        room_type: Optional room type filter
        max_price: Optional maximum price
        service: Room service instance
        
    Returns:
        List of available rooms
    """
    try:
        available_rooms = service.get_available_rooms(
            hostel_id=hostel_id,
            room_type=room_type,
            max_price=max_price
        )
        
        if available_rooms is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found"
            )
        
        logger.info(f"Found {len(available_rooms)} available rooms in hostel {hostel_id}")
        return available_rooms
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting available rooms: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve available rooms"
        )


@router.get(
    "/statistics",
    summary="Get room statistics for hostel",
    description="Get statistical overview of rooms in a hostel",
    responses={
        200: {"description": "Statistics retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Hostel not found"},
    },
)
def get_room_statistics(
    hostel_id: str = Query(
        ...,
        description="ID of the hostel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    admin=Depends(deps.get_admin_user),
    service: RoomService = Depends(get_room_service),
) -> Any:
    """
    Get room statistics for a hostel.
    
    Provides:
    - Total rooms
    - Available rooms
    - Occupied rooms
    - Under maintenance
    - Occupancy rate
    - Room type breakdown
    - Floor distribution
    
    Args:
        hostel_id: The hostel identifier
        admin: Current admin user
        service: Room service instance
        
    Returns:
        Room statistics
    """
    try:
        stats = service.get_room_statistics(hostel_id)
        
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hostel not found"
            )
        
        logger.info(f"Retrieved room statistics for hostel {hostel_id}")
        return stats
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving statistics: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve room statistics"
        )
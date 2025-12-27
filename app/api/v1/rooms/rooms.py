"""
Room Management Endpoints

Provides CRUD operations and management functionality for hostel rooms.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Path, Query, status, HTTPException

from app.core.dependencies import AuthenticationDependency
from app.services.room.room_service import RoomService
from app.schemas.room import (
    RoomDetail,
    RoomListItem,
    RoomCreate,
    RoomUpdate,
    RoomOccupancyStats,
)

router = APIRouter(
    prefix="/rooms",
    tags=["Rooms"],
)


# ============================================================================
# Dependency Injection
# ============================================================================

def get_room_service() -> RoomService:
    """
    Dependency provider for RoomService.
    
    Override this in your dependency configuration to provide
    the actual service implementation.
    
    Raises:
        NotImplementedError: Must be overridden in dependency configuration
    """
    raise NotImplementedError(
        "RoomService dependency must be configured. "
        "Override get_room_service in your dependency injection configuration."
    )


def get_current_user(auth: AuthenticationDependency = Depends()) -> Any:
    """
    Extract and validate current authenticated user.
    
    Args:
        auth: Authentication dependency
        
    Returns:
        Current authenticated user object
    """
    return auth.get_current_user()


# ============================================================================
# Room CRUD Endpoints
# ============================================================================

@router.post(
    "",
    response_model=RoomDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new room",
    description="Create a new room in a hostel with specified configuration",
    response_description="Detailed information about the created room",
)
async def create_room(
    payload: RoomCreate,
    room_service: RoomService = Depends(get_room_service),
    current_user: Any = Depends(get_current_user),
) -> RoomDetail:
    """
    Create a new room in a hostel.
    
    This endpoint allows administrators to add new rooms to a hostel
    with specific room type, floor, number, and capacity settings.
    
    Args:
        payload: Room creation data
        room_service: Injected room service
        current_user: Authenticated user
        
    Returns:
        Detailed information about the created room
        
    Raises:
        HTTPException: If room creation fails
    """
    result = room_service.create_room(data=payload)
    return result.unwrap()


@router.get(
    "",
    response_model=List[RoomListItem],
    summary="List rooms with filters",
    description="Retrieve a paginated list of rooms with optional filtering",
    response_description="List of rooms matching the specified criteria",
)
async def list_rooms(
    hostel_id: str = Query(
        ..., 
        description="Filter by hostel ID (required)",
        min_length=1,
    ),
    room_type_id: Optional[str] = Query(
        None, 
        description="Filter by room type ID",
    ),
    status_filter: Optional[str] = Query(
        None, 
        description="Filter by room status (e.g., available, occupied, maintenance)",
        alias="status",
    ),
    floor: Optional[str] = Query(
        None, 
        description="Filter by floor number or identifier",
    ),
    page: int = Query(
        1, 
        ge=1, 
        description="Page number for pagination",
    ),
    page_size: int = Query(
        20, 
        ge=1, 
        le=100, 
        description="Number of items per page (max 100)",
    ),
    room_service: RoomService = Depends(get_room_service),
    current_user: Any = Depends(get_current_user),
) -> List[RoomListItem]:
    """
    Retrieve a filtered and paginated list of rooms.
    
    Supports filtering by hostel, room type, status, and floor.
    Results are paginated for better performance with large datasets.
    
    Args:
        hostel_id: Required hostel identifier
        room_type_id: Optional room type filter
        status_filter: Optional status filter
        floor: Optional floor filter
        page: Page number (1-indexed)
        page_size: Items per page
        room_service: Injected room service
        current_user: Authenticated user
        
    Returns:
        List of room summary items matching the criteria
    """
    filters = {
        "hostel_id": hostel_id,
        "room_type_id": room_type_id,
        "status": status_filter,
        "floor": floor,
        "page": page,
        "page_size": page_size,
    }
    
    # Remove None values for cleaner filter dict
    filters = {k: v for k, v in filters.items() if v is not None}
    
    result = room_service.list_rooms_for_hostel(
        hostel_id=hostel_id,
        filters=filters,
    )
    return result.unwrap()


@router.get(
    "/{room_id}",
    response_model=RoomDetail,
    summary="Get detailed room information",
    description="Retrieve comprehensive details about a specific room",
    response_description="Detailed room information including bed configuration and occupancy",
)
async def get_room(
    room_id: str = Path(
        ..., 
        description="Unique identifier of the room",
        min_length=1,
    ),
    room_service: RoomService = Depends(get_room_service),
    current_user: Any = Depends(get_current_user),
) -> RoomDetail:
    """
    Get detailed information about a specific room.
    
    Returns comprehensive room data including:
    - Basic room information (number, floor, type)
    - Bed configuration and individual bed details
    - Current occupancy status
    - Amenities and features
    
    Args:
        room_id: Unique room identifier
        room_service: Injected room service
        current_user: Authenticated user
        
    Returns:
        Detailed room information
        
    Raises:
        HTTPException: If room not found (404)
    """
    result = room_service.get_room_with_beds(room_id=room_id)
    return result.unwrap()


@router.patch(
    "/{room_id}",
    response_model=RoomDetail,
    summary="Update room information",
    description="Partially update room details",
    response_description="Updated room information",
)
async def update_room(
    room_id: str = Path(
        ..., 
        description="Unique identifier of the room to update",
        min_length=1,
    ),
    payload: RoomUpdate = ...,
    room_service: RoomService = Depends(get_room_service),
    current_user: Any = Depends(get_current_user),
) -> RoomDetail:
    """
    Update room information (partial update).
    
    Allows updating specific room attributes without affecting others.
    Only provided fields will be updated.
    
    Args:
        room_id: Room identifier
        payload: Room update data (partial)
        room_service: Injected room service
        current_user: Authenticated user
        
    Returns:
        Updated room details
        
    Raises:
        HTTPException: If room not found or update fails
    """
    result = room_service.update_room(room_id=room_id, data=payload)
    return result.unwrap()


@router.delete(
    "/{room_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a room",
    description="Remove a room from the system",
    responses={
        204: {"description": "Room successfully deleted"},
        400: {"description": "Cannot delete occupied room without force flag"},
        404: {"description": "Room not found"},
    },
)
async def delete_room(
    room_id: str = Path(
        ..., 
        description="Unique identifier of the room to delete",
        min_length=1,
    ),
    force: bool = Query(
        False, 
        description="Force delete even if occupied (use with caution)",
    ),
    room_service: RoomService = Depends(get_room_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Delete a room from the system.
    
    By default, prevents deletion of occupied rooms to protect data integrity.
    Use the 'force' parameter with extreme caution as it may orphan student assignments.
    
    Args:
        room_id: Room identifier
        force: If True, allow deletion of occupied rooms
        room_service: Injected room service
        current_user: Authenticated user
        
    Raises:
        HTTPException: If room not found or deletion fails
    """
    room_service.delete_room(room_id=room_id, force=force).unwrap()


# ============================================================================
# Room Analytics and Statistics
# ============================================================================

@router.get(
    "/{room_id}/occupancy",
    response_model=RoomOccupancyStats,
    summary="Get room occupancy statistics",
    description="Retrieve current occupancy stats and metrics for a room",
    response_description="Occupancy statistics including current utilization",
)
async def get_room_occupancy(
    room_id: str = Path(
        ..., 
        description="Unique identifier of the room",
        min_length=1,
    ),
    room_service: RoomService = Depends(get_room_service),
    current_user: Any = Depends(get_current_user),
) -> RoomOccupancyStats:
    """
    Get current occupancy statistics for a room.
    
    Provides metrics such as:
    - Total bed capacity
    - Occupied beds count
    - Available beds count
    - Occupancy percentage
    - Current occupants (if applicable)
    
    Args:
        room_id: Room identifier
        room_service: Injected room service
        current_user: Authenticated user
        
    Returns:
        Room occupancy statistics
        
    Raises:
        HTTPException: If room not found
    """
    result = room_service.get_room_occupancy_stats(room_id=room_id)
    return result.unwrap()
"""
Room Type Management Endpoints

Provides CRUD operations for room type definitions and configurations.
"""

from typing import Any, List

from fastapi import APIRouter, Depends, Path, Query, status

from app.core.dependencies import AuthenticationDependency
from app.services.room.room_type_service import RoomTypeService
from app.schemas.room.room_type import (
    RoomTypeDefinition,
    RoomTypeCreate,
    RoomTypeUpdate,
    RoomTypeSummary,
)

router = APIRouter(
    prefix="/rooms/types",
    tags=["Rooms - Types"],
)


# ============================================================================
# Dependency Injection
# ============================================================================

def get_room_type_service() -> RoomTypeService:
    """
    Dependency provider for RoomTypeService.
    
    Raises:
        NotImplementedError: Must be overridden in dependency configuration
    """
    raise NotImplementedError(
        "RoomTypeService dependency must be configured. "
        "Override get_room_type_service in your dependency injection configuration."
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
# Room Type CRUD Endpoints
# ============================================================================

@router.get(
    "",
    response_model=List[RoomTypeDefinition],
    summary="List room types",
    description="Retrieve all room types for a specific hostel",
    response_description="List of room type definitions",
)
async def list_room_types(
    hostel_id: str = Query(
        ..., 
        description="Filter by hostel ID (required)",
        min_length=1,
    ),
    type_service: RoomTypeService = Depends(get_room_type_service),
    current_user: Any = Depends(get_current_user),
) -> List[RoomTypeDefinition]:
    """
    List all room types for a hostel.
    
    Room types define the categories of rooms available (e.g., Single, Double,
    Dormitory) with their associated attributes like capacity and base pricing.
    
    Args:
        hostel_id: Hostel identifier
        type_service: Injected room type service
        current_user: Authenticated user
        
    Returns:
        List of room type definitions
    """
    result = type_service.list_room_types_for_hostel(hostel_id=hostel_id)
    return result.unwrap()


@router.post(
    "",
    response_model=RoomTypeDefinition,
    status_code=status.HTTP_201_CREATED,
    summary="Create room type",
    description="Create a new room type definition for a hostel",
    response_description="Created room type details",
)
async def create_room_type(
    payload: RoomTypeCreate,
    type_service: RoomTypeService = Depends(get_room_type_service),
    current_user: Any = Depends(get_current_user),
) -> RoomTypeDefinition:
    """
    Create a new room type.
    
    Define a new category of rooms with specific attributes:
    - Name (e.g., "Single", "Double", "Suite")
    - Capacity (number of beds)
    - Base pricing
    - Amenities and features
    
    Args:
        payload: Room type creation data
        type_service: Injected room type service
        current_user: Authenticated user
        
    Returns:
        Created room type definition
        
    Raises:
        HTTPException: If creation fails (duplicate name, validation error, etc.)
    """
    result = type_service.create_room_type(data=payload)
    return result.unwrap()


@router.get(
    "/{type_id}",
    response_model=RoomTypeDefinition,
    summary="Get room type details",
    description="Retrieve detailed information about a specific room type",
    response_description="Room type definition",
)
async def get_room_type(
    type_id: str = Path(
        ..., 
        description="Unique identifier of the room type",
        min_length=1,
    ),
    type_service: RoomTypeService = Depends(get_room_type_service),
    current_user: Any = Depends(get_current_user),
) -> RoomTypeDefinition:
    """
    Get detailed information about a room type.
    
    Returns complete room type configuration including:
    - Type name and description
    - Capacity specifications
    - Pricing information
    - Amenities list
    - Associated metadata
    
    Args:
        type_id: Room type identifier
        type_service: Injected room type service
        current_user: Authenticated user
        
    Returns:
        Room type definition
        
    Raises:
        HTTPException: If room type not found (404)
    """
    result = type_service.get_room_type(type_id=type_id)
    return result.unwrap()


@router.patch(
    "/{type_id}",
    response_model=RoomTypeDefinition,
    summary="Update room type",
    description="Partially update room type definition",
    response_description="Updated room type details",
)
async def update_room_type(
    type_id: str = Path(
        ..., 
        description="Unique identifier of the room type to update",
        min_length=1,
    ),
    payload: RoomTypeUpdate = ...,
    type_service: RoomTypeService = Depends(get_room_type_service),
    current_user: Any = Depends(get_current_user),
) -> RoomTypeDefinition:
    """
    Update room type information (partial update).
    
    Allows modifying room type attributes without affecting all fields.
    Only provided fields will be updated.
    
    Note: Changing capacity or pricing may affect existing rooms.
    
    Args:
        type_id: Room type identifier
        payload: Room type update data (partial)
        type_service: Injected room type service
        current_user: Authenticated user
        
    Returns:
        Updated room type definition
        
    Raises:
        HTTPException: If room type not found or update fails
    """
    result = type_service.update_room_type(type_id=type_id, data=payload)
    return result.unwrap()


@router.delete(
    "/{type_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete room type",
    description="Remove a room type from the system",
    responses={
        204: {"description": "Room type successfully deleted"},
        400: {"description": "Cannot delete room type with existing rooms"},
        404: {"description": "Room type not found"},
    },
)
async def delete_room_type(
    type_id: str = Path(
        ..., 
        description="Unique identifier of the room type to delete",
        min_length=1,
    ),
    type_service: RoomTypeService = Depends(get_room_type_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Delete a room type from the system.
    
    Room types can only be deleted if no rooms are currently using them.
    This prevents orphaned room records and maintains data integrity.
    
    Args:
        type_id: Room type identifier
        type_service: Injected room type service
        current_user: Authenticated user
        
    Raises:
        HTTPException: If room type has associated rooms or not found
    """
    type_service.delete_room_type(type_id=type_id).unwrap()


# ============================================================================
# Room Type Analytics
# ============================================================================

@router.get(
    "/hostels/{hostel_id}/summary",
    response_model=List[RoomTypeSummary],
    summary="Get room type summary",
    description="Get aggregated statistics for all room types in a hostel",
    response_description="Summary statistics for each room type",
)
async def get_room_type_summary(
    hostel_id: str = Path(
        ..., 
        description="Hostel identifier",
        min_length=1,
    ),
    type_service: RoomTypeService = Depends(get_room_type_service),
    current_user: Any = Depends(get_current_user),
) -> List[RoomTypeSummary]:
    """
    Get summary statistics for room types in a hostel.
    
    Provides aggregated data for each room type:
    - Total rooms count
    - Total bed capacity
    - Current occupancy
    - Availability percentage
    - Revenue metrics (if applicable)
    
    Useful for dashboard displays and capacity planning.
    
    Args:
        hostel_id: Hostel identifier
        type_service: Injected room type service
        current_user: Authenticated user
        
    Returns:
        List of room type summaries with statistics
    """
    result = type_service.get_room_type_summary(hostel_id=hostel_id)
    return result.unwrap()
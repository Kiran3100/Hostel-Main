"""
Bed Management Endpoints

Provides CRUD operations for individual beds and bed assignment management.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Path, Query, status

from app.core.dependencies import AuthenticationDependency
from app.services.room.bed_service import BedService
from app.services.room.bed_assignment_service import BedAssignmentService
from app.schemas.room import (
    BedDetail,
    BedCreate,
    BedUpdate,
    BedAssignment,
)

router = APIRouter(
    prefix="/rooms/beds",
    tags=["Rooms - Beds"],
)


# ============================================================================
# Dependency Injection
# ============================================================================

def get_bed_service() -> BedService:
    """
    Dependency provider for BedService.
    
    Raises:
        NotImplementedError: Must be overridden in dependency configuration
    """
    raise NotImplementedError(
        "BedService dependency must be configured. "
        "Override get_bed_service in your dependency injection configuration."
    )


def get_assignment_service() -> BedAssignmentService:
    """
    Dependency provider for BedAssignmentService.
    
    Raises:
        NotImplementedError: Must be overridden in dependency configuration
    """
    raise NotImplementedError(
        "BedAssignmentService dependency must be configured. "
        "Override get_assignment_service in your dependency injection configuration."
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
# Bed CRUD Endpoints
# ============================================================================

@router.post(
    "",
    response_model=BedDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Create a single bed",
    description="Create a new bed in a room with specified configuration",
    response_description="Detailed information about the created bed",
)
async def create_bed(
    payload: BedCreate,
    bed_service: BedService = Depends(get_bed_service),
    current_user: Any = Depends(get_current_user),
) -> BedDetail:
    """
    Create a new bed in a room.
    
    Beds are the fundamental unit of occupancy in the hostel system.
    Each bed can be assigned to a single student.
    
    Args:
        payload: Bed creation data (room_id, bed_number, etc.)
        bed_service: Injected bed service
        current_user: Authenticated user
        
    Returns:
        Detailed information about the created bed
        
    Raises:
        HTTPException: If bed creation fails (duplicate bed number, room not found, etc.)
    """
    result = bed_service.create_bed(data=payload)
    return result.unwrap()


@router.post(
    "/batch",
    response_model=List[BedDetail],
    status_code=status.HTTP_201_CREATED,
    summary="Create multiple beds in batch",
    description="Efficiently create multiple beds in a single operation",
    response_description="List of created beds",
)
async def create_beds_batch(
    payload: List[BedCreate],
    bed_service: BedService = Depends(get_bed_service),
    current_user: Any = Depends(get_current_user),
) -> List[BedDetail]:
    """
    Create multiple beds in a single batch operation.
    
    This is more efficient than creating beds individually when
    setting up a new room or hostel. All beds are created in a
    single transaction for data consistency.
    
    Args:
        payload: List of bed creation data
        bed_service: Injected bed service
        current_user: Authenticated user
        
    Returns:
        List of created bed details
        
    Raises:
        HTTPException: If batch creation fails (rollback occurs)
    """
    result = bed_service.create_beds_batch(data_list=payload)
    return result.unwrap()


@router.get(
    "/{bed_id}",
    response_model=BedDetail,
    summary="Get bed details",
    description="Retrieve detailed information about a specific bed",
    response_description="Bed details including assignment status",
)
async def get_bed(
    bed_id: str = Path(
        ..., 
        description="Unique identifier of the bed",
        min_length=1,
    ),
    bed_service: BedService = Depends(get_bed_service),
    current_user: Any = Depends(get_current_user),
) -> BedDetail:
    """
    Get detailed information about a specific bed.
    
    Includes:
    - Bed number and position
    - Room association
    - Current assignment status
    - Assigned student (if any)
    - Bed type and features
    
    Args:
        bed_id: Bed identifier
        bed_service: Injected bed service
        current_user: Authenticated user
        
    Returns:
        Detailed bed information
        
    Raises:
        HTTPException: If bed not found (404)
    """
    result = bed_service.get_bed(bed_id=bed_id)
    return result.unwrap()


@router.patch(
    "/{bed_id}",
    response_model=BedDetail,
    summary="Update bed information",
    description="Partially update bed details",
    response_description="Updated bed information",
)
async def update_bed(
    bed_id: str = Path(
        ..., 
        description="Unique identifier of the bed to update",
        min_length=1,
    ),
    payload: BedUpdate = ...,
    bed_service: BedService = Depends(get_bed_service),
    current_user: Any = Depends(get_current_user),
) -> BedDetail:
    """
    Update bed information (partial update).
    
    Allows updating bed attributes such as bed number, position,
    maintenance status, etc. without affecting other fields.
    
    Args:
        bed_id: Bed identifier
        payload: Bed update data (partial)
        bed_service: Injected bed service
        current_user: Authenticated user
        
    Returns:
        Updated bed details
        
    Raises:
        HTTPException: If bed not found or update fails
    """
    result = bed_service.update_bed(bed_id=bed_id, data=payload)
    return result.unwrap()


@router.delete(
    "/{bed_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a bed",
    description="Remove a bed from the system",
    responses={
        204: {"description": "Bed successfully deleted"},
        400: {"description": "Cannot delete occupied bed"},
        404: {"description": "Bed not found"},
    },
)
async def delete_bed(
    bed_id: str = Path(
        ..., 
        description="Unique identifier of the bed to delete",
        min_length=1,
    ),
    bed_service: BedService = Depends(get_bed_service),
    current_user: Any = Depends(get_current_user),
) -> None:
    """
    Delete a bed from the system.
    
    Prevents deletion of occupied beds to maintain data integrity.
    Bed must be released before deletion.
    
    Args:
        bed_id: Bed identifier
        bed_service: Injected bed service
        current_user: Authenticated user
        
    Raises:
        HTTPException: If bed is occupied or not found
    """
    bed_service.delete_bed(bed_id=bed_id).unwrap()


# ============================================================================
# Bed Assignment Operations
# ============================================================================

@router.post(
    "/{bed_id}/assign",
    response_model=BedAssignment,
    status_code=status.HTTP_201_CREATED,
    summary="Assign bed to a student",
    description="Assign a vacant bed to a specific student",
    response_description="Bed assignment details",
)
async def assign_bed(
    bed_id: str = Path(
        ..., 
        description="Unique identifier of the bed to assign",
        min_length=1,
    ),
    student_id: str = Query(
        ..., 
        description="Unique identifier of the student",
        min_length=1,
    ),
    assignment_service: BedAssignmentService = Depends(get_assignment_service),
    current_user: Any = Depends(get_current_user),
) -> BedAssignment:
    """
    Assign a bed to a student.
    
    Creates a new assignment record linking the student to the bed.
    The bed must be available (not currently assigned).
    
    Args:
        bed_id: Bed identifier
        student_id: Student identifier
        assignment_service: Injected assignment service
        current_user: Authenticated user
        
    Returns:
        Bed assignment details with timestamps
        
    Raises:
        HTTPException: If bed is already occupied or student/bed not found
    """
    result = assignment_service.assign_bed(bed_id=bed_id, student_id=student_id)
    return result.unwrap()


@router.post(
    "/{bed_id}/release",
    status_code=status.HTTP_200_OK,
    summary="Release bed assignment",
    description="Release a bed from its current assignment (vacate)",
    responses={
        200: {"description": "Bed successfully released"},
        400: {"description": "Bed is not currently assigned"},
        404: {"description": "Bed not found"},
    },
)
async def release_bed(
    bed_id: str = Path(
        ..., 
        description="Unique identifier of the bed to release",
        min_length=1,
    ),
    reason: Optional[str] = Query(
        None, 
        description="Reason for releasing the bed (e.g., checkout, transfer)",
        max_length=500,
    ),
    assignment_service: BedAssignmentService = Depends(get_assignment_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Release a bed from its current assignment.
    
    Marks the bed as available by ending the current assignment.
    Optionally records a reason for audit purposes.
    
    Args:
        bed_id: Bed identifier
        reason: Optional reason for release
        assignment_service: Injected assignment service
        current_user: Authenticated user
        
    Returns:
        Success confirmation message
        
    Raises:
        HTTPException: If bed is not currently assigned or not found
    """
    assignment_service.release_bed(bed_id=bed_id, reason=reason).unwrap()
    return {"message": "Bed released successfully", "bed_id": bed_id}


@router.post(
    "/swap",
    status_code=status.HTTP_200_OK,
    summary="Swap bed assignments",
    description="Swap beds between two students atomically",
    responses={
        200: {"description": "Beds successfully swapped"},
        400: {"description": "Invalid bed states for swapping"},
        404: {"description": "One or both beds not found"},
    },
)
async def swap_beds(
    bed_id_1: str = Query(
        ..., 
        description="First bed identifier",
        min_length=1,
    ),
    bed_id_2: str = Query(
        ..., 
        description="Second bed identifier",
        min_length=1,
    ),
    assignment_service: BedAssignmentService = Depends(get_assignment_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Swap bed assignments between two students.
    
    Atomically exchanges the students assigned to two beds.
    Both beds must be currently assigned for the swap to succeed.
    The operation is transactional to ensure data consistency.
    
    Args:
        bed_id_1: First bed identifier
        bed_id_2: Second bed identifier
        assignment_service: Injected assignment service
        current_user: Authenticated user
        
    Returns:
        Success confirmation with bed identifiers
        
    Raises:
        HTTPException: If beds cannot be swapped (not assigned, same bed, etc.)
    """
    assignment_service.swap_beds(bed_id_1=bed_id_1, bed_id_2=bed_id_2).unwrap()
    return {
        "message": "Beds swapped successfully",
        "bed_id_1": bed_id_1,
        "bed_id_2": bed_id_2,
    }
"""
Booking Assignment API

Handles room and bed assignment operations including:
- Assigning rooms/beds to bookings
- Reassigning bookings to different rooms
- Bulk assignment operations
- Assignment history tracking
"""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger
from app.schemas.booking.booking_assignment import (
    AssignmentRequest,
    AssignmentResponse,
    BulkAssignmentRequest,
    ReassignmentRequest,
    RoomAssignment,
)
from app.services.booking.booking_assignment_service import BookingAssignmentService

logger = get_logger(__name__)

router = APIRouter(prefix="/bookings/assignment", tags=["bookings:assignment"])


def get_assignment_service(
    db: Session = Depends(deps.get_db),
) -> BookingAssignmentService:
    """
    Dependency injection for BookingAssignmentService.
    
    Args:
        db: Database session
        
    Returns:
        BookingAssignmentService instance
    """
    return BookingAssignmentService(db=db)


@router.post(
    "/{booking_id}",
    response_model=AssignmentResponse,
    summary="Assign room/bed to booking",
    description="Assign a specific room or bed to an approved booking. Requires admin privileges.",
    responses={
        200: {"description": "Room/bed assigned successfully"},
        400: {"description": "Invalid assignment request"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Booking or room not found"},
        409: {"description": "Room/bed unavailable or booking already assigned"},
    },
)
async def assign_room(
    booking_id: str,
    payload: AssignmentRequest,
    admin=Depends(deps.get_admin_user),
    service: BookingAssignmentService = Depends(get_assignment_service),
) -> AssignmentResponse:
    """
    Assign room or bed to a booking.
    
    Args:
        booking_id: Unique booking identifier
        payload: Assignment request data
        admin: Admin user performing the assignment
        service: Assignment service instance
        
    Returns:
        Assignment response with details
        
    Raises:
        HTTPException: If assignment fails
    """
    try:
        logger.info(
            f"Admin {admin.id} assigning room to booking {booking_id}",
            extra={
                "admin_id": admin.id,
                "booking_id": booking_id,
                "room_id": payload.room_id,
                "bed_id": getattr(payload, "bed_id", None),
            },
        )
        
        response = service.assign(booking_id, payload, assigner_id=admin.id)
        
        logger.info(f"Room assigned successfully to booking {booking_id}")
        return response
    except ValueError as e:
        logger.warning(f"Invalid assignment for booking {booking_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error assigning room to booking {booking_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to assign room/bed",
        )


@router.post(
    "/{booking_id}/reassign",
    response_model=AssignmentResponse,
    summary="Reassign booking to different room/bed",
    description="Move a booking to a different room or bed. Requires admin privileges.",
    responses={
        200: {"description": "Booking reassigned successfully"},
        400: {"description": "Invalid reassignment request"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Booking or room not found"},
        409: {"description": "New room/bed unavailable"},
    },
)
async def reassign_room(
    booking_id: str,
    payload: ReassignmentRequest,
    admin=Depends(deps.get_admin_user),
    service: BookingAssignmentService = Depends(get_assignment_service),
) -> AssignmentResponse:
    """
    Reassign booking to a different room or bed.
    
    Args:
        booking_id: Unique booking identifier
        payload: Reassignment request data with reason
        admin: Admin user performing the reassignment
        service: Assignment service instance
        
    Returns:
        Assignment response with new details
        
    Raises:
        HTTPException: If reassignment fails
    """
    try:
        logger.info(
            f"Admin {admin.id} reassigning booking {booking_id}",
            extra={
                "admin_id": admin.id,
                "booking_id": booking_id,
                "new_room_id": payload.new_room_id,
                "reason": payload.reason,
            },
        )
        
        response = service.reassign(booking_id, payload, assigner_id=admin.id)
        
        logger.info(f"Booking {booking_id} reassigned successfully")
        return response
    except ValueError as e:
        logger.warning(f"Invalid reassignment for booking {booking_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error reassigning booking {booking_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reassign booking",
        )


@router.post(
    "/bulk",
    response_model=List[AssignmentResponse],
    summary="Bulk assign rooms",
    description="Assign rooms/beds to multiple bookings at once. Requires admin privileges.",
    responses={
        200: {"description": "Bulk assignment completed"},
        207: {"description": "Partial success - some assignments failed"},
        400: {"description": "Invalid bulk assignment request"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
    },
)
async def bulk_assign(
    payload: BulkAssignmentRequest,
    admin=Depends(deps.get_admin_user),
    service: BookingAssignmentService = Depends(get_assignment_service),
) -> List[AssignmentResponse]:
    """
    Assign rooms/beds to multiple bookings at once.
    
    Args:
        payload: Bulk assignment request with multiple assignments
        admin: Admin user performing the assignments
        service: Assignment service instance
        
    Returns:
        List of assignment responses
        
    Raises:
        HTTPException: If bulk assignment fails
    """
    try:
        logger.info(
            f"Admin {admin.id} performing bulk assignment",
            extra={
                "admin_id": admin.id,
                "assignment_count": len(payload.assignments),
            },
        )
        
        responses = service.bulk_assign(payload, assigner_id=admin.id)
        
        success_count = sum(1 for r in responses if r.success)
        logger.info(
            f"Bulk assignment completed: {success_count}/{len(responses)} successful"
        )
        
        return responses
    except ValueError as e:
        logger.warning(f"Invalid bulk assignment request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error in bulk assignment: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process bulk assignment",
        )


@router.get(
    "/{booking_id}/history",
    response_model=List[RoomAssignment],
    summary="Get assignment history",
    description="Retrieve the complete assignment history for a booking.",
    responses={
        200: {"description": "Assignment history retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Booking not found"},
    },
)
async def get_assignment_history(
    booking_id: str,
    admin=Depends(deps.get_admin_user),
    service: BookingAssignmentService = Depends(get_assignment_service),
) -> List[RoomAssignment]:
    """
    Get assignment history for a booking.
    
    Args:
        booking_id: Unique booking identifier
        admin: Admin user requesting history
        service: Assignment service instance
        
    Returns:
        List of assignment records in chronological order
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.debug(f"Fetching assignment history for booking {booking_id}")
        history = service.get_assignment_history(booking_id)
        
        logger.debug(f"Retrieved {len(history)} assignment records")
        return history
    except Exception as e:
        logger.error(
            f"Error fetching assignment history for booking {booking_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve assignment history",
        )
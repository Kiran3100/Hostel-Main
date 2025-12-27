"""
Booking Waitlist API

Handles waitlist operations including:
- Joining waitlist when rooms unavailable
- Managing waitlist entries
- Converting waitlist to bookings when space available
- Cancelling waitlist entries
"""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger
from app.schemas.booking.booking_waitlist import (
    WaitlistCancellation,
    WaitlistConversion,
    WaitlistEntry,
    WaitlistRequest,
    WaitlistResponse,
)
from app.services.booking.booking_waitlist_service import BookingWaitlistService

logger = get_logger(__name__)

router = APIRouter(prefix="/bookings/waitlist", tags=["bookings:waitlist"])


def get_waitlist_service(
    db: Session = Depends(deps.get_db),
) -> BookingWaitlistService:
    """
    Dependency injection for BookingWaitlistService.
    
    Args:
        db: Database session
        
    Returns:
        BookingWaitlistService instance
    """
    return BookingWaitlistService(db=db)


@router.post(
    "",
    response_model=WaitlistResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Join waitlist",
    description="Add user to waitlist when desired room/bed is unavailable.",
    responses={
        201: {"description": "Successfully joined waitlist"},
        400: {"description": "Invalid waitlist request"},
        401: {"description": "Not authenticated"},
        409: {"description": "Already on waitlist"},
    },
)
async def join_waitlist(
    payload: WaitlistRequest,
    current_user=Depends(deps.get_current_user),
    service: BookingWaitlistService = Depends(get_waitlist_service),
) -> WaitlistResponse:
    """
    Join waitlist for unavailable room/bed.
    
    Args:
        payload: Waitlist request details
        current_user: User joining waitlist
        service: Waitlist service instance
        
    Returns:
        Waitlist entry confirmation
        
    Raises:
        HTTPException: If joining waitlist fails
    """
    try:
        logger.info(
            f"User {current_user.id} joining waitlist",
            extra={
                "user_id": current_user.id,
                "hostel_id": payload.hostel_id,
                "room_type": payload.room_type,
            },
        )
        
        response = service.join(payload, user_id=current_user.id)
        
        logger.info(
            f"User {current_user.id} joined waitlist: entry {response.entry_id}, "
            f"position {response.position}"
        )
        return response
    except ValueError as e:
        logger.warning(f"Invalid waitlist request from user {current_user.id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error joining waitlist for user {current_user.id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to join waitlist",
        )


@router.post(
    "/{entry_id}/cancel",
    status_code=status.HTTP_200_OK,
    summary="Cancel waitlist entry",
    description="Remove user from waitlist.",
    responses={
        200: {"description": "Waitlist entry cancelled successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized to cancel this entry"},
        404: {"description": "Waitlist entry not found"},
    },
)
async def cancel_waitlist(
    entry_id: str,
    payload: WaitlistCancellation,
    current_user=Depends(deps.get_current_user),
    service: BookingWaitlistService = Depends(get_waitlist_service),
) -> dict[str, str]:
    """
    Cancel a waitlist entry.
    
    Args:
        entry_id: Unique waitlist entry identifier
        payload: Cancellation request with optional reason
        current_user: User cancelling the entry
        service: Waitlist service instance
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If cancellation fails
    """
    try:
        logger.info(
            f"User {current_user.id} cancelling waitlist entry {entry_id}",
            extra={
                "user_id": current_user.id,
                "entry_id": entry_id,
                "reason": payload.reason,
            },
        )
        
        service.cancel(entry_id, payload, actor_id=current_user.id)
        
        logger.info(f"Waitlist entry {entry_id} cancelled successfully")
        return {
            "detail": "Waitlist entry cancelled successfully",
            "entry_id": entry_id,
        }
    except PermissionError as e:
        logger.warning(
            f"User {current_user.id} not authorized to cancel entry {entry_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        logger.warning(f"Invalid cancellation for entry {entry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error cancelling waitlist entry {entry_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel waitlist entry",
        )


@router.post(
    "/{entry_id}/convert",
    response_model=Any,
    summary="Convert waitlist to booking",
    description="Convert a waitlist entry to an actual booking when space becomes available.",
    responses={
        200: {"description": "Waitlist converted to booking successfully"},
        400: {"description": "Invalid conversion request"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized or space not available"},
        404: {"description": "Waitlist entry not found"},
    },
)
async def convert_waitlist(
    entry_id: str,
    payload: WaitlistConversion,
    current_user=Depends(deps.get_current_user),
    service: BookingWaitlistService = Depends(get_waitlist_service),
) -> Any:
    """
    Convert waitlist entry to booking.
    
    Args:
        entry_id: Unique waitlist entry identifier
        payload: Conversion request details
        current_user: User converting the entry
        service: Waitlist service instance
        
    Returns:
        Created booking response
        
    Raises:
        HTTPException: If conversion fails
    """
    try:
        logger.info(
            f"User {current_user.id} converting waitlist entry {entry_id} to booking",
            extra={"user_id": current_user.id, "entry_id": entry_id},
        )
        
        booking = service.convert_to_booking(entry_id, payload, user_id=current_user.id)
        
        logger.info(
            f"Waitlist entry {entry_id} converted to booking {booking.id}"
        )
        return booking
    except PermissionError as e:
        logger.warning(
            f"User {current_user.id} not authorized to convert entry {entry_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except ValueError as e:
        logger.warning(f"Invalid conversion for entry {entry_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error converting waitlist entry {entry_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to convert waitlist entry",
        )


@router.get(
    "",
    response_model=List[WaitlistEntry],
    summary="List my waitlist entries",
    description="Retrieve all waitlist entries for the current user.",
    responses={
        200: {"description": "Waitlist entries retrieved successfully"},
        401: {"description": "Not authenticated"},
    },
)
async def get_my_waitlist(
    status_filter: str = Query(None, description="Filter by entry status"),
    current_user=Depends(deps.get_current_user),
    service: BookingWaitlistService = Depends(get_waitlist_service),
) -> List[WaitlistEntry]:
    """
    Get waitlist entries for current user.
    
    Args:
        status_filter: Optional status filter (active, converted, cancelled)
        current_user: Authenticated user
        service: Waitlist service instance
        
    Returns:
        List of user's waitlist entries
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.debug(
            f"Fetching waitlist entries for user {current_user.id}",
            extra={"user_id": current_user.id, "status_filter": status_filter},
        )
        
        entries = service.get_user_waitlist_entries(
            user_id=current_user.id,
            status=status_filter,
        )
        
        logger.debug(f"Retrieved {len(entries)} waitlist entries for user {current_user.id}")
        return entries
    except Exception as e:
        logger.error(
            f"Error fetching waitlist entries for user {current_user.id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve waitlist entries",
        )


@router.get(
    "/hostel/{hostel_id}",
    response_model=List[WaitlistEntry],
    summary="Get hostel waitlist",
    description="Retrieve all waitlist entries for a hostel. Requires admin privileges.",
    responses={
        200: {"description": "Waitlist retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Hostel not found"},
    },
)
async def get_hostel_waitlist(
    hostel_id: str,
    room_type: str = Query(None, description="Filter by room type"),
    status_filter: str = Query(None, description="Filter by entry status"),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    admin=Depends(deps.get_admin_user),
    service: BookingWaitlistService = Depends(get_waitlist_service),
) -> List[WaitlistEntry]:
    """
    Get waitlist entries for a hostel.
    
    Args:
        hostel_id: Unique hostel identifier
        room_type: Optional room type filter
        status_filter: Optional status filter
        skip: Pagination offset
        limit: Maximum records to return
        admin: Admin user requesting the list
        service: Waitlist service instance
        
    Returns:
        List of waitlist entries ordered by join date
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.debug(
            f"Admin {admin.id} fetching waitlist for hostel {hostel_id}",
            extra={
                "admin_id": admin.id,
                "hostel_id": hostel_id,
                "room_type": room_type,
                "status": status_filter,
            },
        )
        
        entries = service.get_hostel_waitlist(
            hostel_id=hostel_id,
            room_type=room_type,
            status=status_filter,
            skip=skip,
            limit=limit,
        )
        
        logger.debug(f"Retrieved {len(entries)} waitlist entries for hostel {hostel_id}")
        return entries
    except Exception as e:
        logger.error(
            f"Error fetching waitlist for hostel {hostel_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve hostel waitlist",
        )
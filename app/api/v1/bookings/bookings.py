"""
Core Booking Operations API

Handles CRUD operations for bookings including:
- Creating new bookings
- Retrieving booking details
- Updating booking information
- Listing bookings with pagination
"""

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger
from app.schemas.booking.booking_base import BookingCreate, BookingUpdate
from app.schemas.booking.booking_response import (
    BookingDetail,
    BookingListItem,
    BookingResponse,
)
from app.services.booking.booking_service import BookingService

logger = get_logger(__name__)

router = APIRouter(prefix="/bookings", tags=["bookings"])


def get_booking_service(db: Session = Depends(deps.get_db)) -> BookingService:
    """
    Dependency injection for BookingService.
    
    Args:
        db: Database session
        
    Returns:
        BookingService instance
    """
    return BookingService(db=db)


@router.post(
    "",
    response_model=BookingResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new booking",
    description="Create a new booking request. Authentication required.",
    responses={
        201: {"description": "Booking created successfully"},
        400: {"description": "Invalid booking data"},
        401: {"description": "Not authenticated"},
        409: {"description": "Booking conflict (e.g., room unavailable)"},
    },
)
async def create_booking(
    payload: BookingCreate,
    current_user=Depends(deps.get_current_user),
    service: BookingService = Depends(get_booking_service),
) -> BookingResponse:
    """
    Create a new booking.
    
    Args:
        payload: Booking creation data
        current_user: Authenticated user
        service: Booking service instance
        
    Returns:
        Created booking response
        
    Raises:
        HTTPException: If booking creation fails
    """
    try:
        logger.info(
            f"Creating booking for user {current_user.id}",
            extra={"user_id": current_user.id, "payload": payload.dict()},
        )
        booking = service.create_booking(payload, creator_id=current_user.id)
        logger.info(f"Booking created successfully: {booking.id}")
        return booking
    except ValueError as e:
        logger.warning(f"Invalid booking data: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error creating booking: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create booking",
        )


@router.get(
    "/{booking_id}",
    response_model=BookingDetail,
    summary="Get booking details",
    description="Retrieve detailed information about a specific booking",
    responses={
        200: {"description": "Booking details retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized to view this booking"},
        404: {"description": "Booking not found"},
    },
)
async def get_booking(
    booking_id: str,
    current_user=Depends(deps.get_current_user),
    service: BookingService = Depends(get_booking_service),
) -> BookingDetail:
    """
    Get detailed booking information.
    
    Args:
        booking_id: Unique booking identifier
        current_user: Authenticated user
        service: Booking service instance
        
    Returns:
        Detailed booking information
        
    Raises:
        HTTPException: If booking not found or access denied
    """
    try:
        logger.debug(f"Fetching booking {booking_id} for user {current_user.id}")
        booking = service.get_detail(booking_id)
        
        if not booking:
            logger.warning(f"Booking {booking_id} not found")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Booking with ID {booking_id} not found",
            )
        
        # Optional: Add authorization check
        # if not service.user_can_access_booking(current_user.id, booking):
        #     raise HTTPException(
        #         status_code=status.HTTP_403_FORBIDDEN,
        #         detail="Not authorized to access this booking"
        #     )
        
        return booking
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching booking {booking_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve booking details",
        )


@router.put(
    "/{booking_id}",
    response_model=BookingDetail,
    summary="Update booking",
    description="Update booking information. Only certain fields may be editable depending on booking status.",
    responses={
        200: {"description": "Booking updated successfully"},
        400: {"description": "Invalid update data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized to update this booking"},
        404: {"description": "Booking not found"},
        409: {"description": "Update conflict (e.g., status prevents update)"},
    },
)
async def update_booking(
    booking_id: str,
    payload: BookingUpdate,
    current_user=Depends(deps.get_current_user),
    service: BookingService = Depends(get_booking_service),
) -> BookingDetail:
    """
    Update an existing booking.
    
    Args:
        booking_id: Unique booking identifier
        payload: Booking update data
        current_user: Authenticated user
        service: Booking service instance
        
    Returns:
        Updated booking details
        
    Raises:
        HTTPException: If update fails or booking not found
    """
    try:
        logger.info(
            f"Updating booking {booking_id} by user {current_user.id}",
            extra={"booking_id": booking_id, "updates": payload.dict(exclude_unset=True)},
        )
        
        updated_booking = service.update_booking(
            booking_id, payload, updater_id=current_user.id
        )
        
        logger.info(f"Booking {booking_id} updated successfully")
        return updated_booking
    except ValueError as e:
        logger.warning(f"Invalid update for booking {booking_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating booking {booking_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update booking",
        )


@router.get(
    "",
    response_model=List[BookingListItem],
    summary="List bookings",
    description="Retrieve a paginated list of bookings. Admins see all bookings, users see only their own.",
    responses={
        200: {"description": "Bookings retrieved successfully"},
        401: {"description": "Not authenticated"},
    },
)
async def list_bookings(
    hostel_id: Optional[str] = Query(None, description="Filter by hostel ID"),
    status_filter: Optional[str] = Query(None, description="Filter by booking status"),
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(100, ge=1, le=1000, description="Number of records to return"),
    current_user=Depends(deps.get_current_user),
    service: BookingService = Depends(get_booking_service),
) -> List[BookingListItem]:
    """
    List bookings with pagination and optional filtering.
    
    Args:
        hostel_id: Optional hostel filter
        status_filter: Optional status filter
        skip: Pagination offset
        limit: Maximum records to return
        current_user: Authenticated user
        service: Booking service instance
        
    Returns:
        List of booking items
    """
    try:
        logger.debug(
            f"Listing bookings for user {current_user.id}",
            extra={
                "skip": skip,
                "limit": limit,
                "hostel_id": hostel_id,
                "status": status_filter,
            },
        )
        
        pagination = {"skip": skip, "limit": limit}
        filters = {}
        
        if hostel_id:
            filters["hostel_id"] = hostel_id
        if status_filter:
            filters["status"] = status_filter
        
        # Non-admin users should only see their own bookings
        if not getattr(current_user, "is_admin", False):
            filters["user_id"] = current_user.id
        
        bookings = service.list_bookings(pagination=pagination, filters=filters)
        
        logger.debug(f"Retrieved {len(bookings)} bookings")
        return bookings
    except Exception as e:
        logger.error(f"Error listing bookings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve bookings",
        )


@router.delete(
    "/{booking_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete booking",
    description="Soft delete a booking. Only allowed for certain statuses.",
    responses={
        204: {"description": "Booking deleted successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized to delete this booking"},
        404: {"description": "Booking not found"},
        409: {"description": "Booking cannot be deleted in current status"},
    },
)
async def delete_booking(
    booking_id: str,
    current_user=Depends(deps.get_current_user),
    service: BookingService = Depends(get_booking_service),
) -> None:
    """
    Delete (soft delete) a booking.
    
    Args:
        booking_id: Unique booking identifier
        current_user: Authenticated user
        service: Booking service instance
        
    Raises:
        HTTPException: If deletion fails or not allowed
    """
    try:
        logger.info(f"Deleting booking {booking_id} by user {current_user.id}")
        service.delete_booking(booking_id, deleter_id=current_user.id)
        logger.info(f"Booking {booking_id} deleted successfully")
    except ValueError as e:
        logger.warning(f"Cannot delete booking {booking_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting booking {booking_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete booking",
        )
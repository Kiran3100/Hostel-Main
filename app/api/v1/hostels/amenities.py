"""
Hostel Amenities API Endpoints
Handles CRUD operations and booking for hostel amenities
"""
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query, HTTPException, Path
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.hostel.hostel_amenity import (
    HostelAmenity,
    AmenityCreate,
    AmenityUpdate,
    AmenityBookingRequest,
    AmenityBookingResponse,
    AmenityAvailability,
)
from app.schemas.common import (
    PaginationParams,
    PaginatedResponse,
    SuccessResponse,
    MessageResponse,
)
from app.services.hostel.hostel_amenity_service import HostelAmenityService
from app.core.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/hostels/amenities", tags=["hostels:amenities"])


def get_amenity_service(db: Session = Depends(deps.get_db)) -> HostelAmenityService:
    """
    Dependency to get hostel amenity service instance
    
    Args:
        db: Database session
        
    Returns:
        HostelAmenityService instance
    """
    return HostelAmenityService(db=db)


@router.post(
    "",
    response_model=SuccessResponse[HostelAmenity],
    status_code=status.HTTP_201_CREATED,
    summary="Add amenity to hostel",
    description="Create a new amenity for a specific hostel. Requires admin privileges.",
    responses={
        201: {"description": "Amenity created successfully"},
        400: {"description": "Invalid input data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        409: {"description": "Amenity already exists"},
    },
)
def create_amenity(
    payload: AmenityCreate,
    admin=Depends(deps.get_admin_user),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> SuccessResponse[HostelAmenity]:
    """
    Create a new hostel amenity.
    
    Args:
        payload: Amenity creation data
        admin: Current admin user (from dependency)
        service: Amenity service instance
        
    Returns:
        Success response with created amenity details
        
    Raises:
        HTTPException: If creation fails or validation errors occur
    """
    try:
        logger.info(
            f"Admin {admin.id} creating amenity '{payload.name}' for hostel {payload.hostel_id}"
        )
        amenity = service.create_amenity(payload)
        logger.info(f"Amenity {amenity.id} created successfully")
        return SuccessResponse.create(
            message="Amenity created successfully",
            data=amenity
        )
    except ValueError as e:
        logger.error(f"Validation error creating amenity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating amenity: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create amenity"
        )


@router.get(
    "",
    response_model=PaginatedResponse[HostelAmenity],
    summary="List amenities",
    description="Retrieve all amenities for a specific hostel with pagination",
    responses={
        200: {"description": "List of amenities retrieved successfully"},
        400: {"description": "Invalid hostel ID"},
        404: {"description": "Hostel not found"},
    },
)
def list_amenities(
    hostel_id: str = Query(
        ...,
        description="ID of the hostel to retrieve amenities for",
        min_length=1,
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    include_unavailable: bool = Query(
        False,
        description="Include unavailable amenities in the response"
    ),
    amenity_type: str | None = Query(
        None,
        description="Filter by amenity type"
    ),
    is_bookable: bool | None = Query(
        None,
        description="Filter by bookable status"
    ),
    pagination: PaginationParams = Depends(),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> PaginatedResponse[HostelAmenity]:
    """
    List all amenities for a specific hostel with filtering and pagination.
    
    Args:
        hostel_id: The hostel identifier
        include_unavailable: Whether to include unavailable amenities
        amenity_type: Filter by amenity type
        is_bookable: Filter by bookable status
        pagination: Pagination parameters
        service: Amenity service instance
        
    Returns:
        Paginated list of hostel amenities
        
    Raises:
        HTTPException: If hostel not found or retrieval fails
    """
    try:
        amenities, total_count = service.list_amenities(
            hostel_id=hostel_id,
            include_unavailable=include_unavailable,
            amenity_type=amenity_type,
            is_bookable=is_bookable,
            limit=pagination.limit,
            offset=pagination.offset
        )
        
        logger.info(f"Retrieved {len(amenities)} amenities for hostel {hostel_id}")
        
        return PaginatedResponse.create(
            items=amenities,
            total_items=total_count,
            page=pagination.page,
            page_size=pagination.page_size
        )
    except ValueError as e:
        logger.error(f"Invalid hostel ID: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error listing amenities: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve amenities"
        )


@router.get(
    "/{amenity_id}",
    response_model=SuccessResponse[HostelAmenity],
    summary="Get amenity details",
    description="Retrieve detailed information about a specific amenity",
    responses={
        200: {"description": "Amenity details retrieved successfully"},
        404: {"description": "Amenity not found"},
    },
)
def get_amenity(
    amenity_id: str = Path(
        ...,
        description="ID of the amenity to retrieve",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> SuccessResponse[HostelAmenity]:
    """
    Get detailed information about a specific amenity.
    
    Args:
        amenity_id: The amenity identifier
        service: Amenity service instance
        
    Returns:
        Success response with amenity details
        
    Raises:
        HTTPException: If amenity not found
    """
    amenity = service.get_amenity(amenity_id)
    if not amenity:
        logger.warning(f"Amenity {amenity_id} not found")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Amenity not found"
        )
    
    return SuccessResponse.create(
        message="Amenity retrieved successfully",
        data=amenity
    )


@router.get(
    "/{amenity_id}/availability",
    response_model=SuccessResponse[AmenityAvailability],
    summary="Get amenity availability",
    description="Check availability of an amenity for a specific date",
    responses={
        200: {"description": "Availability retrieved successfully"},
        404: {"description": "Amenity not found"},
    },
)
def get_amenity_availability(
    amenity_id: str = Path(
        ...,
        description="ID of the amenity",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    date: str = Query(
        ...,
        description="Date to check availability (YYYY-MM-DD)",
        example="2024-12-25"
    ),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> SuccessResponse[AmenityAvailability]:
    """
    Get availability information for an amenity on a specific date.
    
    Args:
        amenity_id: The amenity identifier
        date: Date to check availability
        service: Amenity service instance
        
    Returns:
        Success response with availability information
    """
    try:
        availability = service.get_amenity_availability(amenity_id, date)
        return SuccessResponse.create(
            message="Availability retrieved successfully",
            data=availability
        )
    except ValueError as e:
        logger.error(f"Invalid date format: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error getting availability: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve availability"
        )


@router.patch(
    "/{amenity_id}",
    response_model=SuccessResponse[HostelAmenity],
    summary="Update amenity",
    description="Update amenity details. Requires admin privileges.",
    responses={
        200: {"description": "Amenity updated successfully"},
        400: {"description": "Invalid input data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Amenity not found"},
    },
)
def update_amenity(
    amenity_id: str = Path(
        ...,
        description="ID of the amenity to update",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    payload: AmenityUpdate = ...,
    admin=Depends(deps.get_admin_user),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> SuccessResponse[HostelAmenity]:
    """
    Update an existing amenity.
    
    Args:
        amenity_id: The amenity identifier
        payload: Updated amenity data
        admin: Current admin user (from dependency)
        service: Amenity service instance
        
    Returns:
        Success response with updated amenity details
        
    Raises:
        HTTPException: If amenity not found or update fails
    """
    try:
        logger.info(f"Admin {admin.id} updating amenity {amenity_id}")
        updated_amenity = service.update_amenity(amenity_id, payload)
        if not updated_amenity:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Amenity not found"
            )
        logger.info(f"Amenity {amenity_id} updated successfully")
        return SuccessResponse.create(
            message="Amenity updated successfully",
            data=updated_amenity
        )
    except ValueError as e:
        logger.error(f"Validation error updating amenity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error updating amenity: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update amenity"
        )


@router.delete(
    "/{amenity_id}",
    response_model=MessageResponse,
    summary="Delete amenity",
    description="Permanently delete an amenity. Requires admin privileges.",
    responses={
        200: {"description": "Amenity deleted successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized (admin required)"},
        404: {"description": "Amenity not found"},
        409: {"description": "Amenity has active bookings and cannot be deleted"},
    },
)
def delete_amenity(
    amenity_id: str = Path(
        ...,
        description="ID of the amenity to delete",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    force: bool = Query(
        False,
        description="Force delete even if there are dependencies"
    ),
    admin=Depends(deps.get_admin_user),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> MessageResponse:
    """
    Delete an amenity.
    
    Args:
        amenity_id: The amenity identifier
        force: Whether to force deletion
        admin: Current admin user (from dependency)
        service: Amenity service instance
        
    Returns:
        Message response confirming deletion
        
    Raises:
        HTTPException: If amenity not found or deletion fails
    """
    try:
        logger.info(f"Admin {admin.id} deleting amenity {amenity_id}")
        success = service.delete_amenity(amenity_id, force=force)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Amenity not found"
            )
        logger.info(f"Amenity {amenity_id} deleted successfully")
        return MessageResponse.create("Amenity deleted successfully")
    except ValueError as e:
        logger.error(f"Cannot delete amenity: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error deleting amenity: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete amenity"
        )


@router.post(
    "/{amenity_id}/book",
    response_model=SuccessResponse[AmenityBookingResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Book an amenity",
    description="Create a booking for a specific amenity",
    responses={
        201: {"description": "Booking created successfully"},
        400: {"description": "Invalid booking data or amenity not available"},
        401: {"description": "Not authenticated"},
        404: {"description": "Amenity not found"},
        409: {"description": "Amenity already booked for the requested time"},
    },
)
def book_amenity(
    amenity_id: str = Path(
        ...,
        description="ID of the amenity to book",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    payload: AmenityBookingRequest = ...,
    current_user=Depends(deps.get_current_user),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> SuccessResponse[AmenityBookingResponse]:
    """
    Book an amenity for a specific time slot.
    
    Args:
        amenity_id: The amenity identifier
        payload: Booking request data
        current_user: Current authenticated user
        service: Amenity service instance
        
    Returns:
        Success response with booking confirmation details
        
    Raises:
        HTTPException: If booking fails or amenity not available
    """
    try:
        logger.info(f"User {current_user.id} booking amenity {amenity_id}")
        booking = service.book_amenity(
            amenity_id=amenity_id,
            payload=payload,
            user_id=current_user.id
        )
        logger.info(f"Booking {booking.id} created successfully")
        return SuccessResponse.create(
            message="Amenity booked successfully",
            data=booking
        )
    except ValueError as e:
        logger.error(f"Validation error creating booking: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except LookupError as e:
        logger.error(f"Amenity not found: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except RuntimeError as e:
        logger.error(f"Booking conflict: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error creating booking: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create booking"
        )


@router.get(
    "/{amenity_id}/bookings",
    response_model=PaginatedResponse[AmenityBookingResponse],
    summary="List amenity bookings",
    description="Get all bookings for a specific amenity with pagination",
    responses={
        200: {"description": "Bookings retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized"},
        404: {"description": "Amenity not found"},
    },
)
def list_amenity_bookings(
    amenity_id: str = Path(
        ...,
        description="ID of the amenity",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    start_date: str | None = Query(None, description="Filter bookings from this date (YYYY-MM-DD)"),
    end_date: str | None = Query(None, description="Filter bookings until this date (YYYY-MM-DD)"),
    status: str | None = Query(None, description="Filter by booking status"),
    pagination: PaginationParams = Depends(),
    admin=Depends(deps.get_admin_user),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> PaginatedResponse[AmenityBookingResponse]:
    """
    List all bookings for a specific amenity with filtering and pagination.
    
    Args:
        amenity_id: The amenity identifier
        start_date: Optional start date filter
        end_date: Optional end date filter
        status: Optional status filter
        pagination: Pagination parameters
        admin: Current admin user
        service: Amenity service instance
        
    Returns:
        Paginated list of bookings
    """
    try:
        bookings, total_count = service.list_bookings(
            amenity_id=amenity_id,
            start_date=start_date,
            end_date=end_date,
            status=status,
            limit=pagination.limit,
            offset=pagination.offset
        )
        
        return PaginatedResponse.create(
            items=bookings,
            total_items=total_count,
            page=pagination.page,
            page_size=pagination.page_size
        )
    except Exception as e:
        logger.error(f"Error listing bookings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve bookings"
        )


@router.get(
    "/bookings/my",
    response_model=PaginatedResponse[AmenityBookingResponse],
    summary="Get my bookings",
    description="Get all amenity bookings for the current user",
    responses={
        200: {"description": "User bookings retrieved successfully"},
        401: {"description": "Not authenticated"},
    },
)
def get_my_bookings(
    status: str | None = Query(None, description="Filter by booking status"),
    pagination: PaginationParams = Depends(),
    current_user=Depends(deps.get_current_user),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> PaginatedResponse[AmenityBookingResponse]:
    """
    Get all amenity bookings for the current user.
    
    Args:
        status: Optional status filter
        pagination: Pagination parameters
        current_user: Current authenticated user
        service: Amenity service instance
        
    Returns:
        Paginated list of user's bookings
    """
    try:
        bookings, total_count = service.get_user_bookings(
            user_id=current_user.id,
            status=status,
            limit=pagination.limit,
            offset=pagination.offset
        )
        
        return PaginatedResponse.create(
            items=bookings,
            total_items=total_count,
            page=pagination.page,
            page_size=pagination.page_size
        )
    except Exception as e:
        logger.error(f"Error getting user bookings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve bookings"
        )


@router.patch(
    "/bookings/{booking_id}/cancel",
    response_model=MessageResponse,
    summary="Cancel booking",
    description="Cancel an amenity booking",
    responses={
        200: {"description": "Booking cancelled successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized to cancel this booking"},
        404: {"description": "Booking not found"},
        409: {"description": "Booking cannot be cancelled"},
    },
)
def cancel_booking(
    booking_id: str = Path(
        ...,
        description="ID of the booking to cancel",
        example="550e8400-e29b-41d4-a716-446655440000"
    ),
    reason: str | None = Query(None, description="Reason for cancellation"),
    current_user=Depends(deps.get_current_user),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> MessageResponse:
    """
    Cancel an amenity booking.
    
    Args:
        booking_id: The booking identifier
        reason: Optional cancellation reason
        current_user: Current authenticated user
        service: Amenity service instance
        
    Returns:
        Message response confirming cancellation
    """
    try:
        success = service.cancel_booking(
            booking_id=booking_id,
            user_id=current_user.id,
            reason=reason
        )
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Booking not found or cannot be cancelled"
            )
        
        return MessageResponse.create("Booking cancelled successfully")
    except ValueError as e:
        logger.error(f"Cannot cancel booking: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Error cancelling booking: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel booking"
        )
"""
Hostel Amenities API Endpoints
Handles CRUD operations and booking for hostel amenities
"""
from typing import Any, List
from uuid import UUID

from fastapi import APIRouter, Depends, status, Query, HTTPException, Path
from sqlalchemy.orm import Session

from app.api import deps
from app.schemas.hostel.hostel_base import (
    HostelAmenity,
    AmenityCreate,
    AmenityUpdate,
    AmenityBookingRequest,
    AmenityBookingResponse,
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
    response_model=HostelAmenity,
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
) -> HostelAmenity:
    """
    Create a new hostel amenity.
    
    Args:
        payload: Amenity creation data
        admin: Current admin user (from dependency)
        service: Amenity service instance
        
    Returns:
        Created amenity details
        
    Raises:
        HTTPException: If creation fails or validation errors occur
    """
    try:
        logger.info(
            f"Admin {admin.id} creating amenity for hostel {payload.hostel_id}"
        )
        amenity = service.create_amenity(payload)
        logger.info(f"Amenity {amenity.id} created successfully")
        return amenity
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
    response_model=List[HostelAmenity],
    summary="List amenities",
    description="Retrieve all amenities for a specific hostel",
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
    service: HostelAmenityService = Depends(get_amenity_service),
) -> List[HostelAmenity]:
    """
    List all amenities for a specific hostel.
    
    Args:
        hostel_id: The hostel identifier
        include_unavailable: Whether to include unavailable amenities
        service: Amenity service instance
        
    Returns:
        List of hostel amenities
        
    Raises:
        HTTPException: If hostel not found or retrieval fails
    """
    try:
        amenities = service.list_amenities(
            hostel_id=hostel_id,
            include_unavailable=include_unavailable
        )
        logger.info(f"Retrieved {len(amenities)} amenities for hostel {hostel_id}")
        return amenities
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
    response_model=HostelAmenity,
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
) -> HostelAmenity:
    """
    Get detailed information about a specific amenity.
    
    Args:
        amenity_id: The amenity identifier
        service: Amenity service instance
        
    Returns:
        Amenity details
        
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
    return amenity


@router.patch(
    "/{amenity_id}",
    response_model=HostelAmenity,
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
) -> HostelAmenity:
    """
    Update an existing amenity.
    
    Args:
        amenity_id: The amenity identifier
        payload: Updated amenity data
        admin: Current admin user (from dependency)
        service: Amenity service instance
        
    Returns:
        Updated amenity details
        
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
        return updated_amenity
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
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete amenity",
    description="Permanently delete an amenity. Requires admin privileges.",
    responses={
        204: {"description": "Amenity deleted successfully"},
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
) -> None:
    """
    Delete an amenity.
    
    Args:
        amenity_id: The amenity identifier
        force: Whether to force deletion
        admin: Current admin user (from dependency)
        service: Amenity service instance
        
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
    response_model=AmenityBookingResponse,
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
) -> AmenityBookingResponse:
    """
    Book an amenity for a specific time slot.
    
    Args:
        amenity_id: The amenity identifier
        payload: Booking request data
        current_user: Current authenticated user
        service: Amenity service instance
        
    Returns:
        Booking confirmation details
        
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
        return booking
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
    response_model=List[AmenityBookingResponse],
    summary="List amenity bookings",
    description="Get all bookings for a specific amenity",
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
    start_date: str | None = Query(None, description="Filter bookings from this date"),
    end_date: str | None = Query(None, description="Filter bookings until this date"),
    admin=Depends(deps.get_admin_user),
    service: HostelAmenityService = Depends(get_amenity_service),
) -> List[AmenityBookingResponse]:
    """
    List all bookings for a specific amenity.
    
    Args:
        amenity_id: The amenity identifier
        start_date: Optional start date filter
        end_date: Optional end date filter
        admin: Current admin user
        service: Amenity service instance
        
    Returns:
        List of bookings
    """
    try:
        bookings = service.list_bookings(
            amenity_id=amenity_id,
            start_date=start_date,
            end_date=end_date
        )
        return bookings
    except Exception as e:
        logger.error(f"Error listing bookings: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve bookings"
        )
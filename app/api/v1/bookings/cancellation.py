"""
Booking Cancellation API

Handles booking cancellation operations including:
- Individual booking cancellations
- Bulk cancellations
- Refund calculations and previews
- Cancellation policy management
"""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger
from app.schemas.booking.booking_cancellation import (
    BulkCancellation,
    CancellationPolicy,
    CancellationRequest,
    CancellationResponse,
    RefundCalculation,
)
from app.services.booking.booking_cancellation_service import (
    BookingCancellationService,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/bookings/cancellation", tags=["bookings:cancellation"])


def get_cancellation_service(
    db: Session = Depends(deps.get_db),
) -> BookingCancellationService:
    """
    Dependency injection for BookingCancellationService.
    
    Args:
        db: Database session
        
    Returns:
        BookingCancellationService instance
    """
    return BookingCancellationService(db=db)


@router.post(
    "/{booking_id}",
    response_model=CancellationResponse,
    summary="Cancel booking",
    description="Cancel a booking with optional reason. May include refund calculation.",
    responses={
        200: {"description": "Booking cancelled successfully"},
        400: {"description": "Invalid cancellation request"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized to cancel this booking"},
        404: {"description": "Booking not found"},
        409: {"description": "Booking cannot be cancelled in current status"},
    },
)
async def cancel_booking(
    booking_id: str,
    payload: CancellationRequest,
    current_user=Depends(deps.get_current_user),
    service: BookingCancellationService = Depends(get_cancellation_service),
) -> CancellationResponse:
    """
    Cancel a booking.
    
    Args:
        booking_id: Unique booking identifier
        payload: Cancellation request with reason
        current_user: User requesting cancellation
        service: Cancellation service instance
        
    Returns:
        Cancellation response with refund details
        
    Raises:
        HTTPException: If cancellation fails
    """
    try:
        logger.info(
            f"User {current_user.id} cancelling booking {booking_id}",
            extra={
                "user_id": current_user.id,
                "booking_id": booking_id,
                "reason": payload.reason,
            },
        )
        
        response = service.cancel(booking_id, payload, actor_id=current_user.id)
        
        logger.info(
            f"Booking {booking_id} cancelled successfully. "
            f"Refund amount: {response.refund_amount}"
        )
        return response
    except ValueError as e:
        logger.warning(f"Invalid cancellation for booking {booking_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except PermissionError as e:
        logger.warning(
            f"User {current_user.id} not authorized to cancel booking {booking_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error cancelling booking {booking_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to cancel booking",
        )


@router.post(
    "/bulk",
    response_model=List[CancellationResponse],
    summary="Bulk cancel bookings",
    description="Cancel multiple bookings at once. Requires admin privileges.",
    responses={
        200: {"description": "Bulk cancellation completed"},
        207: {"description": "Partial success - some cancellations failed"},
        400: {"description": "Invalid bulk cancellation request"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
    },
)
async def bulk_cancel(
    payload: BulkCancellation,
    admin=Depends(deps.get_admin_user),
    service: BookingCancellationService = Depends(get_cancellation_service),
) -> List[CancellationResponse]:
    """
    Cancel multiple bookings at once.
    
    Args:
        payload: Bulk cancellation request with booking IDs and reason
        admin: Admin user performing bulk cancellation
        service: Cancellation service instance
        
    Returns:
        List of cancellation responses
        
    Raises:
        HTTPException: If bulk cancellation fails
    """
    try:
        logger.info(
            f"Admin {admin.id} performing bulk cancellation",
            extra={
                "admin_id": admin.id,
                "booking_count": len(payload.booking_ids),
                "reason": payload.reason,
            },
        )
        
        responses = service.bulk_cancel(payload, actor_id=admin.id)
        
        success_count = sum(1 for r in responses if r.success)
        total_refund = sum(r.refund_amount or 0 for r in responses if r.success)
        
        logger.info(
            f"Bulk cancellation completed: {success_count}/{len(responses)} successful. "
            f"Total refund: {total_refund}"
        )
        
        return responses
    except ValueError as e:
        logger.warning(f"Invalid bulk cancellation request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error in bulk cancellation: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process bulk cancellation",
        )


@router.get(
    "/{booking_id}/refund-preview",
    response_model=RefundCalculation,
    summary="Preview refund calculation",
    description="Calculate potential refund amount without cancelling the booking.",
    responses={
        200: {"description": "Refund calculation retrieved successfully"},
        401: {"description": "Not authenticated"},
        404: {"description": "Booking not found"},
    },
)
async def calculate_refund(
    booking_id: str,
    current_user=Depends(deps.get_current_user),
    service: BookingCancellationService = Depends(get_cancellation_service),
) -> RefundCalculation:
    """
    Preview refund calculation for a booking.
    
    Args:
        booking_id: Unique booking identifier
        current_user: User requesting refund preview
        service: Cancellation service instance
        
    Returns:
        Refund calculation details
        
    Raises:
        HTTPException: If calculation fails
    """
    try:
        logger.debug(f"Calculating refund preview for booking {booking_id}")
        
        refund_calc = service.calculate_refund(booking_id)
        
        logger.debug(
            f"Refund preview for booking {booking_id}: {refund_calc.refund_amount}"
        )
        return refund_calc
    except Exception as e:
        logger.error(
            f"Error calculating refund for booking {booking_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate refund",
        )


@router.get(
    "/policy/{hostel_id}",
    response_model=CancellationPolicy,
    summary="Get cancellation policy",
    description="Retrieve the cancellation and refund policy for a hostel.",
    responses={
        200: {"description": "Cancellation policy retrieved successfully"},
        404: {"description": "Hostel not found"},
    },
)
async def get_cancellation_policy(
    hostel_id: str,
    service: BookingCancellationService = Depends(get_cancellation_service),
) -> CancellationPolicy:
    """
    Get cancellation policy for a hostel.
    
    Args:
        hostel_id: Unique hostel identifier
        service: Cancellation service instance
        
    Returns:
        Cancellation policy details
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.debug(f"Fetching cancellation policy for hostel {hostel_id}")
        
        policy = service.get_policy(hostel_id)
        
        return policy
    except Exception as e:
        logger.error(
            f"Error fetching cancellation policy for hostel {hostel_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve cancellation policy",
        )


@router.put(
    "/policy/{hostel_id}",
    response_model=CancellationPolicy,
    summary="Update cancellation policy",
    description="Update cancellation and refund policy for a hostel. Requires admin privileges.",
    responses={
        200: {"description": "Policy updated successfully"},
        400: {"description": "Invalid policy data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Hostel not found"},
    },
)
async def update_cancellation_policy(
    hostel_id: str,
    payload: CancellationPolicy,
    admin=Depends(deps.get_admin_user),
    service: BookingCancellationService = Depends(get_cancellation_service),
) -> CancellationPolicy:
    """
    Update cancellation policy for a hostel.
    
    Args:
        hostel_id: Unique hostel identifier
        payload: Updated cancellation policy
        admin: Admin user updating the policy
        service: Cancellation service instance
        
    Returns:
        Updated cancellation policy
        
    Raises:
        HTTPException: If update fails
    """
    try:
        logger.info(
            f"Admin {admin.id} updating cancellation policy for hostel {hostel_id}",
            extra={"admin_id": admin.id, "hostel_id": hostel_id},
        )
        
        updated_policy = service.update_policy(hostel_id, payload)
        
        logger.info(f"Cancellation policy updated for hostel {hostel_id}")
        return updated_policy
    except ValueError as e:
        logger.warning(
            f"Invalid cancellation policy for hostel {hostel_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error updating cancellation policy for hostel {hostel_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update cancellation policy",
        )
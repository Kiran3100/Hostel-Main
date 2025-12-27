"""
Booking Approval API

Handles booking approval workflows including:
- Approving individual bookings
- Rejecting bookings with reasons
- Bulk approval operations
- Approval settings management
"""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger
from app.schemas.booking.booking_approval import (
    ApprovalResponse,
    ApprovalSettings,
    BookingApprovalRequest,
    BulkApprovalRequest,
    RejectionRequest,
)
from app.services.booking.booking_approval_service import BookingApprovalService

logger = get_logger(__name__)

router = APIRouter(prefix="/bookings/approval", tags=["bookings:approval"])


def get_approval_service(db: Session = Depends(deps.get_db)) -> BookingApprovalService:
    """
    Dependency injection for BookingApprovalService.
    
    Args:
        db: Database session
        
    Returns:
        BookingApprovalService instance
    """
    return BookingApprovalService(db=db)


@router.post(
    "/{booking_id}/approve",
    response_model=ApprovalResponse,
    summary="Approve booking",
    description="Approve a pending booking. Requires admin privileges.",
    responses={
        200: {"description": "Booking approved successfully"},
        400: {"description": "Invalid approval request"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Booking not found"},
        409: {"description": "Booking cannot be approved in current status"},
    },
)
async def approve_booking(
    booking_id: str,
    payload: BookingApprovalRequest,
    admin=Depends(deps.get_admin_user),
    service: BookingApprovalService = Depends(get_approval_service),
) -> ApprovalResponse:
    """
    Approve a booking.
    
    Args:
        booking_id: Unique booking identifier
        payload: Approval request data
        admin: Admin user performing the approval
        service: Approval service instance
        
    Returns:
        Approval response with updated booking status
        
    Raises:
        HTTPException: If approval fails
    """
    try:
        logger.info(
            f"Admin {admin.id} approving booking {booking_id}",
            extra={"admin_id": admin.id, "booking_id": booking_id},
        )
        
        response = service.approve(booking_id, payload, approver_id=admin.id)
        
        logger.info(f"Booking {booking_id} approved successfully")
        return response
    except ValueError as e:
        logger.warning(f"Invalid approval request for booking {booking_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error approving booking {booking_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to approve booking",
        )


@router.post(
    "/{booking_id}/reject",
    response_model=ApprovalResponse,
    summary="Reject booking",
    description="Reject a pending booking with a reason. Requires admin privileges.",
    responses={
        200: {"description": "Booking rejected successfully"},
        400: {"description": "Invalid rejection request"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Booking not found"},
        409: {"description": "Booking cannot be rejected in current status"},
    },
)
async def reject_booking(
    booking_id: str,
    payload: RejectionRequest,
    admin=Depends(deps.get_admin_user),
    service: BookingApprovalService = Depends(get_approval_service),
) -> ApprovalResponse:
    """
    Reject a booking.
    
    Args:
        booking_id: Unique booking identifier
        payload: Rejection request data with reason
        admin: Admin user performing the rejection
        service: Approval service instance
        
    Returns:
        Approval response with updated booking status
        
    Raises:
        HTTPException: If rejection fails
    """
    try:
        logger.info(
            f"Admin {admin.id} rejecting booking {booking_id}",
            extra={
                "admin_id": admin.id,
                "booking_id": booking_id,
                "reason": payload.reason,
            },
        )
        
        response = service.reject(booking_id, payload, rejector_id=admin.id)
        
        logger.info(f"Booking {booking_id} rejected successfully")
        return response
    except ValueError as e:
        logger.warning(f"Invalid rejection request for booking {booking_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error rejecting booking {booking_id}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reject booking",
        )


@router.post(
    "/bulk",
    response_model=List[ApprovalResponse],
    summary="Bulk approve bookings",
    description="Approve multiple bookings in a single operation. Requires admin privileges.",
    responses={
        200: {"description": "Bulk approval completed"},
        207: {"description": "Partial success - some bookings failed"},
        400: {"description": "Invalid bulk approval request"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
    },
)
async def bulk_approve(
    payload: BulkApprovalRequest,
    admin=Depends(deps.get_admin_user),
    service: BookingApprovalService = Depends(get_approval_service),
) -> List[ApprovalResponse]:
    """
    Approve multiple bookings at once.
    
    Args:
        payload: Bulk approval request with list of booking IDs
        admin: Admin user performing the approvals
        service: Approval service instance
        
    Returns:
        List of approval responses for each booking
        
    Raises:
        HTTPException: If bulk approval fails
    """
    try:
        logger.info(
            f"Admin {admin.id} performing bulk approval",
            extra={
                "admin_id": admin.id,
                "booking_count": len(payload.booking_ids),
            },
        )
        
        responses = service.bulk_approve(payload, approver_id=admin.id)
        
        success_count = sum(1 for r in responses if r.success)
        logger.info(
            f"Bulk approval completed: {success_count}/{len(responses)} successful"
        )
        
        return responses
    except ValueError as e:
        logger.warning(f"Invalid bulk approval request: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"Error in bulk approval: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process bulk approval",
        )


@router.get(
    "/settings/{hostel_id}",
    response_model=ApprovalSettings,
    summary="Get approval settings",
    description="Retrieve approval configuration for a specific hostel.",
    responses={
        200: {"description": "Approval settings retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Hostel not found"},
    },
)
async def get_approval_settings(
    hostel_id: str,
    admin=Depends(deps.get_admin_user),
    service: BookingApprovalService = Depends(get_approval_service),
) -> ApprovalSettings:
    """
    Get approval settings for a hostel.
    
    Args:
        hostel_id: Unique hostel identifier
        admin: Admin user requesting settings
        service: Approval service instance
        
    Returns:
        Approval settings configuration
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.debug(f"Fetching approval settings for hostel {hostel_id}")
        settings = service.get_settings(hostel_id)
        return settings
    except Exception as e:
        logger.error(
            f"Error fetching approval settings for hostel {hostel_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve approval settings",
        )


@router.put(
    "/settings/{hostel_id}",
    response_model=ApprovalSettings,
    summary="Update approval settings",
    description="Update approval configuration for a specific hostel.",
    responses={
        200: {"description": "Approval settings updated successfully"},
        400: {"description": "Invalid settings data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Hostel not found"},
    },
)
async def update_approval_settings(
    hostel_id: str,
    payload: ApprovalSettings,
    admin=Depends(deps.get_admin_user),
    service: BookingApprovalService = Depends(get_approval_service),
) -> ApprovalSettings:
    """
    Update approval settings for a hostel.
    
    Args:
        hostel_id: Unique hostel identifier
        payload: Updated approval settings
        admin: Admin user updating settings
        service: Approval service instance
        
    Returns:
        Updated approval settings
        
    Raises:
        HTTPException: If update fails
    """
    try:
        logger.info(
            f"Admin {admin.id} updating approval settings for hostel {hostel_id}",
            extra={"admin_id": admin.id, "hostel_id": hostel_id},
        )
        
        updated_settings = service.update_settings(hostel_id, payload)
        
        logger.info(f"Approval settings updated for hostel {hostel_id}")
        return updated_settings
    except ValueError as e:
        logger.warning(
            f"Invalid approval settings for hostel {hostel_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error updating approval settings for hostel {hostel_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update approval settings",
        )
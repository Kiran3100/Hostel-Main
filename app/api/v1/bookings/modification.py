"""
Booking Modification API

Handles booking modification requests including:
- Requesting changes to existing bookings
- Approving or rejecting modification requests
- Tracking modification history
"""

from typing import Any, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.logging import get_logger
from app.schemas.booking.booking_modification import (
    ModificationApproval,
    ModificationRequest,
    ModificationResponse,
)
from app.services.booking.booking_modification_service import (
    BookingModificationService,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/bookings/modification", tags=["bookings:modification"])


def get_modification_service(
    db: Session = Depends(deps.get_db),
) -> BookingModificationService:
    """
    Dependency injection for BookingModificationService.
    
    Args:
        db: Database session
        
    Returns:
        BookingModificationService instance
    """
    return BookingModificationService(db=db)


@router.post(
    "/{booking_id}/request",
    response_model=ModificationResponse,
    summary="Request booking modification",
    description="Submit a modification request for an existing booking.",
    responses={
        200: {"description": "Modification request submitted successfully"},
        400: {"description": "Invalid modification request"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized to modify this booking"},
        404: {"description": "Booking not found"},
        409: {"description": "Booking cannot be modified in current status"},
    },
)
async def request_modification(
    booking_id: str,
    payload: ModificationRequest,
    current_user=Depends(deps.get_current_user),
    service: BookingModificationService = Depends(get_modification_service),
) -> ModificationResponse:
    """
    Request modification to a booking.
    
    Args:
        booking_id: Unique booking identifier
        payload: Modification request details
        current_user: User requesting modification
        service: Modification service instance
        
    Returns:
        Modification response with request details
        
    Raises:
        HTTPException: If request submission fails
    """
    try:
        logger.info(
            f"User {current_user.id} requesting modification for booking {booking_id}",
            extra={
                "user_id": current_user.id,
                "booking_id": booking_id,
                "changes": payload.dict(exclude_unset=True),
            },
        )
        
        response = service.request_modification(
            booking_id, payload, requester_id=current_user.id
        )
        
        logger.info(
            f"Modification request created: {response.request_id} for booking {booking_id}"
        )
        return response
    except ValueError as e:
        logger.warning(
            f"Invalid modification request for booking {booking_id}: {str(e)}"
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except PermissionError as e:
        logger.warning(
            f"User {current_user.id} not authorized to modify booking {booking_id}"
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error requesting modification for booking {booking_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit modification request",
        )


@router.post(
    "/requests/{request_id}/decide",
    response_model=ModificationResponse,
    summary="Approve or reject modification",
    description="Approve or reject a pending modification request. Requires admin privileges.",
    responses={
        200: {"description": "Modification request processed successfully"},
        400: {"description": "Invalid approval/rejection data"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
        404: {"description": "Modification request not found"},
        409: {"description": "Request already processed"},
    },
)
async def decide_modification(
    request_id: str,
    payload: ModificationApproval,
    admin=Depends(deps.get_admin_user),
    service: BookingModificationService = Depends(get_modification_service),
) -> ModificationResponse:
    """
    Approve or reject a modification request.
    
    Args:
        request_id: Unique modification request identifier
        payload: Approval decision and optional notes
        admin: Admin user making the decision
        service: Modification service instance
        
    Returns:
        Updated modification response
        
    Raises:
        HTTPException: If decision processing fails
    """
    try:
        logger.info(
            f"Admin {admin.id} deciding on modification request {request_id}",
            extra={
                "admin_id": admin.id,
                "request_id": request_id,
                "approved": payload.approved,
            },
        )
        
        response = service.approve_modification(
            request_id, payload, approver_id=admin.id
        )
        
        action = "approved" if payload.approved else "rejected"
        logger.info(f"Modification request {request_id} {action}")
        
        return response
    except ValueError as e:
        logger.warning(f"Invalid decision for request {request_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(
            f"Error processing modification request {request_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process modification request",
        )


@router.get(
    "/{booking_id}/requests",
    response_model=List[ModificationResponse],
    summary="Get modification requests for booking",
    description="Retrieve all modification requests for a specific booking.",
    responses={
        200: {"description": "Modification requests retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Not authorized to view these requests"},
        404: {"description": "Booking not found"},
    },
)
async def get_booking_modifications(
    booking_id: str,
    status_filter: str = Query(None, description="Filter by request status"),
    current_user=Depends(deps.get_current_user),
    service: BookingModificationService = Depends(get_modification_service),
) -> List[ModificationResponse]:
    """
    Get modification requests for a booking.
    
    Args:
        booking_id: Unique booking identifier
        status_filter: Optional status filter (pending, approved, rejected)
        current_user: User requesting the list
        service: Modification service instance
        
    Returns:
        List of modification requests
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.debug(
            f"Fetching modification requests for booking {booking_id}",
            extra={"booking_id": booking_id, "status_filter": status_filter},
        )
        
        requests = service.get_booking_requests(
            booking_id, status=status_filter
        )
        
        logger.debug(
            f"Retrieved {len(requests)} modification requests for booking {booking_id}"
        )
        return requests
    except Exception as e:
        logger.error(
            f"Error fetching modification requests for booking {booking_id}: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve modification requests",
        )


@router.get(
    "/requests/pending",
    response_model=List[ModificationResponse],
    summary="Get all pending modification requests",
    description="Retrieve all pending modification requests. Requires admin privileges.",
    responses={
        200: {"description": "Pending requests retrieved successfully"},
        401: {"description": "Not authenticated"},
        403: {"description": "Insufficient permissions"},
    },
)
async def get_pending_modifications(
    hostel_id: str = Query(None, description="Filter by hostel"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    admin=Depends(deps.get_admin_user),
    service: BookingModificationService = Depends(get_modification_service),
) -> List[ModificationResponse]:
    """
    Get all pending modification requests.
    
    Args:
        hostel_id: Optional hostel filter
        skip: Pagination offset
        limit: Maximum records to return
        admin: Admin user requesting the list
        service: Modification service instance
        
    Returns:
        List of pending modification requests
        
    Raises:
        HTTPException: If retrieval fails
    """
    try:
        logger.debug(
            f"Admin {admin.id} fetching pending modification requests",
            extra={"admin_id": admin.id, "hostel_id": hostel_id},
        )
        
        requests = service.get_pending_requests(
            hostel_id=hostel_id,
            skip=skip,
            limit=limit,
        )
        
        logger.debug(f"Retrieved {len(requests)} pending modification requests")
        return requests
    except Exception as e:
        logger.error(
            f"Error fetching pending modification requests: {str(e)}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve pending modification requests",
        )
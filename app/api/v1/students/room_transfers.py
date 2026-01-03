"""
Student Room Transfer API Endpoints

Provides endpoints for managing room transfer requests and room swap operations.
"""
from typing import List, Optional
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, Path, status, Body, Query

from app.core.dependencies import get_current_user
from app.services.student.room_transfer_service import RoomTransferService
from app.schemas.room.room_transfer import (
    RoomTransferRequest,
    RoomTransferRequestCreate,
    RoomTransferHistory,
    RoomSwapRequest,
    TransferStatus,
)
from app.schemas.common.base import User

router = APIRouter(
    prefix="/students",
    tags=["Students - Room Transfers"],
)


def get_transfer_service() -> RoomTransferService:
    """
    Dependency injection for RoomTransferService.
    
    Returns:
        RoomTransferService: Instance of the room transfer service
        
    Raises:
        NotImplementedError: To be implemented with actual service instantiation
    """
    raise NotImplementedError("RoomTransferService dependency not configured")


# ==================== Room Transfer Request Endpoints ====================


@router.post(
    "/{student_id}/transfers",
    response_model=RoomTransferRequest,
    status_code=status.HTTP_201_CREATED,
    summary="Request room transfer",
    description="Submit a new room transfer request.",
    responses={
        201: {"description": "Transfer request created successfully"},
        400: {"description": "Invalid transfer request or pending request exists"},
        401: {"description": "Unauthorized"},
        404: {"description": "Student or target room not found"},
    },
)
async def request_transfer(
    student_id: UUID = Path(..., description="Unique student identifier"),
    payload: RoomTransferRequestCreate = Body(
        ...,
        description="Transfer request details including target room and reason",
    ),
    transfer_service: RoomTransferService = Depends(get_transfer_service),
    current_user: User = Depends(get_current_user),
) -> RoomTransferRequest:
    """
    Submit a room transfer request.
    
    Validates:
    - Student doesn't have pending transfer requests
    - Target room has available capacity
    - Transfer reason is provided
    
    Args:
        student_id: UUID of the student
        payload: Transfer request data
        transfer_service: Injected transfer service
        current_user: Authenticated user from dependency
        
    Returns:
        RoomTransferRequest: Created transfer request
    """
    transfer_data = payload.dict()
    transfer_data["student_id"] = str(student_id)
    transfer_data["requested_by"] = current_user.id
    
    result = transfer_service.submit_transfer_request(data=transfer_data)
    return result.unwrap()


@router.get(
    "/{student_id}/transfers",
    response_model=List[RoomTransferRequest],
    status_code=status.HTTP_200_OK,
    summary="List student transfer requests",
    description="Retrieve all transfer requests for a student.",
)
async def list_transfer_requests(
    student_id: UUID = Path(..., description="Unique student identifier"),
    status_filter: Optional[TransferStatus] = Query(
        None,
        description="Filter by transfer status",
    ),
    transfer_service: RoomTransferService = Depends(get_transfer_service),
    current_user: User = Depends(get_current_user),
) -> List[RoomTransferRequest]:
    """
    List all transfer requests for a student.
    
    Args:
        student_id: UUID of the student
        status_filter: Optional status filter
        transfer_service: Injected transfer service
        current_user: Authenticated user from dependency
        
    Returns:
        List[RoomTransferRequest]: List of transfer requests
    """
    result = transfer_service.list_transfer_requests(
        student_id=str(student_id),
        status=status_filter.value if status_filter else None,
    )
    return result.unwrap()


@router.get(
    "/{student_id}/transfers/{transfer_id}",
    response_model=RoomTransferRequest,
    status_code=status.HTTP_200_OK,
    summary="Get transfer request details",
    description="Retrieve detailed information about a specific transfer request.",
)
async def get_transfer_request_detail(
    student_id: UUID = Path(..., description="Unique student identifier"),
    transfer_id: UUID = Path(..., description="Unique transfer request identifier"),
    transfer_service: RoomTransferService = Depends(get_transfer_service),
    current_user: User = Depends(get_current_user),
) -> RoomTransferRequest:
    """
    Get detailed information about a transfer request.
    
    Args:
        student_id: UUID of the student
        transfer_id: UUID of the transfer request
        transfer_service: Injected transfer service
        current_user: Authenticated user from dependency
        
    Returns:
        RoomTransferRequest: Transfer request details
    """
    result = transfer_service.get_transfer_request_by_id(
        transfer_id=str(transfer_id),
        student_id=str(student_id),
    )
    return result.unwrap()


@router.get(
    "/{student_id}/transfers/history",
    response_model=List[RoomTransferHistory],
    status_code=status.HTTP_200_OK,
    summary="Get room transfer history",
    description="Retrieve complete history of room changes for a student.",
)
async def get_transfer_history(
    student_id: UUID = Path(..., description="Unique student identifier"),
    start_date: Optional[date] = Query(
        None,
        description="Filter history from this date",
    ),
    end_date: Optional[date] = Query(
        None,
        description="Filter history until this date",
    ),
    transfer_service: RoomTransferService = Depends(get_transfer_service),
    current_user: User = Depends(get_current_user),
) -> List[RoomTransferHistory]:
    """
    Get complete room transfer history for a student.
    
    Shows chronological history of all room changes including:
    - Transfer dates
    - Previous and new rooms
    - Transfer reasons
    - Approval details
    
    Args:
        student_id: UUID of the student
        start_date: Optional start date filter
        end_date: Optional end date filter
        transfer_service: Injected transfer service
        current_user: Authenticated user from dependency
        
    Returns:
        List[RoomTransferHistory]: Chronological room history
    """
    result = transfer_service.get_room_history(
        student_id=str(student_id),
        start_date=start_date,
        end_date=end_date,
    )
    return result.unwrap()


@router.patch(
    "/{student_id}/transfers/{transfer_id}/cancel",
    response_model=RoomTransferRequest,
    status_code=status.HTTP_200_OK,
    summary="Cancel transfer request",
    description="Cancel a pending transfer request.",
)
async def cancel_transfer_request(
    student_id: UUID = Path(..., description="Unique student identifier"),
    transfer_id: UUID = Path(..., description="Unique transfer request identifier"),
    cancellation_reason: Optional[str] = Body(
        None,
        embed=True,
        description="Reason for cancellation",
    ),
    transfer_service: RoomTransferService = Depends(get_transfer_service),
    current_user: User = Depends(get_current_user),
) -> RoomTransferRequest:
    """
    Cancel a pending transfer request.
    
    Args:
        student_id: UUID of the student
        transfer_id: UUID of the transfer request
        cancellation_reason: Optional reason for cancellation
        transfer_service: Injected transfer service
        current_user: Authenticated user from dependency
        
    Returns:
        RoomTransferRequest: Updated transfer request
    """
    result = transfer_service.cancel_transfer_request(
        transfer_id=str(transfer_id),
        student_id=str(student_id),
        reason=cancellation_reason,
    )
    return result.unwrap()


# ==================== Transfer Approval Endpoints (Admin/Staff) ====================


@router.post(
    "/transfers/{transfer_id}/approve",
    response_model=RoomTransferRequest,
    status_code=status.HTTP_200_OK,
    summary="Approve transfer request",
    description="Approve a pending room transfer request (admin/staff only).",
)
async def approve_transfer(
    transfer_id: UUID = Path(..., description="Unique transfer request identifier"),
    approval_notes: Optional[str] = Body(
        None,
        embed=True,
        description="Optional notes about the approval",
    ),
    effective_date: Optional[date] = Body(
        None,
        embed=True,
        description="When the transfer should take effect",
    ),
    transfer_service: RoomTransferService = Depends(get_transfer_service),
    current_user: User = Depends(get_current_user),
) -> RoomTransferRequest:
    """
    Approve a room transfer request.
    
    This will:
    - Update transfer status to APPROVED
    - Schedule the room change
    - Notify the student
    
    Args:
        transfer_id: UUID of the transfer request
        approval_notes: Optional approval notes
        effective_date: When the transfer takes effect
        transfer_service: Injected transfer service
        current_user: Authenticated user from dependency
        
    Returns:
        RoomTransferRequest: Updated transfer request
    """
    result = transfer_service.approve_transfer(
        transfer_id=str(transfer_id),
        approver_id=current_user.id,
        notes=approval_notes,
        effective_date=effective_date,
    )
    return result.unwrap()


@router.post(
    "/transfers/{transfer_id}/reject",
    response_model=RoomTransferRequest,
    status_code=status.HTTP_200_OK,
    summary="Reject transfer request",
    description="Reject a pending room transfer request (admin/staff only).",
)
async def reject_transfer(
    transfer_id: UUID = Path(..., description="Unique transfer request identifier"),
    rejection_reason: str = Body(
        ...,
        embed=True,
        description="Reason for rejection",
    ),
    transfer_service: RoomTransferService = Depends(get_transfer_service),
    current_user: User = Depends(get_current_user),
) -> RoomTransferRequest:
    """
    Reject a room transfer request.
    
    Args:
        transfer_id: UUID of the transfer request
        rejection_reason: Reason for rejection
        transfer_service: Injected transfer service
        current_user: Authenticated user from dependency
        
    Returns:
        RoomTransferRequest: Updated transfer request
    """
    result = transfer_service.reject_transfer(
        transfer_id=str(transfer_id),
        rejected_by=current_user.id,
        reason=rejection_reason,
    )
    return result.unwrap()


# ==================== Room Swap Endpoints ====================


@router.post(
    "/transfers/swap",
    response_model=RoomSwapRequest,
    status_code=status.HTTP_201_CREATED,
    summary="Request room swap between students",
    description="Initiate a room swap request between two students.",
    responses={
        201: {"description": "Swap request created successfully"},
        400: {"description": "Invalid swap request or students not eligible"},
        401: {"description": "Unauthorized"},
    },
)
async def request_swap(
    student_id_1: UUID = Body(..., description="First student ID"),
    student_id_2: UUID = Body(..., description="Second student ID"),
    reason: str = Body(..., description="Reason for room swap"),
    transfer_service: RoomTransferService = Depends(get_transfer_service),
    current_user: User = Depends(get_current_user),
) -> RoomSwapRequest:
    """
    Request a room swap between two students.
    
    Both students must:
    - Be in different rooms
    - Have compatible room types
    - Not have pending transfer requests
    - Consent to the swap
    
    Args:
        student_id_1: UUID of first student
        student_id_2: UUID of second student
        reason: Reason for the swap
        transfer_service: Injected transfer service
        current_user: Authenticated user from dependency
        
    Returns:
        RoomSwapRequest: Created swap request
    """
    result = transfer_service.request_room_swap(
        student1_id=str(student_id_1),
        student2_id=str(student_id_2),
        reason=reason,
        requested_by=current_user.id,
    )
    return result.unwrap()


@router.get(
    "/transfers/swaps/pending",
    response_model=List[RoomSwapRequest],
    status_code=status.HTTP_200_OK,
    summary="List pending swap requests",
    description="Retrieve all pending room swap requests.",
)
async def list_pending_swaps(
    transfer_service: RoomTransferService = Depends(get_transfer_service),
    current_user: User = Depends(get_current_user),
) -> List[RoomSwapRequest]:
    """
    List all pending room swap requests.
    
    Args:
        transfer_service: Injected transfer service
        current_user: Authenticated user from dependency
        
    Returns:
        List[RoomSwapRequest]: List of pending swap requests
    """
    result = transfer_service.list_pending_swaps()
    return result.unwrap()


@router.post(
    "/transfers/swaps/{swap_id}/approve",
    response_model=RoomSwapRequest,
    status_code=status.HTTP_200_OK,
    summary="Approve room swap",
    description="Approve a room swap request (admin/staff only).",
)
async def approve_swap(
    swap_id: UUID = Path(..., description="Unique swap request identifier"),
    effective_date: Optional[date] = Body(
        None,
        embed=True,
        description="When the swap should take effect",
    ),
    transfer_service: RoomTransferService = Depends(get_transfer_service),
    current_user: User = Depends(get_current_user),
) -> RoomSwapRequest:
    """
    Approve a room swap request.
    
    This will swap the rooms of both students atomically.
    
    Args:
        swap_id: UUID of the swap request
        effective_date: When the swap takes effect
        transfer_service: Injected transfer service
        current_user: Authenticated user from dependency
        
    Returns:
        RoomSwapRequest: Updated swap request
    """
    result = transfer_service.approve_swap(
        swap_id=str(swap_id),
        approver_id=current_user.id,
        effective_date=effective_date,
    )
    return result.unwrap()
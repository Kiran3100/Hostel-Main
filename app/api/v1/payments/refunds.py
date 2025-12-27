"""
Payment refund management API endpoints.

Handles refund requests, approvals, rejections, and tracking.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, Path, Query, status, HTTPException

from app.core.dependencies import get_current_user
from app.services.payment.payment_refund_service import PaymentRefundService
from app.schemas.payment import (
    RefundRequest,
    RefundResponse,
    RefundListItem,
    BulkRefundApproval,
)
from app.core.exceptions import (
    RefundNotFoundError,
    PaymentNotFoundError,
    UnauthorizedError,
    InvalidRefundRequestError,
)

router = APIRouter(tags=["Payments - Refunds"])


def get_refund_service() -> PaymentRefundService:
    """
    Factory for PaymentRefundService dependency injection.
    Should be implemented by the DI container.
    """
    raise NotImplementedError(
        "Refund service must be configured in dependency injection container"
    )


@router.post(
    "/refunds",
    response_model=RefundResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request refund",
    description="Submit a refund request for a payment.",
    responses={
        201: {"description": "Refund request created successfully"},
        400: {"description": "Invalid refund request"},
        401: {"description": "Authentication required"},
        404: {"description": "Payment not found"},
    },
)
async def request_refund(
    payload: RefundRequest,
    refund_service: PaymentRefundService = Depends(get_refund_service),
    current_user: Any = Depends(get_current_user),
) -> RefundResponse:
    """
    Submit a new refund request.

    Args:
        payload: Refund request details including payment ID, amount, and reason
        refund_service: Injected refund service
        current_user: Currently authenticated user

    Returns:
        RefundResponse: Created refund request details

    Raises:
        HTTPException: 400 for invalid requests, 404 if payment not found
    """
    result = await refund_service.request_refund(
        requested_by=current_user.id,
        data=payload,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, PaymentNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        elif isinstance(error, InvalidRefundRequestError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.post(
    "/refunds/{refund_id}/approve",
    response_model=RefundResponse,
    summary="Approve refund",
    description="Approve a pending refund request (admin only).",
    responses={
        200: {"description": "Refund approved successfully"},
        400: {"description": "Refund cannot be approved"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Refund not found"},
    },
)
async def approve_refund(
    refund_id: str = Path(..., description="Refund ID to approve"),
    refund_service: PaymentRefundService = Depends(get_refund_service),
    current_user: Any = Depends(get_current_user),
) -> RefundResponse:
    """
    Approve a pending refund request.

    Args:
        refund_id: ID of the refund to approve
        refund_service: Injected refund service
        current_user: Currently authenticated user (must be admin)

    Returns:
        RefundResponse: Updated refund details

    Raises:
        HTTPException: 403 if unauthorized, 404 if not found, 400 for invalid state
    """
    result = await refund_service.approve_refund(
        refund_id=refund_id,
        approved_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, RefundNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        elif isinstance(error, UnauthorizedError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.post(
    "/refunds/{refund_id}/reject",
    response_model=RefundResponse,
    summary="Reject refund",
    description="Reject a pending refund request (admin only).",
    responses={
        200: {"description": "Refund rejected successfully"},
        400: {"description": "Refund cannot be rejected"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Refund not found"},
    },
)
async def reject_refund(
    refund_id: str = Path(..., description="Refund ID to reject"),
    reason: str = Query(..., description="Rejection reason", min_length=3),
    refund_service: PaymentRefundService = Depends(get_refund_service),
    current_user: Any = Depends(get_current_user),
) -> RefundResponse:
    """
    Reject a pending refund request.

    Args:
        refund_id: ID of the refund to reject
        reason: Reason for rejection
        refund_service: Injected refund service
        current_user: Currently authenticated user (must be admin)

    Returns:
        RefundResponse: Updated refund details

    Raises:
        HTTPException: 403 if unauthorized, 404 if not found
    """
    result = await refund_service.reject_refund(
        refund_id=refund_id,
        reason=reason,
        rejected_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, RefundNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        elif isinstance(error, UnauthorizedError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.get(
    "/refunds/payment/{payment_id}",
    response_model=List[RefundListItem],
    summary="List refunds for payment",
    description="Get all refund requests associated with a specific payment.",
    responses={
        200: {"description": "List of refunds retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Payment not found"},
    },
)
async def list_refunds_for_payment(
    payment_id: str = Path(..., description="Payment ID"),
    refund_service: PaymentRefundService = Depends(get_refund_service),
    current_user: Any = Depends(get_current_user),
) -> List[RefundListItem]:
    """
    List all refunds for a specific payment.

    Args:
        payment_id: ID of the payment
        refund_service: Injected refund service
        current_user: Currently authenticated user

    Returns:
        List[RefundListItem]: List of refunds

    Raises:
        HTTPException: 404 if payment not found
    """
    result = await refund_service.list_refunds_for_payment(
        payment_id=payment_id,
        user_id=current_user.id
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, PaymentNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.get(
    "/refunds/pending",
    response_model=List[RefundListItem],
    summary="List pending refunds",
    description="Get all pending refund requests (admin only).",
    responses={
        200: {"description": "List of pending refunds retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
    },
)
async def list_pending_refunds(
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    refund_service: PaymentRefundService = Depends(get_refund_service),
    current_user: Any = Depends(get_current_user),
) -> List[RefundListItem]:
    """
    List all pending refund requests.

    Args:
        page: Page number for pagination
        page_size: Number of items per page
        refund_service: Injected refund service
        current_user: Currently authenticated user (must be admin)

    Returns:
        List[RefundListItem]: List of pending refunds

    Raises:
        HTTPException: 403 if not admin
    """
    result = await refund_service.list_pending_refunds(
        user_id=current_user.id,
        page=page,
        page_size=page_size
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, UnauthorizedError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.post(
    "/refunds/bulk-approve",
    summary="Bulk approve refunds",
    description="Approve multiple refund requests at once (admin only).",
    responses={
        200: {"description": "Bulk approval completed"},
        400: {"description": "Invalid request"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
    },
)
async def bulk_approve_refunds(
    payload: BulkRefundApproval,
    refund_service: PaymentRefundService = Depends(get_refund_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Approve multiple refunds in a single operation.

    Args:
        payload: Bulk approval request containing refund IDs
        refund_service: Injected refund service
        current_user: Currently authenticated user (must be admin)

    Returns:
        dict: Summary of successful and failed approvals

    Raises:
        HTTPException: 403 if unauthorized
    """
    result = await refund_service.bulk_approve_refunds(
        refund_ids=payload.refund_ids,
        approved_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, UnauthorizedError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.get(
    "/refunds/{refund_id}",
    response_model=RefundResponse,
    summary="Get refund details",
    description="Retrieve detailed information about a specific refund.",
    responses={
        200: {"description": "Refund details retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Refund not found"},
    },
)
async def get_refund(
    refund_id: str = Path(..., description="Refund ID"),
    refund_service: PaymentRefundService = Depends(get_refund_service),
    current_user: Any = Depends(get_current_user),
) -> RefundResponse:
    """
    Get detailed information about a refund.

    Args:
        refund_id: ID of the refund
        refund_service: Injected refund service
        current_user: Currently authenticated user

    Returns:
        RefundResponse: Detailed refund information

    Raises:
        HTTPException: 404 if not found
    """
    result = await refund_service.get_refund(
        refund_id=refund_id,
        user_id=current_user.id
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, RefundNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=str(error)
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()
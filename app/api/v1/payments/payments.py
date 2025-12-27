"""
Core payment operations API endpoints.

Handles payment creation, retrieval, updates, and status management.
"""

from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Path, Query, status, HTTPException
from fastapi.responses import JSONResponse

from app.core.dependencies import AuthenticationDependency, get_current_user
from app.services.payment.payment_service import PaymentService
from app.schemas.payment import (
    PaymentResponse,
    PaymentDetail,
    PaymentSummary,
    PaymentCreate,
    ManualPaymentRequest,
    PaymentStatusUpdate,
    BulkPaymentStatusUpdate,
    PaymentCancellation,
)
from app.core.exceptions import PaymentNotFoundError, UnauthorizedError
from app.core.result import Result

router = APIRouter(tags=["Payments - Core"])


# Dependency injection
def get_payment_service() -> PaymentService:
    """
    Factory for PaymentService dependency injection.
    Should be implemented by the DI container.
    """
    raise NotImplementedError(
        "Payment service must be configured in dependency injection container"
    )


@router.post(
    "/manual",
    response_model=PaymentDetail,
    status_code=status.HTTP_201_CREATED,
    summary="Record manual payment",
    description="Record an offline payment (cash, cheque, bank transfer, etc.). Admin only.",
    responses={
        201: {"description": "Payment recorded successfully"},
        400: {"description": "Invalid payment data"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Student or hostel not found"},
    },
)
async def record_manual_payment(
    payload: ManualPaymentRequest,
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: Any = Depends(get_current_user),
) -> PaymentDetail:
    """
    Record a manual (offline) payment.

    This endpoint allows administrators to record payments received through
    offline channels such as cash, cheque, or direct bank transfer.

    Args:
        payload: Manual payment details including amount, method, and reference
        payment_service: Injected payment service
        current_user: Currently authenticated user

    Returns:
        PaymentDetail: Detailed information about the recorded payment

    Raises:
        HTTPException: 400 if validation fails, 403 if unauthorized, 404 if entities not found
    """
    result = await payment_service.record_manual_payment(
        data=payload,
        recorded_by=current_user.id
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, UnauthorizedError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=str(error)
            )
        elif isinstance(error, PaymentNotFoundError):
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
    "",
    response_model=List[PaymentResponse],
    summary="List payments with filters",
    description="Retrieve a paginated list of payments with optional filtering by student, hostel, or status.",
    responses={
        200: {"description": "List of payments retrieved successfully"},
        400: {"description": "Invalid filter parameters"},
        401: {"description": "Authentication required"},
    },
)
async def list_payments(
    student_id: Optional[str] = Query(
        None,
        description="Filter by student ID",
        min_length=1,
        max_length=100
    ),
    hostel_id: Optional[str] = Query(
        None,
        description="Filter by hostel ID",
        min_length=1,
        max_length=100
    ),
    status_filter: Optional[str] = Query(
        None,
        description="Filter by payment status (pending, completed, failed, cancelled)",
        regex="^(pending|completed|failed|cancelled|refunded)$"
    ),
    start_date: Optional[str] = Query(
        None,
        description="Filter payments from this date (ISO format)",
        regex=r"^\d{4}-\d{2}-\d{2}$"
    ),
    end_date: Optional[str] = Query(
        None,
        description="Filter payments until this date (ISO format)",
        regex=r"^\d{4}-\d{2}-\d{2}$"
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: Any = Depends(get_current_user),
) -> List[PaymentResponse]:
    """
    List payments with comprehensive filtering options.

    Args:
        student_id: Optional filter by student
        hostel_id: Optional filter by hostel
        status_filter: Optional filter by payment status
        start_date: Optional start date filter
        end_date: Optional end date filter
        page: Page number for pagination
        page_size: Number of items per page
        payment_service: Injected payment service
        current_user: Currently authenticated user

    Returns:
        List[PaymentResponse]: Paginated list of payments

    Raises:
        HTTPException: 400 if invalid filters, 401 if unauthorized
    """
    filters = {
        "status": status_filter,
        "start_date": start_date,
        "end_date": end_date,
        "page": page,
        "page_size": page_size,
    }
    
    # Remove None values from filters
    filters = {k: v for k, v in filters.items() if v is not None}
    
    result = None
    
    if student_id:
        result = await payment_service.list_payments_for_student(
            student_id=student_id,
            filters=filters,
        )
    elif hostel_id:
        result = await payment_service.list_payments_for_hostel(
            hostel_id=hostel_id,
            filters=filters,
        )
    else:
        # General list - requires proper authorization
        result = await payment_service.list_all_payments(
            filters=filters,
            user_id=current_user.id,
        )
    
    if result.is_err():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(result.unwrap_err())
        )
    
    return result.unwrap()


@router.get(
    "/{payment_id}",
    response_model=PaymentDetail,
    summary="Get payment details",
    description="Retrieve detailed information about a specific payment.",
    responses={
        200: {"description": "Payment details retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Access to this payment denied"},
        404: {"description": "Payment not found"},
    },
)
async def get_payment(
    payment_id: str = Path(..., description="Unique payment identifier", min_length=1),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: Any = Depends(get_current_user),
) -> PaymentDetail:
    """
    Get detailed information about a specific payment.

    Args:
        payment_id: Unique identifier of the payment
        payment_service: Injected payment service
        current_user: Currently authenticated user

    Returns:
        PaymentDetail: Comprehensive payment information

    Raises:
        HTTPException: 403 if unauthorized, 404 if not found
    """
    result = await payment_service.get_payment(
        payment_id=payment_id,
        user_id=current_user.id
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, PaymentNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment with ID {payment_id} not found"
            )
        elif isinstance(error, UnauthorizedError):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied to this payment"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.get(
    "/by-reference/{reference}",
    response_model=PaymentDetail,
    summary="Get payment by reference number",
    description="Retrieve payment details using the payment reference number.",
    responses={
        200: {"description": "Payment retrieved successfully"},
        401: {"description": "Authentication required"},
        404: {"description": "Payment not found"},
    },
)
async def get_payment_by_reference(
    reference: str = Path(..., description="Payment reference number", min_length=1),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: Any = Depends(get_current_user),
) -> PaymentDetail:
    """
    Retrieve payment by its reference number.

    Args:
        reference: Payment reference number
        payment_service: Injected payment service
        current_user: Currently authenticated user

    Returns:
        PaymentDetail: Payment information

    Raises:
        HTTPException: 404 if payment not found
    """
    result = await payment_service.get_payment_by_reference(
        reference=reference,
        user_id=current_user.id
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, PaymentNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Payment with reference {reference} not found"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error)
            )
    
    return result.unwrap()


@router.patch(
    "/{payment_id}/status",
    response_model=PaymentDetail,
    summary="Update payment status",
    description="Update the status of a payment (admin only).",
    responses={
        200: {"description": "Payment status updated successfully"},
        400: {"description": "Invalid status transition"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
        404: {"description": "Payment not found"},
    },
)
async def update_payment_status(
    payment_id: str = Path(..., description="Payment ID"),
    payload: PaymentStatusUpdate = None,
    new_status: str = Query(
        ...,
        description="New payment status",
        regex="^(pending|completed|failed|cancelled|refunded)$"
    ),
    reason: Optional[str] = Query(None, description="Reason for status change"),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: Any = Depends(get_current_user),
) -> PaymentDetail:
    """
    Update payment status with optional reason.

    Args:
        payment_id: ID of the payment to update
        new_status: New status to set
        reason: Optional reason for the status change
        payment_service: Injected payment service
        current_user: Currently authenticated user

    Returns:
        PaymentDetail: Updated payment details

    Raises:
        HTTPException: Various errors based on validation and authorization
    """
    result = await payment_service.mark_payment_status(
        payment_id=payment_id,
        status=new_status,
        reason=reason,
        updated_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, PaymentNotFoundError):
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
    "/bulk-status",
    summary="Bulk update payment status",
    description="Update status for multiple payments at once (admin only).",
    responses={
        200: {"description": "Bulk update completed"},
        400: {"description": "Invalid request"},
        401: {"description": "Authentication required"},
        403: {"description": "Admin privileges required"},
    },
)
async def bulk_update_status(
    payload: BulkPaymentStatusUpdate,
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Update status for multiple payments in a single operation.

    Args:
        payload: Bulk update request containing payment IDs and new status
        payment_service: Injected payment service
        current_user: Currently authenticated user

    Returns:
        dict: Summary of successful and failed updates

    Raises:
        HTTPException: 400 for validation errors, 403 for unauthorized access
    """
    result = await payment_service.bulk_update_status(
        payment_ids=payload.payment_ids,
        status=payload.status,
        reason=payload.reason,
        updated_by=current_user.id,
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
    "/{payment_id}/cancel",
    summary="Cancel payment",
    description="Cancel a payment with a reason.",
    responses={
        200: {"description": "Payment cancelled successfully"},
        400: {"description": "Payment cannot be cancelled"},
        401: {"description": "Authentication required"},
        403: {"description": "Unauthorized to cancel this payment"},
        404: {"description": "Payment not found"},
    },
)
async def cancel_payment(
    payment_id: str = Path(..., description="Payment ID to cancel"),
    reason: str = Query(..., description="Cancellation reason", min_length=3),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: Any = Depends(get_current_user),
) -> dict:
    """
    Cancel a payment with a specified reason.

    Args:
        payment_id: ID of payment to cancel
        reason: Reason for cancellation
        payment_service: Injected payment service
        current_user: Currently authenticated user

    Returns:
        dict: Cancellation confirmation

    Raises:
        HTTPException: Various errors based on payment state and authorization
    """
    result = await payment_service.cancel_payment(
        payment_id=payment_id,
        reason=reason,
        cancelled_by=current_user.id,
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, PaymentNotFoundError):
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
    "/summary/student/{student_id}",
    response_model=PaymentSummary,
    summary="Get student payment summary",
    description="Retrieve aggregated payment statistics for a student.",
    responses={
        200: {"description": "Summary retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied"},
        404: {"description": "Student not found"},
    },
)
async def get_student_payment_summary(
    student_id: str = Path(..., description="Student ID"),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: Any = Depends(get_current_user),
) -> PaymentSummary:
    """
    Get aggregated payment summary for a student.

    Args:
        student_id: ID of the student
        payment_service: Injected payment service
        current_user: Currently authenticated user

    Returns:
        PaymentSummary: Aggregated payment statistics

    Raises:
        HTTPException: 403 if unauthorized, 404 if student not found
    """
    result = await payment_service.get_student_payment_summary(
        student_id=student_id,
        requesting_user_id=current_user.id
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, PaymentNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Student with ID {student_id} not found"
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
    "/summary/hostel/{hostel_id}",
    response_model=PaymentSummary,
    summary="Get hostel payment summary",
    description="Retrieve aggregated payment statistics for a hostel.",
    responses={
        200: {"description": "Summary retrieved successfully"},
        401: {"description": "Authentication required"},
        403: {"description": "Access denied"},
        404: {"description": "Hostel not found"},
    },
)
async def get_hostel_payment_summary(
    hostel_id: str = Path(..., description="Hostel ID"),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: Any = Depends(get_current_user),
) -> PaymentSummary:
    """
    Get aggregated payment summary for a hostel.

    Args:
        hostel_id: ID of the hostel
        payment_service: Injected payment service
        current_user: Currently authenticated user

    Returns:
        PaymentSummary: Aggregated payment statistics

    Raises:
        HTTPException: 403 if unauthorized, 404 if hostel not found
    """
    result = await payment_service.get_hostel_payment_summary(
        hostel_id=hostel_id,
        requesting_user_id=current_user.id
    )
    
    if result.is_err():
        error = result.unwrap_err()
        if isinstance(error, PaymentNotFoundError):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Hostel with ID {hostel_id} not found"
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
"""
Student Payments API Endpoints

Provides endpoints for students to view their payment history and dues.
"""
from typing import List, Optional
from uuid import UUID
from datetime import date

from fastapi import APIRouter, Depends, Query, status, Path

from app.core.dependencies import get_current_user
from app.services.payment.payment_service import PaymentService
from app.schemas.payment import (
    PaymentResponse,
    PaymentListResponse,
    PaymentSummary,
    PaymentStatus,
    PaymentType,
)
from app.schemas.base import User

router = APIRouter(
    prefix="/students/me/payments",
    tags=["Students - Payments"],
)


def get_payment_service() -> PaymentService:
    """
    Dependency injection for PaymentService.
    
    Returns:
        PaymentService: Instance of the payment service
        
    Raises:
        NotImplementedError: To be implemented with actual service instantiation
    """
    raise NotImplementedError("PaymentService dependency not configured")


@router.get(
    "",
    response_model=PaymentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List my payments",
    description="Retrieve all payment records for the authenticated student with optional filtering.",
    responses={
        200: {"description": "Payments retrieved successfully"},
        401: {"description": "Unauthorized - Invalid or missing authentication"},
    },
)
async def list_my_payments(
    status_filter: Optional[PaymentStatus] = Query(
        None,
        alias="status",
        description="Filter by payment status",
    ),
    payment_type: Optional[PaymentType] = Query(
        None,
        description="Filter by payment type",
    ),
    start_date: Optional[date] = Query(
        None,
        description="Filter payments from this date onwards",
    ),
    end_date: Optional[date] = Query(
        None,
        description="Filter payments until this date",
    ),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: User = Depends(get_current_user),
) -> PaymentListResponse:
    """
    List all payment records for the authenticated student.
    
    Args:
        status_filter: Optional status filter (PENDING, COMPLETED, FAILED, REFUNDED)
        payment_type: Optional payment type filter (HOSTEL_FEE, MESS_FEE, etc.)
        start_date: Filter by start date
        end_date: Filter by end date
        page: Page number for pagination
        page_size: Number of items per page
        payment_service: Injected payment service
        current_user: Authenticated user from dependency
        
    Returns:
        PaymentListResponse: Paginated list of payments
    """
    result = payment_service.list_payments_for_student(
        student_id=current_user.id,
        status=status_filter.value if status_filter else None,
        payment_type=payment_type.value if payment_type else None,
        start_date=start_date,
        end_date=end_date,
        page=page,
        page_size=page_size,
    )
    return result.unwrap()


@router.get(
    "/{payment_id}",
    response_model=PaymentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get payment details",
    description="Retrieve detailed information about a specific payment.",
)
async def get_payment_detail(
    payment_id: UUID = Path(..., description="Unique payment identifier"),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: User = Depends(get_current_user),
) -> PaymentResponse:
    """
    Get detailed information about a specific payment.
    
    Args:
        payment_id: UUID of the payment
        payment_service: Injected payment service
        current_user: Authenticated user from dependency
        
    Returns:
        PaymentResponse: Detailed payment information
    """
    result = payment_service.get_payment_by_id(
        payment_id=str(payment_id),
        student_id=current_user.id,
    )
    return result.unwrap()


@router.get(
    "/summary",
    response_model=PaymentSummary,
    status_code=status.HTTP_200_OK,
    summary="Get my payment summary",
    description="Retrieve aggregated payment summary including total paid, pending dues, and payment statistics.",
    responses={
        200: {"description": "Payment summary retrieved successfully"},
        401: {"description": "Unauthorized"},
    },
)
async def get_my_payment_summary(
    academic_year: Optional[str] = Query(
        None,
        description="Filter by academic year (e.g., '2024-2025')",
    ),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: User = Depends(get_current_user),
) -> PaymentSummary:
    """
    Get payment summary for the authenticated student.
    
    Includes:
    - Total amount paid
    - Pending dues
    - Overdue payments
    - Payment breakdown by type
    - Payment trends
    
    Args:
        academic_year: Optional academic year filter
        payment_service: Injected payment service
        current_user: Authenticated user from dependency
        
    Returns:
        PaymentSummary: Comprehensive payment summary
    """
    result = payment_service.get_student_payment_summary(
        student_id=current_user.id,
        academic_year=academic_year,
    )
    return result.unwrap()


@router.get(
    "/dues/pending",
    response_model=List[dict],
    status_code=status.HTTP_200_OK,
    summary="Get pending dues",
    description="Retrieve all pending and overdue payment obligations.",
)
async def get_pending_dues(
    include_upcoming: bool = Query(
        False,
        description="Include upcoming dues (not yet overdue)",
    ),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: User = Depends(get_current_user),
) -> List[dict]:
    """
    Get all pending and overdue dues for the student.
    
    Args:
        include_upcoming: Whether to include upcoming (not yet due) payments
        payment_service: Injected payment service
        current_user: Authenticated user from dependency
        
    Returns:
        List[dict]: List of pending dues with due dates and amounts
    """
    result = payment_service.get_pending_dues(
        student_id=current_user.id,
        include_upcoming=include_upcoming,
    )
    return result.unwrap()


@router.get(
    "/{payment_id}/receipt",
    status_code=status.HTTP_200_OK,
    summary="Download payment receipt",
    description="Download PDF receipt for a completed payment.",
)
async def download_receipt(
    payment_id: UUID = Path(..., description="Unique payment identifier"),
    payment_service: PaymentService = Depends(get_payment_service),
    current_user: User = Depends(get_current_user),
):
    """
    Download receipt for a completed payment.
    
    Returns a PDF file with payment details.
    
    Args:
        payment_id: UUID of the payment
        payment_service: Injected payment service
        current_user: Authenticated user from dependency
        
    Returns:
        FileResponse: PDF receipt file
    """
    result = payment_service.generate_receipt(
        payment_id=str(payment_id),
        student_id=current_user.id,
    )
    return result.unwrap()
from typing import List, Union
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.payment import PaymentService
from app.schemas.payment.payment_base import PaymentCreate, PaymentUpdate
from app.schemas.payment.payment_response import (
    PaymentListItem,
    PaymentDetail,
    PaymentSummary,
)
from app.schemas.payment.payment_filters import PaymentFilterParams
from . import CurrentUser, get_current_user, get_current_admin_or_staff

router = APIRouter(tags=["Payments - Core"])


def _get_service(session: Session) -> PaymentService:
    uow = UnitOfWork(session)
    return PaymentService(uow)


@router.get("/", response_model=List[PaymentListItem])
def list_payments(
    filters: PaymentFilterParams = Depends(),
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> List[PaymentListItem]:
    """
    List payments with filters/search/sorting (admin/staff).
    """
    service = _get_service(session)
    # Expected: list_payments(filters: PaymentFilterParams) -> list[PaymentListItem]
    return service.list_payments(filters=filters)


@router.get("/{payment_id}", response_model=PaymentDetail)
def get_payment(
    payment_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> PaymentDetail:
    """
    Get detailed information about a single payment.

    (Visible to staff or the payer themselves; enforcement is in service.)
    """
    service = _get_service(session)
    # Expected: get_payment_detail(payment_id: UUID, requester_id: UUID, role: UserRole) -> PaymentDetail
    return service.get_payment_detail(
        payment_id=payment_id,
        requester_id=current_user.id,
        role=current_user.role,
    )


@router.get("/students/{student_id}", response_model=List[PaymentListItem])
def list_payments_for_student(
    student_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> List[PaymentListItem]:
    """
    List payments for a given student (admin/staff).
    """
    service = _get_service(session)
    # Expected: list_for_student(student_id: UUID) -> list[PaymentListItem]
    return service.list_for_student(student_id=student_id)


@router.get("/hostels/{hostel_id}/summary", response_model=PaymentSummary)
def get_hostel_payment_summary(
    hostel_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> PaymentSummary:
    """
    Payment summary for a hostel (total, due, overdue, etc.).
    """
    service = _get_service(session)
    # Expected: get_summary_for_hostel(hostel_id: UUID) -> PaymentSummary
    return service.get_summary_for_hostel(hostel_id=hostel_id)


@router.post(
    "/",
    response_model=PaymentDetail,
    status_code=status.HTTP_201_CREATED,
)
def create_payment(
    payload: PaymentCreate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> PaymentDetail:
    """
    Low-level create payment (primarily for admin/manual adjustments).
    Prefer /payments/initiate for interactive flows.
    """
    service = _get_service(session)
    # Expected: create_payment(data: PaymentCreate, created_by: UUID) -> PaymentDetail
    return service.create_payment(data=payload, created_by=current_user.id)


@router.patch("/{payment_id}", response_model=PaymentDetail)
def update_payment(
    payment_id: UUID,
    payload: PaymentUpdate,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> PaymentDetail:
    """
    Update a payment (status, receipt info, etc.) (admin/staff).
    """
    service = _get_service(session)
    # Expected: update_payment(payment_id: UUID, data: PaymentUpdate, updated_by: UUID) -> PaymentDetail
    return service.update_payment(
        payment_id=payment_id,
        data=payload,
        updated_by=current_user.id,
    )
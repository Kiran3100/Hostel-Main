# app/api/v1/payments/initiate.py
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.payment import PaymentRequestService
from app.schemas.payment.payment_request import (
    PaymentRequest,
    PaymentInitiation,
    ManualPaymentRequest,
    BulkPaymentRequest,
    SinglePaymentRecord,
)
from app.schemas.payment.payment_response import PaymentDetail
from . import CurrentUser, get_current_user, get_current_admin_or_staff

router = APIRouter(tags=["Payments - Initiation"])


def _get_service(session: Session) -> PaymentRequestService:
    uow = UnitOfWork(session)
    return PaymentRequestService(uow)


@router.post("/online", response_model=PaymentInitiation, status_code=status.HTTP_201_CREATED)
def initiate_online_payment(
    payload: PaymentRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> PaymentInitiation:
    """
    Start an online payment flow (creates Payment + gateway order).
    """
    service = _get_service(session)
    # Expected: initiate_online_payment(requester_id: UUID, data: PaymentRequest) -> PaymentInitiation
    return service.initiate_online_payment(
        requester_id=current_user.id,
        data=payload,
    )


@router.post("/manual", response_model=PaymentDetail, status_code=status.HTTP_201_CREATED)
def record_manual_payment(
    payload: ManualPaymentRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> PaymentDetail:
    """
    Record a completed manual payment (cash/cheque/bank_transfer).
    """
    service = _get_service(session)
    # Expected: record_manual_payment(collector_id: UUID, data: ManualPaymentRequest) -> PaymentDetail
    return service.record_manual_payment(
        collector_id=current_user.id,
        data=payload,
    )


@router.post("/bulk", response_model=list[SinglePaymentRecord], status_code=status.HTTP_201_CREATED)
def bulk_create_payments(
    payload: BulkPaymentRequest,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_admin_or_staff),
) -> list[SinglePaymentRecord]:
    """
    Bulk-create/manual payments (e.g., import from CSV).
    """
    service = _get_service(session)
    # Expected: bulk_create_payments(creator_id: UUID, data: BulkPaymentRequest) -> list[SinglePaymentRecord]
    return service.bulk_create_payments(
        creator_id=current_user.id,
        data=payload,
    )
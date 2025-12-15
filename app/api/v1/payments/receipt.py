# app/api/v1/payments/receipt.py
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core import get_session
from app.services import UnitOfWork
from app.services.payment import PaymentService
from app.schemas.payment.payment_response import PaymentReceipt
from . import CurrentUser, get_current_user

router = APIRouter(tags=["Payments - Receipt"])


def _get_service(session: Session) -> PaymentService:
    uow = UnitOfWork(session)
    return PaymentService(uow)


@router.get("/{payment_id}", response_model=PaymentReceipt)
def get_payment_receipt(
    payment_id: UUID,
    session: Session = Depends(get_session),
    current_user: CurrentUser = Depends(get_current_user),
) -> PaymentReceipt:
    """
    Get a printable receipt view for a payment.

    (Visible to staff or the payer; enforcement is in service.)
    """
    service = _get_service(session)
    # Expected: get_receipt(payment_id: UUID, requester_id: UUID, role: UserRole) -> PaymentReceipt
    return service.get_receipt(
        payment_id=payment_id,
        requester_id=current_user.id,
        role=current_user.role,
    )